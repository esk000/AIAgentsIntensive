import asyncio

from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from google.genai import types


APP_NAME = "research_app_compacting"
USER_ID = "default"

def confirm_api_setup():
    setup_gemini_env()
    print("✅ Gemini API key setup complete.")


async def run_session(runner: Runner, user_query: str, session_name: str):
    # Ensure session exists
    try:
        session = await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_name
        )
    except Exception:
        session = await runner.session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_name
        )

    print("\nUser >", user_query)
    content = types.Content(role="user", parts=[types.Part(text=user_query)])
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts and event.content.parts[0].text:
            print("Agent >", event.content.parts[0].text)


SESSION_NAME = "compaction_demo_04"

async def main():
    confirm_api_setup()

    chatbot_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", section="text_chat_bot"),
        name="research_bot",
        description="A research chatbot with events compaction",
    )

    # Re-define our app with Events Compaction enabled
    research_app_compacting = App(
        name=APP_NAME,
        root_agent=chatbot_agent,
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=3,  # Trigger compaction every 3 invocations
            overlap_size=1,  # Keep 1 previous turn for context
        ),
    )

    db_url = "sqlite:///my_agent_data.db"  # Local SQLite file
    session_service = DatabaseSessionService(db_url=db_url)

    # Create a new runner for our upgraded app
    research_runner_compacting = Runner(
        app=research_app_compacting, session_service=session_service
    )

    print("✅ Research App upgraded with Events Compaction!")

    # Turn 1
    await run_session(
        research_runner_compacting,
        "What is the latest news about AI in healthcare?",
        SESSION_NAME,
    )

    # Turn 2
    await run_session(
        research_runner_compacting,
        "Are there any new developments in drug discovery?",
        SESSION_NAME,
    )

    # Turn 3 - Compaction should trigger after this turn!
    await run_session(
        research_runner_compacting,
        "Tell me more about the second development you found.",
        SESSION_NAME,
    )

    # Turn 4
    await run_session(
        research_runner_compacting,
        "Who are the main companies involved in that?",
        SESSION_NAME,
    )

    # Verify compaction event exists in the session
    final_session = await session_service.get_session(
        app_name=research_runner_compacting.app_name,
        user_id=USER_ID,
        session_id=SESSION_NAME,
    )

    print("--- Searching for Compaction Summary Event ---")
    found_summary = False
    for event in final_session.events:
        if event.actions and event.actions.compaction:
            print("\n✅ SUCCESS! Found the Compaction Event:")
            print(f"  Author: {event.author}")

            compaction = event.actions.compaction
            compacted = None
            summary_text = None

            # Handle both typed object and dict representations
            if isinstance(compaction, dict):
                compacted = compaction.get("compacted_content")
                if compacted and isinstance(compacted, dict):
                    parts = compacted.get("parts") or []
                    if parts:
                        first = parts[0]
                        if isinstance(first, dict):
                            summary_text = first.get("text")
            else:
                compacted = compaction.compacted_content
                if compacted and compacted.parts:
                    summary_text = compacted.parts[0].text

            if summary_text:
                print(f"  Summary: {summary_text}")
            else:
                print("  Summary parts unavailable.")
            found_summary = True
            break

    if not found_summary:
        print(
            "\n❌ No compaction event found. Try increasing the number of turns in the demo."
        )


if __name__ == "__main__":
    asyncio.run(main())