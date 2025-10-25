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
    def __init__(
        self, base_url: str, api_key: str | None, timeout: float = 20.0
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._max_attempts = 3

    async def start(self) -> None:
        if self._client is not None:
            return
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url, headers=headers, timeout=self._timeout
        )

    async def close(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None

    async def get_move(
        self,
        board_fen: str,
        san_history: Sequence[str],
        legal_moves: Sequence[str],
        model_config: OpenRouterModelConfig,
    ) -> str:
        if self._client is None:
            raise OpenRouterError("OpenRouter client not started")
        if not legal_moves:
            raise OpenRouterMoveError("No legal moves available for current position")
        legal_moves_normalized = [
            move.strip().replace("0", "O") for move in legal_moves if move.strip()
        ]
        legal_moves_set = set(legal_moves_normalized)
        messages = [
            {
                "role": "system",
                "content": "You are a chess engine that must obey instructions exactly.",
            },
            {
                "role": "user",
                "content": self._format_prompt(
                    board_fen, san_history, legal_moves_normalized
                ),
            },
        ]
        async with self._lock:
            for attempt in range(self._max_attempts):
                payload = {
                    "model": model_config.name,
                    "temperature": model_config.temperature,
                    "max_tokens": model_config.max_tokens,
                    "messages": messages,
                }
                response = await self._client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                print("llm content", content)
                san = self._extract_san(content, legal_moves_set)
                if san:
                    return san
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": self._format_retry_prompt(legal_moves_normalized),
                    }
                )
        raise OpenRouterMoveError(
            "Model failed to supply a legal SAN move after multiple attempts."
        )

    @staticmethod
    def _format_prompt(
        board_fen: str,
        san_history: Sequence[str],
        legal_moves: Sequence[str],
    ) -> str:
        history = " ".join(san_history) if san_history else "(none)"
        legal_moves_text = ", ".join(legal_moves)
        return (
            "You are to choose the next legal chess move in Standard Algebraic Notation.\n"
            f"Current board FEN: {board_fen}\n"
            f"Moves so far: {history}\n"
            f"Legal moves (SAN): {legal_moves_text}\n"
            "Reply with exactly one line in the format `MOVE: <SAN>` where <SAN> is a string "
            "from the legal moves list. Do not include commentary or any other text."
        )

    @staticmethod
    def _format_retry_prompt(legal_moves: Sequence[str]) -> str:
        legal_moves_text = ", ".join(legal_moves)
        return (
            "Your previous reply did not contain exactly one legal SAN move from the list. "
            "Respond again using the format `MOVE: <SAN>` choosing one move from this list only: "
            f"{legal_moves_text}."
        )

    @staticmethod
    def _extract_san(content: str, legal_moves: set[str]) -> str | None:
        candidates: list[str] = []
        for match in re.finditer(
            r"(?:MOVE:\s*)?([O0]-[O0]-[O0]|[O0]-[O0]|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|[a-h][1-8])",
            content,
            flags=re.IGNORECASE,
        ):
            san = match.group(1).replace("0", "O")
            if san in legal_moves:
                candidates.append(san)
        if candidates:
            return candidates[-1]
        tokens = [token.replace("0", "O") for token in content.split()]
        for token in tokens:
            if token in legal_moves:
                return token
        return None
