# Google ADK quick setup

This folder contains a small helper to set up your Gemini API key for local development with Google ADK.

## Prerequisites
- Python 3.9+
- `google-adk` installed (`python3 -m pip install --user google-adk`)

## Configure your API key
- Create a `.env` file in this directory containing:
  - `GOOGLE_API_KEY="YOUR_API_KEY"`

> Note: `.env` is ignored by Git via `.gitignore` to avoid leaking secrets.

## Run the setup
- `python3 setup_env.py`
  - Loads the key from the environment or `.env`
  - Falls back to Kaggle secrets if running on Kaggle
  - Sets `GOOGLE_GENAI_USE_VERTEXAI=FALSE` for API-key based access

If you plan to build an agent project using ADK, you can scaffold one next:
- `adk create my_agent`
- Put your `GOOGLE_API_KEY` in `my_agent/.env`
- Run your agent via `adk run my_agent` or launch the dev UI with `adk web --port 8000`

## Projects & Agents Directory

Explore the full list of projects and agents:

- Project Introduction (HTML): [public/index.html](https://github.com/esk000/AIAgentsIntensive/blob/main/public/index.html)
- Project Introduction (PDF): [index.pdf (Vercel)](https://ai-agents-intensive.vercel.app/index.pdf) or [index.pdf (GitHub)](https://github.com/esk000/AIAgentsIntensive/blob/main/public/index.pdf)

