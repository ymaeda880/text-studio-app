# config/config.py
import streamlit as st

# ============================================================
# OpenAI API
# ============================================================
OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"

def get_openai_api_key() -> str:
    return st.secrets.get("OPENAI_API_KEY", "")

# ============================================================
# Gemini API
# ============================================================
def get_gemini_api_key() -> str:
    return st.secrets.get("GEMINI_API_KEY", "")

def has_gemini_api_key() -> bool:
    return bool(get_gemini_api_key())

# ============================================================
# 価格（USD / 100万トークン）※テキスト生成・理解系
# ============================================================
MODEL_PRICES_USD = {
    # --- OpenAI ---
    "gpt-5":         {"in": 1.25,  "out": 10.00},
    "gpt-5-mini":    {"in": 0.25,  "out": 2.00},
    "gpt-5-nano":    {"in": 0.05,  "out": 0.40},
    "gpt-4.1":       {"in": 2.00,  "out": 8.00},
    "gpt-4.1-mini":  {"in": 0.40,  "out": 1.60},

    # --- Gemini ---
    # ※ 公式価格改定があり得るので「概算用」
    "gemini-2.0-flash": {"in": 0.30, "out": 2.50},
    "gemini-2.0-pro":   {"in": 1.25, "out": 10.00},
}

# ============================================================
# Whisper / Transcribe（USD / 分）
# ============================================================
WHISPER_PRICE_PER_MIN = 0.006  # Whisper

TRANSCRIBE_PRICES_USD_PER_MIN = {
    "gpt-4o-mini-transcribe": 0.0125,
    "gpt-4o-transcribe":      0.025,
    "whisper-1":              WHISPER_PRICE_PER_MIN,
    # Gemini は「分単価」ではないためここには入れない
}

# ============================================================
# Prices (USD / 1M tokens) - Embeddings
# ============================================================
EMBEDDING_PRICES_USD = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,  # レガシー
}

# ============================================================
# Prices (USD / minute) - Audio
# ============================================================
WHISPER_PRICE_PER_MIN = 0.006

AUDIO_PRICES_USD_PER_MIN = {
    "whisper-1": WHISPER_PRICE_PER_MIN,
}

# もし “分単価” のモデル（OpenAI Transcribe系など）も扱うならここに集約
TRANSCRIBE_PRICES_USD_PER_MIN = {
    "gpt-4o-mini-transcribe": 0.0125,
    "gpt-4o-transcribe":      0.025,
    "whisper-1":              WHISPER_PRICE_PER_MIN,
    # Gemini は「分単価」ではない想定
}


# ============================================================
# 為替（USDJPY）
# ============================================================
DEFAULT_USDJPY = 150.0

# ============================================================
# Constants
# ============================================================
MILLION = 1_000_000

# ============================================================
# Gemini 用：トークン概算ユーティリティ
# ============================================================
def estimate_tokens_from_text(text: str) -> int:
    """
    Gemini / OpenAI 共通の簡易トークン推定。
    厳密ではないが費用目安には十分。
    目安：1 token ≒ 4 characters（日本語含む概算）
    """
    if not text:
        return 0
    return max(len(text) // 4, 1)

# def estimate_gemini_cost_usd(
#     *,
#     model: str,
#     input_tokens: int,
#     output_tokens: int,
# ) -> float | None:
#     """
#     Gemini の概算費用（USD）を返す。
#     未定義モデルの場合は None。
#     """
#     price = MODEL_PRICES_USD.get(model)
#     if not price:
#         return None

#     usd = (
#         (input_tokens * price["in"]) +
#         (output_tokens * price["out"])
#     ) / 1_000_000
#     return usd


# ============================================================
# API使用量・コスト概算ユーティリティ（共通）
# ------------------------------------------------------------
# 目的:
#   - OpenAI / Gemini の「入力トークン」「出力トークン」から、概算費用（USD/JPY）を算出する。
#   - 価格表（MODEL_PRICES_USD）を単一のソースとして参照し、ページごとの実装差分を無くす。
#
# 設計方針:
#   - できるだけ「純粋関数」（引数 → 戻り値）にし、テスト／再利用を容易にする。
#   - 為替（USD/JPY）は secrets 依存になり得るため、import時に評価しない。
#     → get_usdjpy() で実行時に取得し、必要なら呼び出し側で上書き可能にする。
#
# 前提:
#   - MODEL_PRICES_USD は「USD / 100万トークン」単価（in/out 別）を保持する。
#   - input_tokens / output_tokens は、可能なら API レスポンスの usage を使用し、
#     取得できない場合のみ estimate_tokens_from_text() 等で概算する。
# ============================================================

def get_usdjpy(default: float = 150.0) -> float:
    """secrets が使えるときは USDJPY、なければ default。import時評価を避ける。"""
    try:
        return float(st.secrets.get("USDJPY", default))
    except Exception:
        return float(default)

def estimate_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float | None:
    """MODEL_PRICES_USD を使って USD の概算費用を返す。未定義モデルなら None。"""
    price = MODEL_PRICES_USD.get(model)
    if not price:
        return None
    return ((input_tokens * price["in"]) + (output_tokens * price["out"])) / 1_000_000

def usd_to_jpy(usd: float, usd_jpy: float) -> float:
    return float(usd) * float(usd_jpy)

def format_cost_lines(*, model: str, in_t: int, out_t: int, usd_jpy: float) -> list[str]:
    usd = estimate_cost_usd(model=model, input_tokens=in_t, output_tokens=out_t)
    if usd is None:
        return [f"概算トークン：in {in_t:,} / out {out_t:,}（計 {in_t+out_t:,}）", "概算費用：N/A（価格表未定義）"]
    jpy = usd_to_jpy(usd, usd_jpy)
    return [
        f"概算トークン：in {in_t:,} / out {out_t:,}（計 {in_t+out_t:,}）",
        f"概算費用：${usd:,.6f}（約 ¥{jpy:,.0f} @ USD/JPY={usd_jpy:.1f}）",
    ]
