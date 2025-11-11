import asyncio
import os
from typing import Any, Dict

from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.tools.tool_context import ToolContext
from google.genai import types

# Define scope levels for state keys (following best practices)
USER_NAME_SCOPE_LEVELS = ("temp", "user", "app")


# This demonstrates how tools can write to session state using tool_context.
# The 'user:' prefix indicates this is user-specific data.
def save_userinfo(
    tool_context: ToolContext, user_name: str, country: str
) -> Dict[str, Any]:
    """
    Tool to record and save user name and country in session state.

    Args:
        user_name: The username to store in session state
        country: The name of the user's country
    """
    # Write to session state using the 'user:' prefix for user data
    tool_context.state["user:name"] = user_name
    tool_context.state["user:country"] = country

    return {"status": "success"}


# This demonstrates how tools can read from session state.
def retrieve_userinfo(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Tool to retrieve user name and country from session state.
    """
    # Read from session state
    user_name = tool_context.state.get("user:name", "Username not found")
    country = tool_context.state.get("user:country", "Country not found")

    return {"status": "success", "user_name": user_name, "country": country}


print("✅ Tools created.")

# Configuration
APP_NAME = "default"
USER_ID = "default"
MODEL_NAME = "gemini-2.5-flash-lite"

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)


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


async def main() -> None:
    setup_gemini_env()

    # Clean up any existing database to start fresh (if Notebook is restarted)
    if os.path.exists("my_agent_data.db"):
        os.remove("my_agent_data.db")
    print("✅ Cleaned up old database files")

    # Create an agent with session state tools
    root_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="text_chat_bot",
        description="""A text chatbot.
        Tools for managing user context:
        * To record username and country when provided use `save_userinfo` tool. 
        * To fetch username and country when required use `retrieve_userinfo` tool.
        """,
        tools=[save_userinfo, retrieve_userinfo],  # Provide the tools to the agent
    )

    # Set up session service and runner
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)

    print("✅ Agent with session state tools initialized!")

    # Test conversation demonstrating session state
    await run_session(
        runner,
        [
            "Hi there, how are you doing today? What is my name?",
            "My name is Sam. I'm from Poland.",
            "What is my name? Which country am I from?",
        ],
        "state-demo-session",
    )

    # Retrieve the session and inspect its state
    session = await session_service.get_session(
    app_name=APP_NAME, user_id=USER_ID, session_id="state-demo-session"
    )

    print("Session State Contents:")
    print(session.state)
    print("\n🔍 Notice the 'user:name' and 'user:country' keys storing our data!")

    # Start a completely new session - the agent won't know our name
    await run_session(
        runner,
        ["Hi there, how are you doing today? What is my name?"],
        "new-isolated-session",
    )

    # Expected: The agent won't know the name because this is a different session
    print("\n🔍 Notice the 'user:name' and 'user:country' keys are empty in this new session!")

    # Cross-Session State Sharing¶
    # Check the state of the new session
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id="new-isolated-session"
    )

    print("New Session State:")
    print(session.state)

    # Note: Depending on implementation, you might see shared state here.
    # This is where the distinction between session-specific and user-specific state becomes important.

if __name__ == "__main__":
    asyncio.run(main())