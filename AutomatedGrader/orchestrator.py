import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from setup_env import setup_gemini_env
import AgentObservability  # initializes logging
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai import types

from AutomatedGrader.ingestion import extract_text
from AutomatedGrader.tools.plagiarism import check_plagiarism
from AutomatedGrader.tools.ai_detection import detect_ai_generated
from AutomatedGrader.agents.grading_agent import create_grading_app
from AutomatedGrader.agents.feedback_agent import create_feedback_app
import logging


APP_NAME = "AutomatedGrader"
USER_ID = "grader_user"

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationState:
    paused: bool = False
    current_stage: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class AutomatedGraderOrchestrator:
    def __init__(self) -> None:
        self.state = OrchestrationState()
        self.session_service = InMemorySessionService()
        self.memory_service = InMemoryMemoryService()
        self.grading_runner: Optional[Runner] = None
        self.feedback_runner: Optional[Runner] = None

    def pause(self):
        self.state.paused = True

    def resume(self):
        self.state.paused = False

    async def _await_resume(self, stage: str):
        self.state.current_stage = stage
        while self.state.paused:
            await asyncio.sleep(0.25)

    def _sanitize_text(self, text: str) -> str:
        """Sanitize student text to prevent prompt injection.
        
        Removes instruction-like patterns and excessive special characters.
        """
        # Remove potential injection patterns
        sanitized = re.sub(r'(?i)(ignore|disregard|forget)\s+(previous|all|the)\s+(instructions?|prompts?|rules?)', 
                          '[REDACTED]', text)
        sanitized = re.sub(r'(?i)system\s*[:>]', '[REDACTED]', sanitized)
        sanitized = re.sub(r'(?i)assistant\s*[:>]', '[REDACTED]', sanitized)
        return sanitized

    async def setup(self):
        setup_gemini_env()
        grading_app = create_grading_app()
        feedback_app = create_feedback_app()
        self.grading_runner = Runner(
            app=grading_app,
            session_service=self.session_service,
            memory_service=self.memory_service,
        )
        self.feedback_runner = Runner(
            app=feedback_app,
            session_service=self.session_service,
            memory_service=self.memory_service,
        )
        logger.info("Orchestrator setup complete")

    async def _run_agent(self, runner: Runner, session_id: str, prompt: str) -> Dict[str, Any]:
        # Ensure the session exists - check first to avoid masking errors
        try:
            session = await self.session_service.get_session(
                app_name=runner.app.name, user_id=USER_ID, session_id=session_id
            )
        except Exception:
            session = None

        if session is None:
            # Attempt to create the session if get_session returned None or failed
            try:
                session = await self.session_service.create_session(
                    app_name=runner.app.name, user_id=USER_ID, session_id=session_id
                )
            except Exception:
                session = None

        # Fallback to the provided session_id string if the service returned no object
        session_id_to_use = getattr(session, "id", None) or session_id

        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        last_json: Dict[str, Any] = {}

        def try_parse(text: str) -> Optional[Dict[str, Any]]:
            try:
                return json.loads(text)
            except Exception:
                return None

        def strip_code_fences(text: str) -> str:
            # Extract JSON inside ```json ... ``` or ``` ... ``` fences if present
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if m:
                return m.group(1).strip()
            return text

        async for event in runner.run_async(user_id=USER_ID, session_id=session_id_to_use, new_message=content):
            if event.is_final_response() and event.content.parts:
                for part in event.content.parts:
                    t = getattr(part, "text", None)
                    if not t:
                        continue
                    t = t.strip()
                    parsed = try_parse(t)
                    if not parsed:
                        t_unfenced = strip_code_fences(t)
                        parsed = try_parse(t_unfenced)
                    if parsed is not None:
                        last_json = parsed
                    else:
                        last_json = {"raw": t}
        return last_json

    async def run(self, input_path: str, rubric: Optional[str] = None, pause_after: Optional[str] = None) -> Dict[str, Any]:
        await self.setup()

        text, meta = extract_text(input_path)
        self.state.data["ingestion"] = {"meta": meta, "chars": len(text)}
        if pause_after == "ingestion":
            self.pause()
        await self._await_resume("ingestion")

        # Parallel analysis with error handling
        async def safe_plagiarism_check():
            try:
                return await asyncio.to_thread(check_plagiarism, text)
            except Exception as e:
                logger.error(f"Plagiarism check failed: {e}")
                return {"error": str(e), "confidence": "unavailable"}, []

        async def safe_ai_detection():
            try:
                return await asyncio.to_thread(detect_ai_generated, text)
            except Exception as e:
                logger.error(f"AI detection failed: {e}")
                return {"error": str(e), "risk": "unknown"}

        (plag_summary, plag_findings), ai_eval = await asyncio.gather(
            safe_plagiarism_check(), safe_ai_detection()
        )
        self.state.data["plagiarism"] = {"summary": plag_summary, "findings": plag_findings[:5]}
        self.state.data["ai_eval"] = ai_eval
        if pause_after == "analysis":
            self.pause()
        await self._await_resume("analysis")

        # Sanitize text and warn about truncation
        sanitized_text = self._sanitize_text(text)
        grading_text = sanitized_text[:8000]
        if len(sanitized_text) > 8000:
            logger.warning(f"Text truncated for grading: {len(sanitized_text)} -> 8000 chars")

        grading_prompt = (
            f"Rubric: {rubric or 'Overall clarity, accuracy, structure, evidence'}.\n"
            f"StudentText:\n{grading_text}\n"
            "Return JSON only."
        )
        grade_json = await self._run_agent(self.grading_runner, session_id="grading", prompt=grading_prompt)
        self.state.data["grade"] = grade_json
        if pause_after == "grading":
            self.pause()
        await self._await_resume("grading")

        feedback_text = sanitized_text[:6000]
        if len(sanitized_text) > 6000:
            logger.warning(f"Text truncated for feedback: {len(sanitized_text)} -> 6000 chars")

        feedback_prompt = (
            f"Based on this grade: {json.dumps(grade_json)} and analysis: {json.dumps({'plagiarism':plag_summary,'ai_eval':ai_eval})}.\n"
            f"StudentText:\n{feedback_text}\n"
            "Return JSON only."
        )
        feedback_json = await self._run_agent(self.feedback_runner, session_id="feedback", prompt=feedback_prompt)
        self.state.data["feedback"] = feedback_json

        report = {
            "input": meta,
            "analysis": {"plagiarism": plag_summary, "ai_eval": ai_eval},
            "grade": grade_json,
            "feedback": feedback_json,
        }

        os.makedirs("AutomatedGrader/output", exist_ok=True)
        out_path = os.path.join("AutomatedGrader/output", "latest_report.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return {
            "ok": True,
            "report_path": out_path,
            "grade": grade_json,
            "analysis": {"plagiarism": plag_summary, "ai_eval": ai_eval},
            "feedback": feedback_json,
        }


async def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="Automated Grader Orchestrator")
    parser.add_argument("input", help="Path to PDF/image/text file")
    parser.add_argument("--rubric", help="Rubric text", default=None)
    parser.add_argument("--pause-after", choices=["ingestion", "analysis", "grading"], default=None)
    args = parser.parse_args()

    orchestrator = AutomatedGraderOrchestrator()
    result = await orchestrator.run(args.input, rubric=args.rubric, pause_after=args.pause_after)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main_cli())