import os
import asyncio
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from AutomatedGrader.orchestrator import AutomatedGraderOrchestrator


app = FastAPI(title="AutomatedGrader API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "*"],  # local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/grade")
async def grade_endpoint(
    text: Optional[str] = Form(None),
    rubric: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    os.makedirs("AutomatedGrader/tmp", exist_ok=True)

    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide either text or file")

    input_path = None
    if file is not None:
        suffix = os.path.splitext(file.filename or "uploaded")[1] or ".bin"
        input_path = os.path.join("AutomatedGrader/tmp", f"upload{suffix}")
        with open(input_path, "wb") as out:
            out.write(await file.read())
    elif text:
        input_path = os.path.join("AutomatedGrader/tmp", "input.txt")
        with open(input_path, "w", encoding="utf-8") as out:
            out.write(text)

    try:
        orchestrator = AutomatedGraderOrchestrator()
        result = await orchestrator.run(input_path, rubric=rubric)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"grading_failed: {e}")