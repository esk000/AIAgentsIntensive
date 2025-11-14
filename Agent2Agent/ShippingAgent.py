import uvicorn
from typing import Dict, Any

from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from Agent2Agent.a2a_auth import attach_auth_middleware


def get_delivery_estimate(destination_zip: str) -> Dict[str, Any]:
    zip_code = destination_zip.strip()
    # Simple heuristic demo
    if zip_code.startswith("9"):
        return {"eta_days": 2, "method": "Express", "cost_usd": 19.99}
    if zip_code.startswith("1"):
        return {"eta_days": 4, "method": "Ground", "cost_usd": 14.99}
    return {"eta_days": 3, "method": "Standard", "cost_usd": 16.99}


def get_tracking_status(tracking_number: str) -> Dict[str, Any]:
    tn = tracking_number.strip().upper()
    # Demo data
    tracking_db = {
        "1Z999AA10123456784": {
            "status": "In transit",
            "last_location": "Memphis, TN hub",
            "eta": "2 days",
        },
        "9400111899223856921456": {
            "status": "Out for delivery",
            "last_location": "Mountain View, CA",
            "eta": "Today",
        },
    }
    return tracking_db.get(tn, {
        "status": "Unknown",
        "last_location": "Unknown",
        "eta": "Unknown",
    })


def main():
    setup_gemini_env()

    retry_config = types.HttpRetryOptions(
        attempts=5,
        exp_base=7,
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504],
    )

    shipping_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="shipping_agent",
        description="Provides delivery estimates and shipment tracking updates.",
        instruction=(
            "Use get_delivery_estimate and get_tracking_status to answer shipping questions."
        ),
        tools=[get_delivery_estimate, get_tracking_status],
    )

    shipping_a2a_app = to_a2a(shipping_agent, port=8004)
    attach_auth_middleware(shipping_a2a_app)

    print("✅ Shipping Agent is now A2A-compatible!")
    print("   Agent will be served at: http://localhost:8004")
    print("   Agent card will be at: http://localhost:8004/.well-known/agent-card.json")
    print("🚀 Shipping Agent A2A server starting...")
    uvicorn.run(shipping_a2a_app, host="0.0.0.0", port=8004)


if __name__ == "__main__":
    main()