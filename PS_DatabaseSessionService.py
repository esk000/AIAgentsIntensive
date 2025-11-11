import asyncio

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from google.genai import types
from setup_env import setup_gemini_env

import sqlite3

setup_ready = setup_gemini_env()
if not setup_ready:
    raise RuntimeError("GOOGLE_API_KEY is not set. Populate .env or environment.")

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

APP_NAME = "default"
USER_ID = "default"

async def run_session(runner_instance: Runner, user_queries: list[str] | str, session_name: str) -> None:
    print(f"\n ### Session: {session_name}")

    # Ensure list
    if isinstance(user_queries, str):
        user_queries = [user_queries]

    # Create or get session
    try:
        session = await runner_instance.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_name
        )
    except Exception:
        session = await runner_instance.session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_name
        )

    for query in user_queries:
        print(f"\nUser > {query}")
        content = types.Content(role="user", parts=[types.Part(text=query)])
        async for event in runner_instance.run_async(
            user_id=USER_ID, session_id=session.id, new_message=content
        ):
            if event.content and event.content.parts and event.content.parts[0].text:
                print("Agent > ", event.content.parts[0].text)

def build_runner() -> Runner:
    chatbot_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="text_chat_bot",
        description="A text chatbot with persistent memory",
    )

    db_url = "sqlite:///my_agent_data.db"
    session_service = DatabaseSessionService(db_url=db_url)

    runner = Runner(agent=chatbot_agent, app_name=APP_NAME, session_service=session_service)
    print("✅ Upgraded to persistent sessions!")
    print("   - Database: my_agent_data.db")
    print("   - Sessions will survive restarts!")
    return runner

def check_data_in_db():
    with sqlite3.connect("my_agent_data.db") as connection:
        cursor = connection.cursor()
        result = cursor.execute(
            "select app_name, session_id, author, content from events"
        )
        print([_[0] for _ in result.description])
        for each in result.fetchall():
            print(each)

async def main() -> None:
    runner = build_runner()
    await run_session(
        runner,
        [
            "Hi, I am Sam! What is the capital of the United States?",
            "Hello! What is my name?",
        ],
        "test-db-session-01",
    )

    await run_session(
    runner,
    ["What is the capital of India?", "Hello! What is my name?"],
    "test-db-session-01",
    )


if __name__ == "__main__":
    asyncio.run(main())
    check_data_in_db()