import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.replay import ReplayProvider

logger = get_logger("base_agent")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_prompt_file(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_llm_provider() -> LLMProvider:
    """
    Return the appropriate LLM provider.
    - Uses Gemini if GEMINI_API_KEY is set and LLM_PROVIDER is 'gemini'.
    - Falls back to ReplayProvider only when DEMO_MODE is explicitly 'on'
      or when LLM_PROVIDER is explicitly 'replay'.
    - NEVER silently falls back to fake data when a real key is provided
      but the request fails — errors are propagated to callers.
    """
    if settings.DEMO_MODE == "on" or settings.LLM_PROVIDER == "replay":
        logger.info("Using ReplayProvider (demo/replay mode enabled).")
        return ReplayProvider()

    if not settings.GEMINI_API_KEY:
        logger.warning(
            "GEMINI_API_KEY is not set. "
            "Using ReplayProvider with demonstration data. "
            "Set GEMINI_API_KEY to enable real AI-generated itineraries."
        )
        return ReplayProvider()

    # Real Gemini — errors from this provider will propagate to callers
    return GeminiProvider()


class BaseAgent:
    def __init__(self, name: str, prompt_file: str):
        self.name = name
        self.system_instruction = load_prompt_file(prompt_file)
        self.llm = get_llm_provider()

    def run_tool_loop(
        self,
        prompt: str,
        tools: Dict[str, Callable],
        max_iterations: int = 4
    ) -> Tuple[Dict[str, Any], List[str]]:
        trace: List[str] = [f"Initialized {self.name} agent"]

        if isinstance(self.llm, ReplayProvider):
            trace.append("Using ReplayProvider for deterministic demonstration response.")
            result = self.llm.generate_json(prompt, system_instruction=self.system_instruction)
            return result, trace

        # Real Gemini call — do NOT silently catch and fallback
        trace.append(f"Calling {settings.LLM_MODEL} via Gemini API...")
        try:
            result = self.llm.generate_json(prompt, system_instruction=self.system_instruction)
            trace.append(f"Successfully generated structured response from {settings.LLM_MODEL}.")
            return result, trace
        except Exception as e:
            # Log the real error and re-raise — do NOT silently return fake data
            trace.append(f"Gemini API call failed: {e}")
            logger.error(f"Error in {self.name} agent Gemini call: {e}")
            raise
