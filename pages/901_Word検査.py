# -*- coding: utf-8 -*-
# pages/22_Word検査.py
from __future__ import annotations
import io, os, re, json, tempfile, subprocess, sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pandas as pd
import streamlit as st

# ========== 依存（任意のものは存在チェック） ==========
try:
    import docx  # python-docx
except Exception:
    docx = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from docx2pdf import convert as docx2pdf_convert  # macOS/Windowsのみ安定
except Exception:
    docx2pdf_convert = None

try:
    import pypandoc  # pandoc が入っていればDOCX→PDF可能
except Exception:
    pypandoc = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ========== ページ設定 ==========
st.set_page_config(page_title="📝 Wordドキュメント検査（gpt-5-mini）", page_icon="📝", layout="wide")
st.title("📝 Wordドキュメント検査（gpt-5-mini）")
st.caption("DOCXをアップロードして、見出しチェック・表記ゆれ・図表引用のズレを自動検出します。")

# ========== ユーティリティ ==========
FIG_PATTERNS = [
    r"(?:図|Fig(?:\.|ure)?)\s*(\d+)(?:\s*[-–]\s*|[:：]\s*|\s+)?(.+)?",
]
TAB_PATTERNS = [
    r"(?:表|Tab(?:\.|le)?)\s*(\d+)(?:\s*[-–]\s*|[:：]\s*|\s+)?(.+)?",
]
REF_PATTERNS = [
    r"(?:図|Fig(?:\.|ure)?)\s*(\d+)",
    r"(?:表|Tab(?:\.|le)?)\s*(\d+)",
]

HEADING_STYLES_JA = {"見出し 1","見出し 2","見出し 3","Heading 1","Heading 2","Heading 3"}

def safe_openai_client() -> Optional["OpenAI"]:
    """OpenAIクライアント（環境に合わせてAPIキーを読み込み）"""
    if OpenAI is None:
        return None
    # 先に Streamlit の secrets → 環境変数 の順で
    api_key = None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        pass
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def try_docx_to_pdf(input_docx: Path, out_pdf: Path) -> bool:
    """DOCX→PDF変換を複数手段で試みる。成功したらTrue"""
    # 1) docx2pdf（macOS/Windows）
    if docx2pdf_convert is not None:
        try:
            docx2pdf_convert(str(input_docx), str(out_pdf))
            return out_pdf.exists() and out_pdf.stat().st_size > 0
        except Exception:
            pass
    # 2) pandoc
    if pypandoc is not None:
        try:
            pypandoc.convert_file(str(input_docx), 'pdf', outputfile=str(out_pdf))
            return out_pdf.exists() and out_pdf.stat().st_size > 0
        except Exception:
            pass
    # 3) LibreOffice（soffice）コマンド
    try:
        cmd = ["soffice","--headless","--convert-to","pdf","--outdir",str(out_pdf.parent), str(input_docx)]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        guess = input_docx.with_suffix(".pdf")
        if guess.exists():
            guess.replace(out_pdf)
        return out_pdf.exists() and out_pdf.stat().st_size > 0
    except Exception:
        pass
    return False

def extract_paragraphs(doc: "docx.document.Document") -> List[Tuple[str, str]]:
    """(style_name, text) を段落順で返す"""
    rows = []
    for p in doc.paragraphs:
        style = getattr(getattr(p, "style", None), "name", "") or ""
        text = p.text.strip()
        if text:
            rows.append((style, text))
    return rows

def list_headings(paras: List[Tuple[str,str]]) -> List[Dict]:
    """見出し候補を抽出"""
    out = []
    for i, (style, txt) in enumerate(paras, start=1):
        if style in HEADING_STYLES_JA:
            out.append({"index": i, "style": style, "heading": txt})
        else:
            # スタイル不明でも番号・章節形なら見出し候補
            if re.match(r"^\d+(?:\.\d+)*\s+.+", txt):
                out.append({"index": i, "style": style or "（不明）", "heading": txt})
    return out

def regex_search_all(patterns: List[str], text: str) -> List[re.Match]:
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            matches.append(m)
    return matches

