# -*- coding: utf-8 -*-
# pages/25_目次チェック.py
from __future__ import annotations
import io, re, tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

import streamlit as st
import pandas as pd

# ==== PDF→テキスト ====
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None

# ==== DOCX→PDF ====
try:
    import pypandoc
except Exception:
    pypandoc = None
try:
    from docx2pdf import convert as docx2pdf_convert
except Exception:
    docx2pdf_convert = None


# =========================
# UI
# =========================
st.set_page_config(page_title="📄 直列テキスト法：頁番号抽出（方式選択→実行）", page_icon="📄", layout="wide")
st.title("📄 直列テキスト法：頁番号抽出（単独行のみ）")

with st.sidebar:
    st.subheader("① 入力ファイル")
    uploaded = st.file_uploader("Word（.docx）または PDF をアップロード", type=["docx", "pdf"])

    st.subheader("② ページ方式を選択")
    scheme = st.radio(
        "方式",
        ["(1) 1, 2, 3, 4, …", "(2) 1-1, 1-2, 2-1, 2-2, …"],
        index=1
    )

    st.subheader("③ 変換/抽出オプション")
    prefer = st.selectbox("DOCX→PDF 変換の優先順", ["pandoc,docx2pdf", "docx2pdf,pandoc"], index=0)
    join_pages = st.checkbox("PDFはページごとではなく全文を連結して処理（推奨）", value=True)
    keep_pdf = st.checkbox("変換PDFを ./data/last_converted.pdf に保存", value=False)

    st.subheader("④ 実行")
    run = st.button("処理開始", type="primary")

st.caption("※ 抽出は **“単独行にページ番号だけが書かれている行”** を区切りとして使います。本文に混ざる数字は無視します。")

if not run:
    st.stop()
if not uploaded:
    st.warning("まずファイルをアップロードしてください。")
    st.stop()
if fitz is None and pdfplumber is None:
    st.error("PyMuPDF か pdfplumber のどちらかをインストールしてください。`pip install pymupdf pdfplumber`")
    st.stop()


# =========================
# 変換 & テキスト抽出
# =========================
def convert_docx_to_pdf(input_docx: Path, out_pdf: Path, prefer: str) -> str:
    methods = [m.strip().lower() for m in prefer.split(",") if m.strip()]
    errs = []
    for m in methods:
        try:
            if m == "pandoc":
                if pypandoc is None:
                    raise RuntimeError("pypandoc not available")
                pypandoc.convert_file(str(input_docx), "pdf", outputfile=str(out_pdf))
                if out_pdf.exists() and out_pdf.stat().st_size > 0:
                    return "pandoc"
                raise RuntimeError("pandoc produced empty pdf")
            elif m == "docx2pdf":
                if docx2pdf_convert is None:
                    raise RuntimeError("docx2pdf not available")
                docx2pdf_convert(str(input_docx), str(out_pdf))
                if out_pdf.exists() and out_pdf.stat().st_size > 0:
                    return "docx2pdf"
                raise RuntimeError("docx2pdf produced empty pdf")
            else:
                raise RuntimeError(f"unknown method: {m}")
        except Exception as e:
            errs.append(f"{m}: {e}")
    raise RuntimeError("DOCX→PDF conversion failed. " + " / ".join(errs))

def pdf_to_fulltext(pdf_path: Path, join_pages: bool) -> str:
    if fitz is not None:
        doc = fitz.open(str(pdf_path))
        pages = [(p.get_text("text") or "") for p in doc]
        return ("\n".join(pages)) if join_pages else ("\n\n---PAGE-BREAK---\n\n".join(pages))
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
        return ("\n".join(pages)) if join_pages else ("\n\n---PAGE-BREAK---\n\n".join(pages))

# 入力の準備
Path("data").mkdir(parents=True, exist_ok=True)
suffix = uploaded.name.lower().rsplit(".", 1)[-1]

