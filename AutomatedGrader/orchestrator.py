import asyncio
import json
import os
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
from AutomatedGrader.agents.grading_agent import create_grading_agent
from AutomatedGrader.agents.feedback_agent import create_feedback_agent


APP_NAME = "AutomatedGrader"
USER_ID = "grader_user"


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

    async def setup(self):
        setup_gemini_env()
        grading_agent = create_grading_agent()
        feedback_agent = create_feedback_agent()
        self.grading_runner = Runner(
            agent=grading_agent,
            app_name=APP_NAME,
            session_service=self.session_service,
            memory_service=self.memory_service,
        )
        self.feedback_runner = Runner(
            agent=feedback_agent,
            app_name=APP_NAME,
            session_service=self.session_service,
            memory_service=self.memory_service,
        )

    async def _run_agent(self, runner: Runner, session_id: str, prompt: str) -> Dict[str, Any]:
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        last_json: Dict[str, Any] = {}
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        try:
                            last_json = json.loads(part.text)
                        except Exception:
                            last_json = {"raw": part.text}
        return last_json

    async def run(self, input_path: str, rubric: Optional[str] = None, pause_after: Optional[str] = None) -> Dict[str, Any]:
        await self.setup()

        text, meta = extract_text(input_path)
        self.state.data["ingestion"] = {"meta": meta, "chars": len(text)}
        if pause_after == "ingestion":
            self.pause()
        await self._await_resume("ingestion")

        plag_task = asyncio.to_thread(check_plagiarism, text)
        ai_task = asyncio.to_thread(detect_ai_generated, text)
        (plag_summary, plag_findings), ai_eval = await asyncio.gather(plag_task, ai_task)
        self.state.data["plagiarism"] = {"summary": plag_summary, "findings": plag_findings[:5]}
        self.state.data["ai_eval"] = ai_eval
        if pause_after == "analysis":
            self.pause()
        await self._await_resume("analysis")

        grading_prompt = (
            f"Rubric: {rubric or 'Overall clarity, accuracy, structure, evidence'}.\n"
            f"StudentText:\n{text[:8000]}\n"
            "Return JSON only."
        )
        grade_json = await self._run_agent(self.grading_runner, session_id="grading", prompt=grading_prompt)
        self.state.data["grade"] = grade_json
        if pause_after == "grading":
            self.pause()
        await self._await_resume("grading")

        feedback_prompt = (
            f"Based on this grade: {json.dumps(grade_json)} and analysis: {json.dumps({'plagiarism':plag_summary,'ai_eval':ai_eval})}.\n"
            f"StudentText:\n{text[:6000]}\n"
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
        return {"ok": True, "report_path": out_path, "summary": report.get("grade", {})}


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