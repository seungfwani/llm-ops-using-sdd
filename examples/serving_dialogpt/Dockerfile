FROM huggingface/transformers-pytorch-cpu

# Example HTTP server for microsoft/DialoGPT-small using FastAPI + Uvicorn.
# This image is intended as a reference serving runtime image that can be
# plugged into the llm-ops platform as `servingRuntimeImage`.

WORKDIR /app

# Ensure UTF-8 locale so Click/uvicorn do not crash with ASCII encoding
ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Install minimal server and S3 client dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] boto3

# Copy example serving code
COPY serve_dialogpt.py /app/serve_dialogpt.py

# Expose default serving port expected by the platform (8000)
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "serve_dialogpt:app", "--host", "0.0.0.0", "--port", "8000"]


