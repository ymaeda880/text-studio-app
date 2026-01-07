# lib/gemini_responder.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator

from config.config import get_gemini_api_key


@dataclass
class GeminiUsage:
    # Geminiは usage を安定して取れない/取りにくい場合があるので推定用（呼び出し側で入れる）
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class GeminiResult:
    text: str
    usage: GeminiUsage


class GeminiResponder:
    """
    google-genai（Google GenAI SDK）を使う最小 responder。
    - stream(): 逐次テキストyield
    - complete(): 一括で text 返却
    参考：generate_content / generate_content_stream と config(system_instruction, max_output_tokens) :contentReference[oaicite:1]{index=1}
    """

    def __init__(self) -> None:
        self.final_text: str = ""
        self.usage = GeminiUsage()

        key = get_gemini_api_key()
        if not key:
            raise RuntimeError("GEMINI_API_KEY が未設定です（st.secrets）。")

        try:
            # 新SDK
            from google import genai
            from google.genai import types
        except Exception as e:
            raise RuntimeError(
                "google-genai が未導入です。`pip install google-genai` を実行してください。"
            ) from e

        self._genai = genai
        self._types = types

        # Gemini Developer API（APIキーで呼ぶ）
        # ※ Vertex AI を使う場合は genai.Client(vertexai=True, project=..., location=...) に切り替え
        self._client = genai.Client(api_key=key)

    def complete(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        max_output_tokens: int,
    ) -> GeminiResult:
        cfg = self._types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=int(max_output_tokens),
        )

        resp = self._client.models.generate_content(
            model=model,
            contents=user_content,
            config=cfg,
        )

        text = getattr(resp, "text", "") or ""
        self.final_text = text
        return GeminiResult(text=text, usage=self.usage)

    def stream(
        self,
        *,
        model: str,
        system_instruction: str,
        user_content: str,
        max_output_tokens: int,
        on_error_text: str = "Gemini stream error.",
    ) -> Iterator[str]:
        cfg = self._types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=int(max_output_tokens),
        )

        try:
            buf: list[str] = []
            for chunk in self._client.models.generate_content_stream(
                model=model,
                contents=user_content,
                config=cfg,
            ):
                t = getattr(chunk, "text", "") or ""
                if t:
                    buf.append(t)
                    yield t
            self.final_text = "".join(buf)
        except Exception:
            self.final_text = on_error_text
            yield on_error_text
