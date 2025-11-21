# Google ADK quick setup

Author: Erum Saba

## Automated Homework/Test Grader & Feedback Agent

- Input: image or PDF of test sheet or student writing.
- Outputs: rubric-based grade, plagiarism analysis, AI-generated text risk, and constructive feedback with sources.
- Concepts demonstrated: multi-agent (sequential + parallel), custom tools, sessions & memory, context engineering, observability, and long-running pause/resume.

### Run Locally
- Install optional parsers: `pip install pypdf pillow pytesseract duckduckgo-search`
- Configure Gemini API key: `export GOOGLE_API_KEY=...`
- Execute: `python -m AutomatedGrader.orchestrator /path/to/input.pdf --rubric "Clarity, accuracy, structure, evidence"`
- Output report: `AutomatedGrader/output/latest_report.json`

### Architecture
- Ingestion: `AutomatedGrader/ingestion.py` extracts text from PDF/images with fallbacks.
- Analysis (parallel): `AutomatedGrader/tools/plagiarism.py` + `AutomatedGrader/tools/ai_detection.py`.
- Grading Agent: `AutomatedGrader/agents/grading_agent.py` (LLM, sessions & memory).
- Feedback Agent: `AutomatedGrader/agents/feedback_agent.py` (LLM feedback, sources, style).
- Orchestrator: `AutomatedGrader/orchestrator.py` combines stages, supports pause/resume.

### Notes
- Web search uses DuckDuckGo if available; otherwise, confidence is limited.
- Observability logging initializes via `AgentObservability`.
- Memory persists within the process; upgrade to database-backed sessions via `PS_DatabaseSessionService.py` if needed.

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

- Project Introduction (HTML): [index.html](https://ai-agents-intensive.vercel.app/index.html)
- Project Introduction (PDF): [index.pdf (GitHub)](https://github.com/esk000/AIAgentsIntensive/blob/main/public/index.pdf)

