import hashlib
import json
from typing import Any, Dict, Optional
from app.repositories.entities import CacheRepository


def compute_prompt_hash(model: str, prompt: str, system_instruction: Optional[str] = None) -> str:
    content = f"{model}:{system_instruction or ''}:{prompt}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class LLMResponseCache:
    @classmethod
    def get(cls, db: Any, model: str, prompt: str, system_instruction: Optional[str] = None) -> Optional[Dict[str, Any]]:
        prompt_hash = compute_prompt_hash(model, prompt, system_instruction)
        repo = CacheRepository(db)
        cached = repo.get(f"llm:{prompt_hash}", provider="llm")
        if cached:
            if isinstance(cached, dict) and "value" in cached:
                return cached["value"]
            return cached
        return None

    @classmethod
    def set(cls, db: Any, model: str, prompt: str, system_instruction: Optional[str], response_json: Any, ttl_seconds: int = 86400 * 7):
        prompt_hash = compute_prompt_hash(model, prompt, system_instruction)
        repo = CacheRepository(db)
        repo.set(f"llm:{prompt_hash}", provider="llm", value=response_json, ttl_seconds=ttl_seconds)
