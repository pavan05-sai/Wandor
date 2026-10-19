import json
import re
import time
from typing import Any, Dict, Optional
import google.generativeai as genai
from app.core.config import settings
from app.core.errors import ExternalServiceError
from app.core.logging import get_logger
from app.llm.base import LLMProvider

logger = get_logger("gemini_provider")


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences and extract JSON."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        return match.group(1).strip()
    return text


def _attempt_json_repair(text: str) -> Optional[Dict[str, Any]]:
    """Try progressively more aggressive JSON parsing strategies."""
    for candidate in [text, _strip_json_fences(text)]:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return None


class GeminiProvider(LLMProvider):
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = max(1, settings.LLM_MAX_REPAIR_ATTEMPTS)
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def _build_model(self, system_instruction=None):
        full_system = ""
        if system_instruction:
            full_system = system_instruction.strip() + "\n\n"
        full_system += (
            "CRITICAL OUTPUT RULES:\n"
            "- Respond ONLY with a valid JSON object matching the requested schema.\n"
            "- Do NOT include any conversational text, markdown, or explanation outside JSON.\n"
            "- Do NOT invent facts, places, prices, or addresses not provided to you.\n"
            "- If information is unavailable, omit the field or use null — never fabricate values.\n"
            "- Your response must be parseable by Python json.loads() without preprocessing."
        )
        return genai.GenerativeModel(model_name=self.model_name, system_instruction=full_system)

    def generate_json(self, prompt, schema=None, system_instruction=None):
        if not self.api_key:
            raise ExternalServiceError(
                "Gemini API key is not configured. Set GEMINI_API_KEY to enable AI features."
            )
        model = self._build_model(system_instruction)
        last_error = RuntimeError("No attempt was made")
        for attempt in range(1, self.max_retries + 1):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(temperature=0.3, max_output_tokens=4096),
                    request_options={"timeout": self.timeout}
                )
                if not response or not response.candidates:
                    raise ExternalServiceError("Gemini returned an empty response. May be due to safety filtering or quota limit.")
                raw_text = response.text
                if not raw_text or not raw_text.strip():
                    raise ExternalServiceError("Gemini returned an empty text response.")
                parsed = _attempt_json_repair(raw_text)
                if parsed is None:
                    if attempt < self.max_retries:
                        logger.warning(f"Gemini attempt {attempt}: JSON parse failed. Preview: {raw_text[:200]!r}. Retrying...")
                        time.sleep(1.5 * attempt)
                        continue
                    raise ExternalServiceError(
                        f"Gemini response could not be parsed as JSON after {self.max_retries} attempt(s). "
                        f"Preview: {raw_text[:300]!r}"
                    )
                return parsed
            except ExternalServiceError:
                raise
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "quota" in err_str.lower() or "429" in err_str:
                    raise ExternalServiceError("Gemini API rate limit or quota exceeded. Please wait and try again.")
                if attempt < self.max_retries:
                    logger.warning(f"Gemini attempt {attempt} failed: {e}. Retrying...")
                    time.sleep(1.5 * attempt)
                else:
                    logger.error(f"Gemini failed after {self.max_retries} attempt(s): {e}")
                    raise ExternalServiceError(f"Gemini API error: {err_str}") from e
        raise ExternalServiceError(f"Gemini failed after {self.max_retries} attempt(s): {last_error}")

    def generate_text(self, prompt, system_instruction=None):
        if not self.api_key:
            raise ExternalServiceError("Gemini API key is not configured.")
        model = self._build_model(system_instruction)
        for attempt in range(1, self.max_retries + 1):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=2048),
                    request_options={"timeout": self.timeout}
                )
                if not response or not response.text:
                    raise ExternalServiceError("Gemini returned an empty text response.")
                return response.text.strip()
            except ExternalServiceError:
                raise
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Gemini text attempt {attempt} failed: {e}. Retrying...")
                    time.sleep(1.5 * attempt)
                else:
                    raise ExternalServiceError(f"Gemini text error: {str(e)}") from e
        raise ExternalServiceError("Gemini text generation failed.")
