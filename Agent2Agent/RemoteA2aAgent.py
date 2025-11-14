import os
from typing import Dict

import httpx

from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)


def _build_auth_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    api_key = os.getenv("A2A_API_KEY")
    bearer = os.getenv("A2A_BEARER_TOKEN")
    if api_key:
        headers["X-A2A-API-Key"] = api_key
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _build_httpx_client() -> httpx.AsyncClient:
    timeout = float(os.getenv("A2A_HTTP_TIMEOUT", "30"))
    headers = _build_auth_headers()
    # Note: httpx does not provide built-in retries; ADK handles some errors.
    # We configure sane timeouts and default headers for auth.
    return httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True)

# Create a RemoteA2aAgent that connects to our Product Catalog Agent
# This acts as a client-side proxy - the Customer Support Agent can use it like a local agent
PRODUCT_CATALOG_AGENT_CARD_URL = os.getenv(
    "PRODUCT_CATALOG_AGENT_CARD_URL",
    "https://ai-agents-intensive.vercel.app/.well-known/agent-card.json",
)

remote_product_catalog_agent = RemoteA2aAgent(
    name="product_catalog_agent",
    description="Remote product catalog agent from external vendor that provides product information.",
    # Point to the agent card URL - this is where the A2A protocol metadata lives
    agent_card=PRODUCT_CATALOG_AGENT_CARD_URL,
    httpx_client=_build_httpx_client(),
)

print("✅ Remote Product Catalog Agent proxy created!")
print(f"   Agent card: {PRODUCT_CATALOG_AGENT_CARD_URL}")
print("   The Customer Support Agent can now use this like a local sub-agent!")

# Create a RemoteA2aAgent that connects to our Inventory Agent
remote_inventory_agent = RemoteA2aAgent(
    name="inventory_agent",
    description="Remote inventory agent that provides stock levels and restocking schedules.",
    agent_card=f"http://localhost:8003{AGENT_CARD_WELL_KNOWN_PATH}",
    httpx_client=_build_httpx_client(),
)

print("✅ Remote Inventory Agent proxy created!")
print(f"   Connected to: http://localhost:8003")
print(f"   Agent card: http://localhost:8003{AGENT_CARD_WELL_KNOWN_PATH}")

# Create a RemoteA2aAgent that connects to our Shipping Agent
remote_shipping_agent = RemoteA2aAgent(
    name="shipping_agent",
    description="Remote shipping agent that provides delivery estimates and tracking.",
    agent_card=f"http://localhost:8004{AGENT_CARD_WELL_KNOWN_PATH}",
    httpx_client=_build_httpx_client(),
)

print("✅ Remote Shipping Agent proxy created!")
print(f"   Connected to: http://localhost:8004")
print(f"   Agent card: http://localhost:8004{AGENT_CARD_WELL_KNOWN_PATH}")

# Create a RemoteA2aAgent that connects to our Payment Agent
remote_payment_agent = RemoteA2aAgent(
    name="payment_agent",
    description="Remote payment agent that handles Stripe payments (test mode).",
    agent_card=f"http://localhost:8005{AGENT_CARD_WELL_KNOWN_PATH}",
    httpx_client=_build_httpx_client(),
)

print("✅ Remote Payment Agent proxy created!")
print(f"   Connected to: http://localhost:8005")
print(f"   Agent card: http://localhost:8005{AGENT_CARD_WELL_KNOWN_PATH}")
