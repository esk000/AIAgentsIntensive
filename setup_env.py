import os
from typing import Optional


def _load_from_env_file() -> None:
    """Load environment variables from a local .env file if present."""
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        # dotenv is optional; continue if not available
        pass


def _get_api_key() -> Optional[str]:
    """Return GOOGLE_API_KEY from environment, .env, or Kaggle secrets if available."""
    # 1) Environment variable (possibly loaded from .env)
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return key

    # 2) Try Kaggle secrets (works only on Kaggle notebooks)
    try:
        from kaggle_secrets import UserSecretsClient  # type: ignore

        key = UserSecretsClient().get_secret("GOOGLE_API_KEY")
        if key:
            return key
    except Exception:
        pass

    return None


def setup_gemini_env() -> bool:
    """Set required environment variables for Gemini/ADK usage.

    - Ensures `GOOGLE_API_KEY` is available
    - Sets `GOOGLE_GENAI_USE_VERTEXAI` to "FALSE" (Express mode / API key usage)
    """
    _load_from_env_file()

    api_key = _get_api_key()
    if not api_key:
        print(
            "🔑 Authentication Error: GOOGLE_API_KEY not found.\n"
            "Add it to your environment or a local .env file, or Kaggle secrets."
        )
        return False

    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    print("✅ Gemini API key setup complete.")
    return True


if __name__ == "__main__":
    setup_gemini_env()