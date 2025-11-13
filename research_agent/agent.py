from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.google_search_tool import google_search

from google.genai import types
from typing import Iterable, Sequence, List
import json
import re

retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)


def _normalize_to_list(value: Sequence[str] | str | None) -> List[str]:
    """Convert tool output into a clean list of paper strings."""
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        # Try strict JSON first
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and isinstance(obj.get("papers"), Iterable):
                return [str(item).strip() for item in obj["papers"] if str(item).strip()]
            if isinstance(obj, list):
                return [str(item).strip() for item in obj if str(item).strip()]
        except json.JSONDecodeError:
            pass

        # Heuristic fallback: split lines and URLs
        candidates = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.search(r"https?://", line) or len(line) > 6:
                candidates.append(line)
        return candidates

    if isinstance(value, Iterable):
        return [str(item).strip() for item in value if str(item).strip()]

    return []


def count_papers(papers: Sequence[str] | str | None) -> dict:
    """
    Count the number of research papers and return both list and count.

    Returns:
        dict with keys `papers` (List[str]) and `count` (int).
    """
    normalized = _normalize_to_list(papers)
    return {"papers": normalized, "count": len(normalized)}


# Google Search agent
google_search_agent = LlmAgent(
    name="google_search_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    description="Searches for information using Google search",
    instruction="""Use the google_search tool to find information on the given topic.
Return ONLY JSON with key `papers` as a list of strings (titles or URLs).""",
    tools=[google_search],
)


# Root agent
root_agent = LlmAgent(
    name="research_paper_finder_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction="""Your task is to find research papers and count them.

You MUST ALWAYS follow these steps:
1) Use the 'google_search_agent' tool to collect papers about the topic.
2) Pass the tool output to 'count_papers' to produce the list and count.
3) Return ONLY the JSON produced by 'count_papers'. """,
    tools=[AgentTool(agent=google_search_agent), FunctionTool(func=count_papers)],
)
print("✅ Agent created")

from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ToolCallCountingPlugin import ToolCallCountingPlugin

import asyncio

async def main():
    runner = InMemoryRunner(
        agent=root_agent,
        plugins=[LoggingPlugin(), ToolCallCountingPlugin()],
    )

    print("✅ Runner configured")
    print("🚀 Running agent with LoggingPlugin...")
    print("📊 Watch the comprehensive logging output below:\n")

    # Debug helper is async; await to run and print events.
    await runner.run_debug("Find latest quantum computing papers", verbose=True)


if __name__ == "__main__":
    asyncio.run(main())