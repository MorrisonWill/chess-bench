from __future__ import annotations

import asyncio
import re
from typing import Sequence

import httpx
from pydantic import BaseModel


class OpenRouterError(RuntimeError):
    pass


class OpenRouterMoveError(OpenRouterError):
    pass


class OpenRouterModelConfig(BaseModel):
    name: str
    temperature: float = 0.2
    max_tokens: int = 32


class OpenRouterClient:
    def __init__(self, base_url: str, api_key: str | None, timeout: float = 20.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._client is not None:
            return
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=self._timeout)

    async def close(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    async def get_move(
        self,
        board_fen: str,
        san_history: Sequence[str],
        model_config: OpenRouterModelConfig,
    ) -> str:
        if self._client is None:
            raise OpenRouterError("OpenRouter client not started")
        payload = {
            "model": model_config.name,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a chess engine that responds with a single legal SAN move.",
                },
                {
                    "role": "user",
                    "content": self._format_prompt(board_fen, san_history),
                },
            ],
        }
        async with self._lock:
            response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        san = self._extract_san(content)
        if not san:
            raise OpenRouterMoveError(f"Unable to parse SAN move from response: {content!r}")
        return san

    @staticmethod
    def _format_prompt(board_fen: str, san_history: Sequence[str]) -> str:
        history = " ".join(san_history) if san_history else "(none)"
        return (
            "Provide the next legal chess move in Standard Algebraic Notation. "
            f"Current board FEN: {board_fen}. Moves so far: {history}. Respond with only the SAN string."
        )

    @staticmethod
    def _extract_san(content: str) -> str | None:
        san_match = re.search(r"([O0]-[O0]-[O0]|[O0]-[O0]|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|[a-h][1-8])", content)
        if san_match:
            return san_match.group(1).replace("0", "O")
        text = content.strip().split()
        return text[0] if text else None
