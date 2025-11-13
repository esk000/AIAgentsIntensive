import logging
from collections import defaultdict
from typing import Any, Optional

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext


class CountInvocationPlugin(BasePlugin):
    """A simple plugin that counts agent and LLM invocations globally."""

    def __init__(self) -> None:
        super().__init__(name="count_invocation")
        self.agent_count: int = 0
        self.llm_request_count: int = 0

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> Optional[None]:
        self.agent_count += 1
        logging.info(f"[count_invocation] Agent runs: {self.agent_count}")
        return None

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> Optional[None]:
        self.llm_request_count += 1
        logging.info(f"[count_invocation] LLM requests: {self.llm_request_count}")
        return None


class ToolCallCountingPlugin(BasePlugin):
    """Tracks and reports total number of tool calls made during a session.

    - Increments per-session count on every tool invocation.
    - Snapshots baseline at run start and reports delta at run end.
    """

    def __init__(self) -> None:
        super().__init__(name="tool_call_counter")
        # Cumulative counts per session
        self._session_tool_counts: dict[str, int] = defaultdict(int)
        # Baseline counts captured at the beginning of each runner invocation
        self._session_run_baseline: dict[str, int] = {}

    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> Optional[None]:
        session_id = invocation_context.session.id
        self._session_run_baseline[session_id] = self._session_tool_counts.get(session_id, 0)
        print(
            f"[tool_call_counter] Baseline for session '{session_id}': {self._session_run_baseline[session_id]}"
        )
        return None

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> Optional[dict]:
        # Increment per-session count
        session_id = tool_context._invocation_context.session.id
        self._session_tool_counts[session_id] += 1
        total = self._session_tool_counts[session_id]
        print(
            f"[tool_call_counter] Tool '{tool.name}' called. Session '{session_id}' total so far: {total}"
        )
        return None

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        session_id = invocation_context.session.id
        start = self._session_run_baseline.get(session_id, 0)
        end = self._session_tool_counts.get(session_id, 0)
        delta = max(end - start, 0)
        print(
            f"[tool_call_counter] Session '{session_id}' tool-call total this run: {delta} (cumulative: {end})"
        )
        