import asyncio
from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import preload_memory
from google.genai import types

print("✅ ADK components imported successfully.")

async def run_session(
    runner_instance: Runner,
    session_service: InMemorySessionService,
    user_queries: list[str] | str,
    session_id: str = "default",
):
    print(f"\n### Session: {session_id}")

    # Create or retrieve session
    try:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
    except:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )

    # Normalize queries
    if isinstance(user_queries, str):
        user_queries = [user_queries]

    for query in user_queries:
        print(f"\nUser > {query}")
        query_content = types.Content(role="user", parts=[types.Part(text=query)])

        async for event in runner_instance.run_async(
            user_id=USER_ID, session_id=session.id, new_message=query_content
        ):
            if not event.content:
                continue
            if event.is_final_response() and event.content.parts:
                text_parts = [p.text for p in event.content.parts if getattr(p, "text", None)]
                combined = "\n".join([t for t in text_parts if t and t != "None"])
                if combined:
                    print(f"Model: > {combined}")

print("✅ Helper functions defined.")

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

APP_NAME = "MemoryCallbackDemo"
USER_ID = "demo_user"

async def auto_save_to_memory(callback_context):
    """Automatically save session to memory after each agent turn."""
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )

print("✅ Callback created.")

async def main() -> None:
    setup_gemini_env()
    print("✅ Gemini API key setup complete.")

    # Services
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

    # Agent with automatic memory saving
    auto_memory_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="AutoMemoryAgent",
        instruction="Answer user questions.",
        tools=[preload_memory],
        after_agent_callback=auto_save_to_memory,  # Saves after each turn!
    )

    print("✅ Agent created with automatic memory saving!")

    # Runner
    auto_runner = Runner(
        agent=auto_memory_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )

    print("✅ Runner created.")

    # Test 1: Tell the agent about a gift (first conversation)
    await run_session(
        auto_runner,
        session_service,
        "I gifted a new toy to my nephew on his 1st birthday!",
        "auto-save-test",
    )

    # Test 2: Ask about the gift in a NEW session (second conversation)
    await run_session(
        auto_runner,
        session_service,
        "What did I gift my nephew?",
        "auto-save-test-2",
    )

if __name__ == "__main__":
    asyncio.run(main())