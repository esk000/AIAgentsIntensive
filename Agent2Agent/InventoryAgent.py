import uvicorn
from typing import Dict, Any

from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from Agent2Agent.a2a_auth import attach_auth_middleware


def get_stock_info(product_name: str) -> Dict[str, Any]:
    name = product_name.strip().lower()
    inventory = {
        "iphone 15 pro": {
            "available": True,
            "units": 28,
            "restock": None,
        },
        "macbook pro 14": {
            "available": True,
            "units": 22,
            "restock": None,
        },
        "dell xps 15": {
            "available": True,
            "units": 45,
            "restock": None,
        },
        "lg ultrawide 34": {
            "available": False,
            "units": 0,
            "restock": "Next Friday",
        },
        "sony wh-1000xm5": {
            "available": True,
            "units": 67,
            "restock": None,
        },
    }
    return inventory.get(name, {
        "available": False,
        "units": 0,
        "restock": "Unknown",
    })


def main():
    setup_gemini_env()

    retry_config = types.HttpRetryOptions(
        attempts=5,
        exp_base=7,
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504],
    )

    inventory_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
        name="inventory_agent",
        description="Provides stock levels and restocking schedules.",
        instruction=(
            "Use get_stock_info to answer questions about availability and restocking."
        ),
        tools=[get_stock_info],
    )

    inventory_a2a_app = to_a2a(inventory_agent, port=8003)
    attach_auth_middleware(inventory_a2a_app)

    print("✅ Inventory Agent is now A2A-compatible!")
    print("   Agent will be served at: http://localhost:8003")
    print("   Agent card will be at: http://localhost:8003/.well-known/agent-card.json")
    print("🚀 Inventory Agent A2A server starting...")
    uvicorn.run(inventory_a2a_app, host="0.0.0.0", port=8003)


if __name__ == "__main__":
    main()