with st.spinner("テキスト準備中..."):
    if suffix == "pdf":
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            pdf_path = td / "input.pdf"
            pdf_path.write_bytes(uploaded.getvalue())
            in_type = "pdf"
            fulltext = pdf_to_fulltext(pdf_path, join_pages=join_pages)
    else:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            docx_path = td / "input.docx"
            docx_path.write_bytes(uploaded.getvalue())
            out_pdf = (Path("data/last_converted.pdf") if keep_pdf else (td / "output.pdf"))
            in_type = convert_docx_to_pdf(docx_path, out_pdf, prefer=prefer)
            fulltext = pdf_to_fulltext(out_pdf, join_pages=join_pages)

st.success(f"テキスト抽出完了（入力: {in_type}）")


# =========================
# 単独行ラベル検出（方式別）＋ 年っぽい除外 + 連番チェック
# =========================
HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"  # 各種ハイフン
def z2h_numhy(s: str) -> str:
    s = s.replace("\u3000", " ")
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    return re.sub(HY, "-", s)

def build_label_line_regex(scheme: str) -> re.Pattern:
    if scheme.startswith("(1)"):
        core = r"[0-9０-９]{1,6}"               # 連番
    else:
        core = rf"[0-9０-９]+(?:{HY}[0-9０-９]+)+"  # 章-ページ（複合可）
    return re.compile(rf"^\s*(?:p(?:age)?\.?\s*)?(?P<label>{core})\s*$", re.MULTILINE)

LABEL_LINE_RE = build_label_line_regex(scheme)

def valid_and_reason(label: str, scheme: str, prev_ok: Optional[str]) -> Tuple[bool, str]:
    """
    ラベルを「ページとして採用するか」を判定。
    - 方式(2)：先頭が >=100（例: 2018-3）は “年っぽい” として不採用
    - 連番チェック：前の「採用ラベル」との連続性を確認
      * (1) n が prev+1 なら採用。prev が無い最初は採用。
      * (2) chap-page 形式： (c,p) が (c, prev_p+1) か (c+1, 1) なら採用
    - 連続でない場合は不採用にし、理由を返す（テーブルには残す）
    """
    if scheme.startswith("(1)"):
        # 連番
        try:
            n = int(label)
        except Exception:
            return False, "連番形式で数値化できない"
        if prev_ok is None:
            return True, ""  # 最初は採用
        try:
            prev = int(prev_ok)
        except Exception:
            return True, ""  # 前が読めなければ採用
        if n == prev + 1:
            return True, ""
        else:
            return False, "非連番（連続していない）"
    else:
        # 章-ページ
        parts = label.split("-")
        if not (len(parts) >= 2 and all(p.isdigit() for p in parts)):
            return False, "章-ページ形式でない"
        chap = int(parts[0])
        # 年っぽい（例: 2018-3）は不採用
        if chap >= 100:
            return False, "年っぽい章番号（例: 2018-3）"
        page_n = int(parts[1])
        if prev_ok is None:
            return True, ""
        pparts = prev_ok.split("-")
        if not (len(pparts) >= 2 and all(p.isdigit() for p in pparts)):
            return True, ""  # 前が読めなければ採用
        pchap, ppage = int(pparts[0]), int(pparts[1])
        # 同じ章でページが +1 なら連番OK / 次の章の 1 ならOK
        if (chap == pchap and page_n == ppage + 1) or (chap == pchap + 1 and page_n == 1):
            return True, ""
        else:
            return False, "非連番（連続していない）"

def split_by_singleline_labels(fulltext: str, scheme: str) -> List[Dict[str, Any]]:
    """
    単独行のラベルだけで区切る。
    - 無効/非連番は is_page=False, reason に理由を入れて表には残す
    - is_page=True のものだけを「後工程に使用」できる
    """
    if not fulltext:
        return []
    txt = z2h_numhy(fulltext.replace("\r\n", "\n").replace("\r", "\n"))

    matches = list(LABEL_LINE_RE.finditer(txt))
    if not matches:
        return []

    rows: List[Dict[str, Any]] = []

    def next_nonempty_pos(pos: int) -> int:
        n = pos
        while n < len(txt) and txt[n] == "\n":
            n += 1
        return n

    prev_ok_label: Optional[str] = None  # 直前の「採用された」ページラベル
    for i, m in enumerate(matches):
        label = z2h_numhy(m.group("label"))
        start = next_nonempty_pos(m.end())
        end = matches[i+1].start() if i+1 < len(matches) else len(txt)
        body = txt[start:end].lstrip("\n ")

        ok, reason = valid_and_reason(label, scheme, prev_ok_label)
        if ok:
            prev_ok_label = label  # 採用されたら更新

        rows.append({
            "page_label": label,
            "is_page": ok,                 # 後工程に使えるかどうか
            "reason": "" if ok else reason, # 不採用理由（例：年っぽい／非連番）
            "char_count": len(body),
            "preview": body[:160].replace("\n", " ") + ("…" if len(body) > 160 else "")
        })
    return rows


