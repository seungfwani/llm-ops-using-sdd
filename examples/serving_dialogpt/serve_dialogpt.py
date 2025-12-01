from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Optional
import time
import uuid

import boto3


app = FastAPI()


class GenerateRequest(BaseModel):
    text: str
    max_new_tokens: int = 64


def _download_s3_prefix_to_local(storage_uri: str, local_root: Path) -> Path:
    """
    Download all objects under an s3:// prefix (MinIO) to a local directory.

    This is a simple example implementation and not optimized for very large models.
    """
    parsed = urlparse(storage_uri)
    if parsed.scheme != "s3":
        # Not an S3 URI, return as-is
        return Path(storage_uri)

    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")

    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    session = boto3.session.Session()
    s3 = session.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
    )

    local_root.mkdir(parents=True, exist_ok=True)

    continuation_token = None
    while True:
        list_kwargs = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            list_kwargs["ContinuationToken"] = continuation_token

        resp = s3.list_objects_v2(**list_kwargs)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            # Strip the common prefix from the key to build a relative path
            rel = key[len(prefix) :].lstrip("/") if prefix else key
            local_path = local_root / rel
            local_path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(local_path))

        if not resp.get("IsTruncated"):
            break
        continuation_token = resp.get("NextContinuationToken")

    return local_root


def _resolve_model_path() -> str:
    """
    Resolve model path for DialogGPT example.

    Priority:
    1) MODEL_STORAGE_URI (S3/MinIO URI, used directly by transformers)
    2) MODEL_PATH (local path in container)
    3) Fallback to HF hub id: microsoft/DialoGPT-small
    """
    storage_uri = os.environ.get("MODEL_STORAGE_URI")
    if storage_uri:
        # If this is an S3/MinIO URI, download to a local cache directory first.
        if storage_uri.startswith("s3://"):
            cache_dir = Path(os.environ.get("LOCAL_MODEL_DIR", "/app/model"))
            local_path = _download_s3_prefix_to_local(storage_uri, cache_dir)
            return str(local_path)

        # Otherwise assume it's a local path already
        return storage_uri

    model_path = os.environ.get("MODEL_PATH")
    if model_path:
        return model_path

    return "microsoft/DialoGPT-small"


MODEL_PATH = _resolve_model_path()
TOKENIZER = AutoTokenizer.from_pretrained(MODEL_PATH)
MODEL = AutoModelForCausalLM.from_pretrained(MODEL_PATH)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    max_tokens: int = 128
    temperature: float = 0.8


def _build_prompt_from_messages(messages: List[ChatMessage]) -> str:
    """
    Simplified formatting of chat messages into a single prompt for DialogGPT.
    """
    # Use only the last user message for simplicity; DialogGPT is not instruction-tuned.
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    # Fallback: concatenate all contents
    return "\n".join(m.content for m in messages)


@app.post("/generate")
async def generate(req: GenerateRequest):
    """
    Simple text generation endpoint for DialogGPT.
    """
    inputs = TOKENIZER.encode(req.text + TOKENIZER.eos_token, return_tensors="pt")
    outputs = MODEL.generate(
        inputs,
        max_new_tokens=req.max_new_tokens,
        do_sample=True,
        top_p=0.9,
        temperature=0.8,
    )
    # Decode only the newly generated tokens (exclude the prompt part)
    generated_tokens = outputs[0][inputs.shape[-1] :]
    response = TOKENIZER.decode(generated_tokens, skip_special_tokens=True)
    return {"response": response}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    Minimal OpenAI-compatible chat completions endpoint for the platform.
    """
    start_time = time.time()

    prompt = _build_prompt_from_messages(req.messages)
    inputs = TOKENIZER.encode(prompt + TOKENIZER.eos_token, return_tensors="pt")
    outputs = MODEL.generate(
        inputs,
        max_new_tokens=req.max_tokens,
        do_sample=True,
        top_p=0.9,
        temperature=req.temperature,
    )
    # Decode only the newly generated tokens (exclude the prompt part)
    generated_tokens = outputs[0][inputs.shape[-1] :]
    response_text = TOKENIZER.decode(generated_tokens, skip_special_tokens=True)

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or "dialogpt-small",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            # We don't compute exact token counts in this simple example.
            "prompt_tokens": len(inputs[0]),
            "completion_tokens": len(outputs[0]) - len(inputs[0]),
            "total_tokens": len(outputs[0]),
        },
        "latency_ms": latency_ms,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    # In a more advanced example we could check a flag set after model load
    return {"status": "ok"}


