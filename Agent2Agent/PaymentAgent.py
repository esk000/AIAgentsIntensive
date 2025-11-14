import os
import uvicorn
from typing import Dict, Any

import stripe

from setup_env import setup_gemini_env
from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types
from Agent2Agent.a2a_auth import attach_auth_middleware


def _init_stripe() -> None:
    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "STRIPE_API_KEY not set. Please export a Stripe test secret key (sk_test_...)."
        )
    stripe.api_key = api_key
    # Improve network resilience for Stripe calls
    try:
        stripe.max_network_retries = int(os.getenv("STRIPE_MAX_NETWORK_RETRIES", "3"))
    except Exception:
        stripe.max_network_retries = 3


def create_payment_intent(amount_usd: float, customer_email: str) -> Dict[str, Any]:
    """
    Create a Stripe PaymentIntent in test mode.
    Returns payment intent id and client secret.
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(round(amount_usd * 100)),
            currency="usd",
            receipt_email=customer_email,
            description="ADK Agent order",
            payment_method_types=["card"],
        )
        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
        }
    except Exception as e:
        return {"error": str(e), "status": "error", "stage": "create_payment_intent"}


def confirm_payment_intent(payment_intent_id: str) -> Dict[str, Any]:
    """
    Confirm the PaymentIntent using a Stripe test card.
    Uses payment method 'pm_card_visa' in test mode.
    """
    try:
        intent = stripe.PaymentIntent.confirm(
            payment_intent_id, payment_method="pm_card_visa"
        )
        return {"id": intent.id, "status": intent.status}
    except Exception as e:
        return {"error": str(e), "status": "error", "stage": "confirm_payment_intent"}


def refund_payment(payment_intent_id: str) -> Dict[str, Any]:
    """
    Issue a refund for a completed PaymentIntent.
    """
    try:
        refund = stripe.Refund.create(payment_intent=payment_intent_id)
        return {"id": refund.id, "status": refund.status}
    except Exception as e:
        return {"error": str(e), "status": "error", "stage": "refund_payment"}


def main():
    setup_gemini_env()
    _init_stripe()

    retry_options = types.HttpRetryOptions(
        attempts=5,
        exp_base=7,
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504],
    )

    payment_agent = LlmAgent(
        model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_options),
        name="payment_agent",
        description="Handles payment processing using Stripe test mode (create, confirm, refund).",
        instruction=(
            "Use create_payment_intent to start checkout, confirm_payment_intent to capture, "
            "and refund_payment for refunds. Always summarize results clearly."
        ),
        tools=[create_payment_intent, confirm_payment_intent, refund_payment],
    )

    payment_a2a_app = to_a2a(payment_agent, port=8005)
    attach_auth_middleware(payment_a2a_app)

    print("✅ Payment Agent is now A2A-compatible!")
    print("   Agent will be served at: http://localhost:8005")
    print("   Agent card will be at: http://localhost:8005/.well-known/agent-card.json")
    print("🚀 Payment Agent A2A server starting...")
    uvicorn.run(payment_a2a_app, host="0.0.0.0", port=8005)


if __name__ == "__main__":
    main()