# =========================
# 実行
# =========================
rows = split_by_singleline_labels(fulltext, scheme)
df = pd.DataFrame(rows)

st.subheader("抽出結果（全件）")
st.write(f"方式: **{scheme}**　/　検出ラベル数：**{len(df)}**")
if len(df):
    st.dataframe(df, use_container_width=True)
else:
    st.warning("単独行のページ番号が見つかりませんでした。")

# 後工程で使う対象（is_page=True のみ）
df_pages = df[df["is_page"] == True].reset_index(drop=True)
st.subheader("後工程に使用するページ（is_page=True）")
st.write(f"有効ページ数：**{len(df_pages)}**")
st.dataframe(df_pages, use_container_width=True)

# 警告まとめ
df_warn = df[df["is_page"] == False][["page_label", "reason"]].reset_index(drop=True)
if len(df_warn):
    st.subheader("⚠️ 警告（ページとして不採用）")
    st.dataframe(df_warn, use_container_width=True)
    st.caption("例：3-8 の次に 2018-3 のような “年っぽい” ラベルは不採用としてテーブルに残し、後工程から除外しています。")

# ダウンロード
buf_all = io.StringIO(); df.to_csv(buf_all, index=False)
st.download_button("CSVダウンロード（全件）", data=buf_all.getvalue().encode("utf-8-sig"),
                   file_name="page_segments_all.csv", mime="text/csv")
buf_ok = io.StringIO(); df_pages.to_csv(buf_ok, index=False)
st.download_button("CSVダウンロード（is_page=True のみ）", data=buf_ok.getvalue().encode("utf-8-sig"),
                   file_name="page_segments_valid_only.csv", mime="text/csv")


# =========================
# GPT API による目次ページ検証
# =========================
from typing import List
from openai import OpenAI


st.header("📑 目次ページ検証（GPTレビュー）")

