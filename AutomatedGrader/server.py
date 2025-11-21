import os
import asyncio
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from AutomatedGrader.orchestrator import AutomatedGraderOrchestrator


app = FastAPI(title="AutomatedGrader API", version="0.1.0")

# CORS configuration - restrict origins in production
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:8080,http://localhost:3000,http://127.0.0.1:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def _cleanup_temp_files(older_than_hours: int = 24):
    """Remove temporary files older than specified hours."""
    import time
    
    tmp_dir = "AutomatedGrader/tmp"
    if not os.path.exists(tmp_dir):
        return
    
    now = time.time()
    cutoff = now - (older_than_hours * 3600)
    
    for filename in os.listdir(tmp_dir):
        filepath = os.path.join(tmp_dir, filename)
        try:
            if os.path.isfile(filepath) and os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
        except Exception:
            pass  # Skip files we can't remove


@app.post("/grade")
async def grade_endpoint(
    text: Optional[str] = Form(None),
    rubric: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    os.makedirs("AutomatedGrader/tmp", exist_ok=True)
    
    # Cleanup old temp files on each request
    _cleanup_temp_files(older_than_hours=24)

    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide either text or file")

    input_path = None
    temp_file_created = None
    
    try:
        if file is not None:
            suffix = os.path.splitext(file.filename or "uploaded")[1] or ".bin"
            input_path = os.path.join("AutomatedGrader/tmp", f"upload_{os.urandom(8).hex()}{suffix}")
            temp_file_created = input_path
            with open(input_path, "wb") as out:
                out.write(await file.read())
        elif text:
            input_path = os.path.join("AutomatedGrader/tmp", f"input_{os.urandom(8).hex()}.txt")
            temp_file_created = input_path
            with open(input_path, "w", encoding="utf-8") as out:
                out.write(text)

        orchestrator = AutomatedGraderOrchestrator()
        result = await orchestrator.run(input_path, rubric=rubric)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"grading_failed: {e}")
    finally:
        # Clean up the temp file immediately after processing
        if temp_file_created and os.path.exists(temp_file_created):
            try:
                os.remove(temp_file_created)
            except Exception:
                pass  # Best effort cleanup
@app.get("/health")
async def health():
    return {"ok": True}