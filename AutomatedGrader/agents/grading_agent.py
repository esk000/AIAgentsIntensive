from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.apps.app import App
from google.genai import types


retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)


def create_grading_agent() -> LlmAgent:
    """Build an LLM agent specialized for rubric-based grading.

    Output format is a concise JSON covering scores per criterion,
    justification, and overall grade.
    """
    return LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="GradingAgent",
        instruction=(
            "You are a strict but fair grader. Given student text and a rubric, "
            "return JSON with fields: overall_score (0-100), criteria (list of {name,score,notes}), "
            "and notes (brief and constructive). Be specific and point to evidence."
        ),
    )


def create_grading_app() -> App:
    """Build an App wrapping the grading agent."""
    return App(
        name="GradingApp",
        root_agent=create_grading_agent()
    )