# ---- API キー確認 ----
api_key = st.secrets.get("OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.warning("OPENAI_API_KEY が未設定のため、GPT による目次検証はスキップしました。 .streamlit/secrets.toml か環境変数に設定してください。")
else:
    client = OpenAI(api_key=api_key)

    # ---- 目次候補の抽出（素直版：行末に 1 / 1-1 / 3-60 などがある行）----
    HY = r"[\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFF0D]"  # 各種ハイフン
    LEADERS = r"[\.．・…]+"                                     # ドットリーダー群

    def z2h_numhy(s: str) -> str:
        s = (s or "").replace("\u3000", " ")
        s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        return re.sub(HY, "-", s)

    def build_label_tail_regex(scheme: str) -> re.Pattern:
        if scheme.startswith("(1)"):
            tail = r"(?P<label>[0-9０-９]{1,6})"
        else:
            tail = rf"(?P<label>[0-9０-９]+(?:{HY}[0-9０-９]+)+)"
        pat = rf"""
            ^(?P<head>.*?)                               # 左側本文
            (?:\s*{LEADERS}\s*|\s{{2,}})?                # ドットリーダー or 連続空白
            {tail}\s*$                                   # 行末にページラベル
        """
        return re.compile(pat, re.X)

    LABEL_TAIL_RE = build_label_tail_regex(scheme)

    
    def extract_toc_lines_for_gpt(fulltext: str, limit: int = 250) -> List[str]:
        """
        GPT に渡す TOC 行：行頭が『第』or数字で始まり、
        テキスト部分に日本語などの文字を含む行のみ採用。
        数字・記号・空白だけの行は除外。
        """
        lines = [l.rstrip() for l in fulltext.replace("\r\n","\n").replace("\r","\n").split("\n")]
        head_ok = re.compile(r"^(第|[0-9０-９])")               # ✅ 行頭が「第」or数字
        text_char = re.compile(r"[A-Za-z\u3040-\u30FF\u4E00-\u9FFF]")  # ✅ 文字が含まれるか
        out: List[str] = []

        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            # 行頭が「第」または数字で始まらない → 除外
            if not head_ok.match(s):
                continue
            # テキスト（文字）が一切ない → 除外
            if not text_char.search(s):
                continue

            m = LABEL_TAIL_RE.match(s)
            if not m:
                continue

            head = re.sub(rf"\s*{LEADERS}\s*$", "", m.group("head")).strip()
            label = z2h_numhy(m.group("label"))

            # タイトルが短すぎるものも除外
            if len(head) <= 1:
                continue

            out.append(f"{head} ::: {label}")
            if len(out) >= limit:
                break

        return out



    toc_lines = extract_toc_lines_for_gpt(fulltext)
    if not toc_lines:
        st.info("GPT に渡す目次候補が見つかりませんでした。")
    else:
        st.markdown("### 抽出された目次候補（上位）")
        st.code("\n".join(toc_lines[:60]))

        # ---- GPT へ投げる入力を準備 ----
        # ページラベルは is_page=True のものを優先（なければ全 df から）
        try:
            valid_labels_series = df_pages["page_label"].astype(str)
        except Exception:
            valid_labels_series = df["page_label"].astype(str) if "page_label" in df.columns else pd.Series([], dtype=str)

        # トークン節約のため先頭 N 件だけ
        VALID_MAX = 800
        TOC_MAX   = 250
        valid_labels_list = valid_labels_series.tolist()[:VALID_MAX]
        toc_for_prompt     = toc_lines[:TOC_MAX]

        system_prompt = (
            "あなたはPDF/Wordレポートの校正担当です。"
            "与えられた『目次候補の行』と『抽出された実ページラベル一覧』を照合し、"
            "各目次行が指すページ番号が実在しているか、章番号と整合しているかを確認します。"
            "短く箇条書きで、以下の分類で出してください：\n"
            "・OK（ページが存在し整合）\n"
            "・ズレ（ページは存在するが章や順序の整合が弱い）\n"
            "・不明（ページが未検出／本文側で見当たらない）\n"
            "また、最後に、全部OKであれば、OK塗装でない時はズレていると指摘してください。"
        )

        # 章-ページ方式のヒント（例：3-60 の章=3 を章見出しと照合する方向性）
        scheme_hint = "章-ページ方式（例: 3-60）。章はハイフン左側。" if scheme.startswith("(2)") else "連番方式（例: 1,2,3, ...）。"

        user_prompt = (
            f"【方式】{scheme_hint}\n"
            "【目次候補（左：タイトル、右：ページラベル）】\n"
            + "\n".join(toc_for_prompt) + "\n\n"
            "【抽出済みの実ページラベル（is_page=True 優先）】\n"
            + ", ".join(valid_labels_list)
        )

        # ---- 呼び出し（※ gpt-5-mini は temperature 指定不可）----
        with st.spinner("GPT による目次ページ検証を実行中…"):
            resp = client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        gpt_answer = resp.choices[0].message.content.strip()
        st.success("GPT による検証結果")
        st.text_area("🔎 GPTの判定・指摘", gpt_answer, height=420)

        # ダウンロード（Markdown）
        md_buf = io.StringIO()
        md_buf.write("# 目次ページ検証（GPT結果）\n\n")
        md_buf.write("## 目次候補（先頭）\n")
        md_buf.write("```\n" + "\n".join(toc_for_prompt) + "\n```\n\n")
        md_buf.write("## 抽出ページラベル（抜粋）\n")
        md_buf.write("```\n" + ", ".join(valid_labels_list[:200]) + "\n```\n\n")
        md_buf.write("## GPTの回答\n\n")
        md_buf.write(gpt_answer + "\n")
        st.download_button(
            "📥 GPT結果をMarkdownで保存",
            data=md_buf.getvalue().encode("utf-8"),
            file_name="toc_check_gpt_result.md",
            mime="text/markdown",
        )
