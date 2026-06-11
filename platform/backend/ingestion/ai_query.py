from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "https://api.apimart.ai"
DEFAULT_MODEL = "gemini-3.5-flash"
_TIMEOUT_SECONDS = 60.0


class AiQueryError(Exception):
    """Raised when the upstream AI call fails or returns an unexpected shape."""


class ApimartGeminiClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    def ask(self, prompt: str) -> str:
        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AiQueryError(f"AI upstream call failed: {exc}") from exc
        return extract_answer_text(response.json())


def extract_answer_text(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AiQueryError("AI response is not a JSON object")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise AiQueryError("AI response is missing candidates")
    first = candidates[0]
    if not isinstance(first, dict):
        raise AiQueryError("AI response candidate is malformed")
    content = first.get("content")
    if not isinstance(content, dict):
        raise AiQueryError("AI response is missing content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise AiQueryError("AI response is missing parts")
    texts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not texts:
        raise AiQueryError("AI response has no text")
    return "".join(texts)
