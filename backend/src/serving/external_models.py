"""External model clients for OpenAI, Ollama, and other external providers."""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ExternalModelClient:
    """Base class for external model clients."""

    def __init__(self, config: dict):
        self.config = config

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Generate chat completion from external model.
        
        Returns:
            Dict with 'content', 'usage' (prompt_tokens, completion_tokens, total_tokens)
        """
        raise NotImplementedError


class OpenAIClient(ExternalModelClient):
    """Client for OpenAI API (GPT-3.5, GPT-4, etc.)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model_name = config.get("model_name", "gpt-3.5-turbo")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Call OpenAI chat completion API."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                choice = data["choices"][0]
                usage = data.get("usage", {})
                
                return {
                    "content": choice["message"]["content"],
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "usage": {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                }
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
                raise ValueError(f"OpenAI API error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"OpenAI request failed: {e}")
                raise


class OllamaClient(ExternalModelClient):
    """Client for Ollama API (local or remote Ollama server)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("endpoint", "http://localhost:11434")
        self.model_name = config.get("model_name", "llama2")
        # Remove trailing slash
        self.endpoint = self.endpoint.rstrip("/")

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Call Ollama chat completion API."""
        url = f"{self.endpoint}/api/chat"
        
        # Convert messages to Ollama format
        # Ollama expects messages in a specific format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })
        
        payload = {
            "model": self.model_name,
            "messages": ollama_messages,
            "stream": False,  # Disable streaming to get single JSON response
            "options": {
                "temperature": temperature,
            },
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # Ollama may return streaming response even with stream=False
                # Handle both single JSON and newline-delimited JSON
                response_text = response.text.strip()
                
                # Try to parse as single JSON first
                data = None
                content = ""
                lines = []
                
                try:
                    data = response.json()
                except (ValueError, json.JSONDecodeError):
                    # If that fails, it might be newline-delimited JSON
                    # Take the last complete JSON object
                    lines = response_text.split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            break
                        except (ValueError, json.JSONDecodeError):
                            continue
                    
                    if data is None:
                        raise ValueError("Could not parse Ollama response as JSON")
                
                # Extract content from the response
                if data:
                    message_obj = data.get("message", {})
                    if isinstance(message_obj, dict):
                        content = message_obj.get("content", "")
                    else:
                        content = str(message_obj) if message_obj else ""
                
                # If content is still empty and we have multiple lines, accumulate from all chunks
                if not content and lines:
                    all_content = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            chunk_message = chunk.get("message", {})
                            if isinstance(chunk_message, dict):
                                chunk_content = chunk_message.get("content", "")
                            else:
                                chunk_content = str(chunk_message) if chunk_message else ""
                            if chunk_content:
                                all_content.append(chunk_content)
                        except (ValueError, json.JSONDecodeError):
                            continue
                    if all_content:
                        content = "".join(all_content)
                
                if not content:
                    logger.warning(f"Ollama response had no content. Response: {response_text[:200]}")
                    content = "No response generated"
                
                done = data.get("done", True) if data else True
                finish_reason = "stop" if done else "length"
                
                # Ollama doesn't provide token usage in the same format
                # Estimate based on content length
                prompt_text = " ".join(msg["content"] for msg in messages)
                prompt_tokens = len(prompt_text.split()) * 1.3
                completion_tokens = len(content.split()) * 1.3
                
                return {
                    "content": content,
                    "finish_reason": finish_reason,
                    "usage": {
                        "prompt_tokens": int(prompt_tokens),
                        "completion_tokens": int(completion_tokens),
                        "total_tokens": int(prompt_tokens + completion_tokens),
                    },
                }
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error: {e.response.status_code} - {e.response.text}")
                raise ValueError(f"Ollama API error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"Ollama request failed: {e}")
                raise


def get_external_model_client(model_entry) -> Optional[ExternalModelClient]:
    """Factory function to create appropriate external model client.
    
    Args:
        model_entry: ModelCatalogEntry with type='external' and metadata containing provider info
        
    Returns:
        ExternalModelClient instance or None if not external model
    """
    if model_entry.type != "external":
        return None
    
    metadata = model_entry.model_metadata or {}
    provider = metadata.get("provider", "").lower()
    
    if provider == "openai":
        config = {
            "api_key": metadata.get("api_key"),
            "model_name": metadata.get("model_name", "gpt-3.5-turbo"),
            "base_url": metadata.get("base_url", "https://api.openai.com/v1"),
        }
        return OpenAIClient(config)
    
    elif provider == "ollama":
        config = {
            "endpoint": metadata.get("endpoint", "http://localhost:11434"),
            "model_name": metadata.get("model_name", "llama2"),
        }
        return OllamaClient(config)
    
    else:
        logger.warning(f"Unknown external provider: {provider}")
        return None

