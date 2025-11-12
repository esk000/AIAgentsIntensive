import asyncio
from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import load_memory, preload_memory
from google.genai import types

print("✅ ADK components imported successfully.")

async def run_session(
    runner_instance: Runner,
    session_service: InMemorySessionService,
    user_queries: list[str] | str,
    session_id: str = "default",
):
    """Helper function to run queries in a session and display responses."""
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

    # Convert single query to list
    if isinstance(user_queries, str):
        user_queries = [user_queries]

    # Process each query
    for query in user_queries:
        print(f"\nUser > {query}")
        query_content = types.Content(role="user", parts=[types.Part(text=query)])

        # Stream agent response
        async for event in runner_instance.run_async(
            user_id=USER_ID, session_id=session.id, new_message=query_content
        ):
            if not event.content:
                continue

            # Print any text parts in the final response
            if event.is_final_response() and event.content.parts:
                text_parts = []
                func_calls = []
                for part in event.content.parts:
                    # Capture text parts
                    if getattr(part, "text", None):
                        text_parts.append(part.text)
                    # Capture function/tool call parts
                    fc = getattr(part, "function_call", None)
                    if fc:
                        func_calls.append(fc)

                if text_parts:
                    combined = "\n".join([t for t in text_parts if t and t != "None"])
                    if combined:
                        print(f"Model: > {combined}")

                # Log function calls for transparency when there are non-text parts
                if func_calls:
                    try:
                        for call in func_calls:
                            name = getattr(call, "name", "<unknown>")
                            args = getattr(call, "args", {})
                            print(
                                "Tool call detected:",
                                f"name={name}",
                                f"args={args}",
                            )
                    except Exception:
                        print("Tool call detected (details unavailable)")


print("✅ Helper functions defined.")
retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

# Three-step integration process:
# Initialize → Create a MemoryService and provide it to your agent via the Runner
# Ingest → Transfer session data to memory using add_session_to_memory()
# Retrieve → Search stored memories using search_memory()

memory_service = (
    InMemoryMemoryService()
)  # ADK's built-in Memory Service for development and testing

# Define constants used throughout the notebook
APP_NAME = "MemoryDemoApp"
USER_ID = "demo_user"

# Create agent
user_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="MemoryDemoAgent",
    instruction="Answer user questions in simple words.",
)

print("✅ Agent created")

async def main() -> None:
    # Set up API key / environment
    setup_gemini_env()
    print("✅ Gemini API key setup complete.")
    # Create Session Service
    session_service = InMemorySessionService()  # Handles conversations

    # Create runner with BOTH services
    runner = Runner(
        agent=user_agent,
        app_name="MemoryDemoApp",
        session_service=session_service,
        memory_service=memory_service,  # Memory service is now available!
    )

    print("✅ Agent and Runner created with memory support!")

    # User tells agent about their favorite color
    await run_session(
        runner,
        session_service,
        "My favorite color is blue-green. Can you write a Haiku about it?",
        "conversation-01",  # Session ID
    )

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id="conversation-01"
    )

    # Let's see what's in the session
    print("📝 Session contains:")
    for event in session.events:
        text = (
            event.content.parts[0].text[:60]
            if event.content and event.content.parts
            else "(empty)"
        )
        print(f"  {event.content.role}: {text}...")

    # This is the key method!
    await memory_service.add_session_to_memory(session)

    print("✅ Session added to memory!")

    # Upgrade agent to include load_memory tool
    memory_enabled_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="MemoryDemoAgent",
        instruction="Answer user questions in simple words. Use load_memory tool if you need to recall past conversations.",
        tools=[load_memory],
    )
    print("✅ Agent with load_memory tool created.")

    # Create a new runner with the updated agent
    runner_with_memory = Runner(
        agent=memory_enabled_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )

    await run_session(
        runner_with_memory,
        session_service,
        "What is my favorite color?",
        "color-test",
    )

    await run_session(
        runner_with_memory,
        session_service,
        "My birthday is on March 15th.",
        "birthday-session-01",
    )

    # Manually save the session to memory
    birthday_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id="birthday-session-01"
    )

    await memory_service.add_session_to_memory(birthday_session)

    print("✅ Birthday session saved to memory!")

    # Test retrieval in a NEW session
    await run_session(
        runner_with_memory,
        session_service,
        "When is my birthday?",
        "birthday-session-02",  # Different session ID
    )

    # Alternative: agent using preload_memory tool
    #(proactive): Automatically loads memory before every turn
    preload_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="MemoryPreloadAgent",
        instruction="Answer user questions in simple words. Use preload_memory to store info.",
        tools=[preload_memory],
    )
    print("✅ Agent with preload_memory tool created.")

    runner_with_preload = Runner(
        agent=preload_agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service,
    )

    await run_session(
        runner_with_preload,
        session_service,
        "Please remember that my timezone is PST.",
        "preload-session-01",
    )

    # Ingest the preload session so the fact is persisted to memory
    preload_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id="preload-session-01"
    )
    await memory_service.add_session_to_memory(preload_session)
    print("✅ Preload session saved to memory!")

    await run_session(
        runner_with_preload,
        session_service,
        "What time zone do I use?",
        "preload-session-02",
    )

    # Test runner_with_preload behavior in a new session
    await run_session(
        runner_with_preload,
        session_service,
        "What is my favorite color?",
        "preload-color-test",
    )

    # Follow-up turn in the same session; preload_memory will still run
    await run_session(
        runner_with_preload,
        session_service,
        "Tell me a joke",
        "preload-color-test",
    )

    # Search for color preferences
    search_response = await memory_service.search_memory(
        app_name=APP_NAME, user_id=USER_ID, query="What is the user's favorite color?"
    )

    print("🔍 Search Results:")
    print(f"  Found {len(search_response.memories)} relevant memories")
    print()

    for memory in search_response.memories:
        if memory.content and memory.content.parts:
            text = memory.content.parts[0].text[:80]
            print(f"  [{memory.author}]: {text}...")

    # Additional keyword search tests to observe matching behavior
    queries = [
        "what color does the user like",
        "haiku",
        "age",
        "preferred hue",
    ]
    print()
    for q in queries:
        print(f"### Keyword Search: {q}")
        resp = await memory_service.search_memory(
            app_name=APP_NAME, user_id=USER_ID, query=q
        )
        print(f"  Found {len(resp.memories)} relevant memories")
        for mem in resp.memories:
            if mem.content and mem.content.parts:
                snippet = mem.content.parts[0].text[:80]
                print(f"  [{mem.author}]: {snippet}...")
        print()
    
if __name__ == "__main__":
    asyncio.run(main())