def extract_fig_tab_captions(paras: List[Tuple[str,str]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """段落から図表キャプションを抽出"""
    fig_rows, tab_rows = [], []
    for idx, (style, txt) in enumerate(paras, start=1):
        for m in regex_search_all(FIG_PATTERNS, txt):
            num = m.group(1)
            title = (m.group(2) or "").strip()
            fig_rows.append({"para_index": idx, "number": int(num), "title": title, "raw": txt})
        for m in regex_search_all(TAB_PATTERNS, txt):
            num = m.group(1)
            title = (m.group(2) or "").strip()
            tab_rows.append({"para_index": idx, "number": int(num), "title": title, "raw": txt})
    return pd.DataFrame(fig_rows), pd.DataFrame(tab_rows)

def extract_references(paras: List[Tuple[str,str]]) -> pd.DataFrame:
    """本文中の図表参照（図1、表3、Figure 2、Table 4 など）を抽出"""
    rows = []
    for idx, (_, txt) in enumerate(paras, start=1):
        for pat in REF_PATTERNS:
            for m in re.finditer(pat, txt, flags=re.IGNORECASE):
                label = "図" if re.match(r"^(?:図|Fig)", m.group(0), re.IGNORECASE) else "表"
                num = int(m.group(1))
                rows.append({"para_index": idx, "label": label, "number": num, "context": txt})
    return pd.DataFrame(rows)

def detect_spelling_variants(paras: List[Tuple[str,str]]) -> Dict[str, List[str]]:
    """簡易：同綴の大小・全半角・カナ/英などの候補を拾う（後段でGPTに渡す）"""
    # 単語スキャン（日本語は難しいので簡易トークン化）
    text_all = "\n".join(t for _, t in paras)
    # 同一語の大小/全半角/長音などを緩く拾うための簡易規則
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-_/]*|[一-龥ぁ-んァ-ンー]{2,}", text_all)
    norm_map: Dict[str, set] = {}
    def norm(s: str) -> str:
        s2 = s.lower()
        s2 = s2.replace("‐","-").replace("—","-").replace("–","-").replace("／","/").replace("・","·")
        return s2
    for w in tokens:
        key = norm(w)
        norm_map.setdefault(key, set()).add(w)
    # バリエーションが複数あるものだけ返す
    variants = {k: sorted(list(v)) for k,v in norm_map.items() if len(v) >= 2}
    return variants

def guess_pages_from_pdf(pdf_path: Path, headings: List[Dict]) -> List[Dict]:
    """PDF化できた場合、見出しがどのページに現れるかを検索（簡易一致）"""
    if not pdfplumber:
        return headings
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return headings
    for h in headings:
        title = re.escape(h["heading"][:40])  # 先頭40文字で簡易検索
        found_page = None
        for i, t in enumerate(pages_text, start=1):
            if re.search(title, t):
                found_page = i
                break
        h["page"] = found_page
    return headings

def run_gpt_check(client: OpenAI, task: str, inputs: Dict) -> str:
    """gpt-5-miniに投げる汎用ヘルパー"""
    sys_prompt = (
        "あなたは日本語の学術レポート編集アシスタントです。"
        "入力（JSON）に基づき、短く要点整理して出力してください。出力はMarkdownで。"
    )
    user_msg = f"タスク: {task}\n入力JSON:\n```json\n{json.dumps(inputs, ensure_ascii=False, indent=2)}\n```"
    resp = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role":"system","content":sys_prompt},{"role":"user","content":user_msg}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()

def download_button_df(df: pd.DataFrame, label: str, file_name: str):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    st.download_button(label, data=buf.getvalue().encode("utf-8-sig"), file_name=file_name, mime="text/csv")

# ========== サイドバーUI ==========
with st.sidebar:
    st.header("設定")
    proc = st.selectbox("処理の種類", ["（１）見出しチェック", "（２）表記ゆれ", "（３）図表↔本文のズレ"])
    option = st.radio("オプション", ["標準", "厳密（検出多め）", "GPTに任せる"], index=0)
    st.caption("※ GPTに任せる：要点要約・統一案の生成に gpt-5-mini を使います。")

uploaded = st.file_uploader("Word（.docx）をアップロード", type=["docx"])

if not uploaded:
    st.info("まず .docx ファイルをアップロードしてください。")
    st.stop()

if docx is None:
    st.error("python-docx が見つかりません。requirements.txt を参照してインストールしてください。")
    st.stop()

# ========== 解析フロー ==========
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    docx_path = td / "input.docx"
    with open(docx_path, "wb") as f:
        f.write(uploaded.read())

    # DOCX読み込み
    doc = docx.Document(str(docx_path))
    paras = extract_paragraphs(doc)

    # 可能ならPDF化（ページ割り当て用）
    pdf_path = td / "input.pdf"
    got_pdf = try_docx_to_pdf(docx_path, pdf_path)

# （１）見出しとページ一覧
if proc.startswith("（１）"):
    headings = list_headings(paras)
    if got_pdf:
        headings = guess_pages_from_pdf(pdf_path, headings)
    df = pd.DataFrame(headings)
    st.subheader("見出し一覧")
    st.dataframe(df, use_container_width=True)
    download_button_df(df, "CSVダウンロード（見出し一覧）", "headings.csv")

    # GPTによる「見出しの付き方」チェック（階層・重複・粒度）
    if option == "GPTに任せる":
        client = safe_openai_client()
        if client:
            inputs = {
                "headings": headings,
                "notes": "ページ番号はnullの場合があります（PDF化できなかった等）。"
            }
            st.markdown("#### GPTのチェック結果")
            st.markdown(run_gpt_check(client, "見出し構成の適否・不足/重複の指摘・改善提案", inputs))
        else:
            st.warning("OpenAI APIキーが未設定のため、GPT解析はスキップしました。")

# （２）表記ゆれ
elif proc.startswith("（２）"):
    variants = detect_spelling_variants(paras)
    # 閾値（厳密モードは短い語も拾う）
    min_len = 2 if option == "厳密（検出多め）" else 3
    rows = []
    for k, vs in variants.items():
        if max(len(v) for v in vs) >= min_len:
            rows.append({"normalized_key": k, "variants": ", ".join(vs), "count": len(vs)})
    df = pd.DataFrame(sorted(rows, key=lambda r: (-r["count"], r["normalized_key"])))
    st.subheader("表記ゆれ候補（ルール検出）")
    st.dataframe(df, use_container_width=True)
    download_button_df(df, "CSVダウンロード（表記ゆれ候補）", "variants.csv")

    # GPTに統一案を出させる
    if option == "GPTに任せる":
        client = safe_openai_client()
        if client and len(df):
            # 上位 N 件のみ渡す（トークン節約）
            N = 60
            sample = df.head(N).to_dict(orient="records")
            inputs = {
                "variants_topN": sample,
                "policy_hint": "学術レポートの日本語表記。英語用語は小文字の英語表記（例：決定木（decision tree））を基本。用語は一貫性を優先。"
            }
            st.markdown("#### GPTの統一提案（上位候補）")
            st.markdown(run_gpt_check(client, "表記のゆれの統一リスト（推奨表記・置換例）を箇条書きで提示", inputs))
        elif not client:
            st.warning("OpenAI APIキーが未設定のため、GPT解析はスキップしました。")

# （３）図表番号・タイトルと本文引用のズレ
else:
    figs_df, tabs_df = extract_fig_tab_captions(paras)
    refs_df = extract_references(paras)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 図のキャプション")
        st.dataframe(figs_df, use_container_width=True)
        if len(figs_df):
            download_button_df(figs_df, "CSVダウンロード（図）", "figures.csv")
    with col2:
        st.markdown("#### 表のキャプション")
        st.dataframe(tabs_df, use_container_width=True)
        if len(tabs_df):
            download_button_df(tabs_df, "CSVダウンロード（表）", "tables.csv")

    st.markdown("#### 本文内の参照（図/表）")
    st.dataframe(refs_df, use_container_width=True)
    if len(refs_df):
        download_button_df(refs_df, "CSVダウンロード（参照）", "references.csv")

    # 不整合チェック
    issues = []
    # 期待される連番（欠番検出）
    def missing_numbers(df: pd.DataFrame) -> List[int]:
        if not len(df):
            return []
        nums = sorted(df["number"].unique().tolist())
        expected = list(range(1, max(nums)+1))
        return [n for n in expected if n not in nums]

    miss_fig = missing_numbers(figs_df)
    miss_tab = missing_numbers(tabs_df)

    # 参照はあるのに定義がない、または定義はあるのに本文で参照されていない
    ref_fig_nums = set(refs_df.loc[refs_df["label"]=="図","number"].tolist())
    ref_tab_nums = set(refs_df.loc[refs_df["label"]=="表","number"].tolist())
    cap_fig_nums = set(figs_df["number"].tolist())
    cap_tab_nums = set(tabs_df["number"].tolist())

    undef_fig = sorted(list(ref_fig_nums - cap_fig_nums))
    undef_tab = sorted(list(ref_tab_nums - cap_tab_nums))
    unused_fig = sorted(list(cap_fig_nums - ref_fig_nums))
    unused_tab = sorted(list(cap_tab_nums - ref_tab_nums))

    if miss_fig: issues.append(f"図：欠番 {miss_fig}")
    if miss_tab: issues.append(f"表：欠番 {miss_tab}")
    if undef_fig: issues.append(f"本文に参照があるが未定義の図番号: {undef_fig}")
    if undef_tab: issues.append(f"本文に参照があるが未定義の表番号: {undef_tab}")
    if unused_fig: issues.append(f"本文で参照されていない図番号: {unused_fig}")
    if unused_tab: issues.append(f"本文で参照されていない表番号: {unused_tab}")

    st.subheader("検出結果（要約）")
    if issues:
        st.error(" / ".join(issues))
    else:
        st.success("図表と本文参照の整合性に大きな問題は見つかりませんでした。")

    # GPTで簡易レビュー（タイトルの重複・命名規則・説明性）
    if option == "GPTに任せる":
        client = safe_openai_client()
        if client:
            inputs = {
                "figures": figs_df.to_dict(orient="records"),
                "tables":  tabs_df.to_dict(orient="records"),
                "refs":    refs_df.to_dict(orient="records"),
            }
            st.markdown("#### GPTのレビュー（図表命名・参照の仕方）")
            st.markdown(run_gpt_check(client, "図表番号・タイトルの付け方と参照の仕方に関するレビュー", inputs))
        else:
            st.warning("OpenAI APIキーが未設定のため、GPT解析はスキップしました。")
