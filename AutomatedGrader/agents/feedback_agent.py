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


def create_feedback_agent() -> LlmAgent:
    """Build an LLM agent specialized for constructive feedback and sources.

    The agent suggests structure improvements, sources to consult, and style
    enhancements tailored to the observed weaknesses.
    """
    return LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="FeedbackAgent",
        instruction=(
            "You provide constructive feedback on student writing. Respond with JSON "
            "fields: suggestions (list of strings), sources (list of URLs or citations), "
            "style (list of concise style improvements). Keep it practical and kind."
        ),
    )


def create_feedback_app() -> App:
    """Build an App wrapping the feedback agent."""
    return App(
        name="FeedbackApp",
        root_agent=create_feedback_agent()
    )