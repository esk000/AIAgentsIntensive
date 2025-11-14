from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types
from Agent2Agent.RemoteA2aAgent import (
    remote_product_catalog_agent,
    remote_inventory_agent,
    remote_shipping_agent,
    remote_payment_agent,
)
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
import asyncio
import uuid

# Ensure Gemini/ADK environment is configured
setup_gemini_env()

# Retry configuration for network robustness
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

# Now create the Customer Support Agent that uses the remote Product Catalog Agent
customer_support_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="customer_support_agent",
    description="A customer support assistant that helps customers with product inquiries and information.",
    instruction="""
    You are a friendly and professional customer support agent.
    
    Routing guidance:
    - Use product_catalog_agent to look up product information and specs.
    - Use inventory_agent to check stock levels and restocking schedules.
    - Use shipping_agent to provide delivery estimates and tracking updates.
    - Use payment_agent to create/confirm payments and process refunds.
    
    Always fetch authoritative data from the relevant sub-agent before answering.
    Be clear, helpful, and professional.
    """,
    sub_agents=[
        remote_product_catalog_agent,
        remote_inventory_agent,
        remote_shipping_agent,
        remote_payment_agent,
    ],
)

print("✅ Customer Support Agent created!")
print("   Model: gemini-2.5-flash-lite")
print("   Sub-agents: 3 (catalog, inventory, shipping via A2A)")
print("   Sub-agents: 4 (catalog, inventory, shipping, payments via A2A)")
print("   Ready to help customers!")


async def test_a2a_communication(user_query: str):
    """
    Test the A2A communication between Customer Support Agent and Product Catalog Agent.

    This function:
    1. Creates a new session for this conversation
    2. Sends the query to the Customer Support Agent
    3. Support Agent communicates with Product Catalog Agent via A2A
    4. Displays the response

    Args:
        user_query: The question to ask the Customer Support Agent
    """
    # Setup session management (required by ADK)
    session_service = InMemorySessionService()

    # Session identifiers
    app_name = "support_app"
    user_id = "demo_user"
    # Use unique session ID for each test to avoid conflicts
    session_id = f"demo_session_{uuid.uuid4().hex[:8]}"

    # CRITICAL: Create session BEFORE running agent (synchronous, not async!)
    # This pattern matches the deployment notebook exactly
    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    # Create runner for the Customer Support Agent
    # The runner manages the agent execution and session state
    runner = Runner(
        agent=customer_support_agent, app_name=app_name, session_service=session_service
    )

    # Create the user message
    # This follows the same pattern as the deployment notebook
    test_content = types.Content(parts=[types.Part(text=user_query)])

    # Display query
    print(f"\n👤 Customer: {user_query}")
    print(f"\n🎧 Support Agent response:")
    print("-" * 60)

    # Run the agent asynchronously (handles streaming responses and A2A communication)
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=test_content
    ):
        # Print final response only (skip intermediate events)
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, "text"):
                    print(part.text)

    print("-" * 60)


# Run the test
async def _run_tests():
    print("🧪 Testing A2A Communication...\n")
    await test_a2a_communication(
        "Can you tell me about the iPhone 15 Pro? Is it in stock?"
    )
    await test_a2a_communication(
        "I'm looking for a laptop. Can you compare the Dell XPS 15 and MacBook Pro 14 for me?"
    )
    await test_a2a_communication(
        "Do you have the Sony WH-1000XM5 headphones? What's the price?"
    )
    # Inventory-focused query
    await test_a2a_communication(
        "Is the LG UltraWide 34 in stock? If not, when will it restock?"
    )
    # Shipping estimate
    await test_a2a_communication(
        "What's the delivery estimate and shipping cost to ZIP 94043?"
    )
    # Tracking update
    await test_a2a_communication(
        "Can you check tracking on 1Z999AA10123456784?"
    )
    # Payment end-to-end (Stripe test mode)
    await test_a2a_communication(
        "Create a Stripe test payment intent for $12.34 with receipt to john.doe+test@example.com, then confirm it using a test card and finally refund it. Report the payment_intent id, each status, and any client_secret if applicable."
    )

if __name__ == "__main__":
    asyncio.run(_run_tests())