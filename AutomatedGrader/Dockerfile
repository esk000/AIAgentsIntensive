FROM python:3.11-slim

# System deps for OCR (optional) and builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY AutomatedGrader/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Runtime env
ENV AI_DETECT_STRICT=true

# Expose and run
# Use the platform-provided PORT if available; default to 8080 locally
EXPOSE 8080
CMD ["sh", "-c", "uvicorn AutomatedGrader.server:app --host 0.0.0.0 --port ${PORT:-8080}"]