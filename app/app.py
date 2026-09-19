"""卡6 · Streamlit 双入口 Demo：海报合规审核 Agent。

启动：.venv/Scripts/python.exe -m streamlit run app/app.py --server.port 8501
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from engine.llm_client import LLMClient
from engine.pipeline import audit_image, audit_text, finalize
from engine.rag_layer import LawIndex

st.set_page_config(page_title="海报合规审核 Agent", page_icon="🛡️", layout="wide")

RISK = {"violation": ("违规", "red"), "suspicious": ("疑似违规", "orange"), "compliant": ("合规", "green")}
SOURCE_LABEL = {"keyword": "关键词层", "rag": "法律RAG", "visual": "视觉判定"}

SAMPLES = {
    "违规：极限词（全网最低价）": "全网最低价，行业第一品牌，点击抢购！",
    "违规：医疗功效（根治痘痘）": "根治痘痘，消炎杀菌一步到位",
    "违规：贬损竞品（吊打同行）": "吊打同行，别家都是假货，我们才是正品",
    "合规：正常促销": "新店开业，全场9折，欢迎进店选购",
    "陷阱：第一人称（应判合规）": "第一人称视角实拍，所见即所得",
}


@st.cache_resource(show_spinner="加载引擎（首次构建法条向量库约半分钟）…")
def load_engine():
    llm = LLMClient()
    idx = LawIndex(k=5)
    idx.build()
    return llm, idx


def render_findings(report):
    findings = report.get("findings", [])
    if not findings:
        st.success("两层审核均未发现问题。")
    for i, f in enumerate(findings, 1):
        with st.container(border=True):
            src = SOURCE_LABEL.get(f["source"], f["source"])
            color = "red" if f["source"] != "keyword" else "orange"
            st.markdown(f":{color}[**{i}. {f['type']}**]（来源：{src}） — 命中：**{f['fragment']}**")
            law = f["law"]
            quote = law["quote"][:90] + ("…" if len(law["quote"]) > 90 else "")
            st.markdown(f"> 📜 **{law['name']}·{law['article']}**　{quote}")
            st.markdown(f"- **判定理由**：{f['reason']}")
            st.markdown(f"- **改写建议**：{f['suggestion'] or '—'}")


def render_report(report):
    risk = report.get("risk_level", "compliant")
    label, color = RISK.get(risk, ("未知", "gray"))
    st.markdown(f"### 审核结论：:{color}[{label}]")
    st.markdown(f"**{report.get('summary', '')}**　"
                f"· 模型 `{report['meta']['model']}` · 耗时 {report['meta']['latency_ms'] / 1000:.1f}s")
    if report.get("input_type") == "image" and report.get("transcript"):
        tr = report["transcript"]
        with st.expander("📋 画面转写（供人工核对）", expanded=True):
            for t in tr.get("texts", []):
                st.markdown(f"- {t}")
            st.caption(f"画面元素：{tr.get('visual_elements', '')}")
    render_findings(report)


llm, index = load_engine()

st.title("🛡️ 海报合规审核 Agent")
st.caption("粘贴海报文案或上传海报图 → 输出带法条引用的合规审核报告　｜　语料：《广告法》+《民法典》人格权编·侵权责任编")

mode = st.sidebar.radio("审核模式", ["双层（关键词 + 法律 RAG）", "仅关键词层"], index=0)
use_rag = "none" if mode.startswith("仅关键词") else "full"
st.sidebar.success(f"供应商：**{llm.provider}**\n\n文本：`{llm.text_model}`\n\n视觉：`{llm.vision_model}`\n\n法条库：{len(index.rows)} 条")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**判定口径**\n"
    "- 🔴 违规：明确命中法条禁止情形\n"
    "- 🟠 疑似：边缘表达，转人工复核\n"
    "- 🟢 合规：双层均无发现")

tab1, tab2 = st.tabs(["📝 文案审核", "🖼️ 海报图审核"])

with tab1:
    sample = st.selectbox("快速填充示例", ["（自己输入）"] + list(SAMPLES))
    text = st.text_area("海报文案", value=SAMPLES.get(sample, ""), height=130,
                        placeholder="粘贴待审核的推广文案…")
    if st.button("开始审核文案", type="primary"):
        if not text.strip():
            st.warning("请先输入或选择一段文案。")
        else:
            with st.spinner("双层审核中（关键词层 + 法律 RAG 逐条比对）…" if use_rag == "full"
                            else "关键词层审核中…"):
                try:
                    st.session_state["text_report"] = finalize(audit_text(llm, text, index, use_rag=use_rag))
                except Exception as e:
                    st.error(f"审核失败：{e}")
    if "text_report" in st.session_state:
        render_report(st.session_state["text_report"])

with tab2:
    up = st.file_uploader("上传海报图（png / jpg）", type=["png", "jpg", "jpeg"])
    use_demo = st.checkbox("没有图？用内置示例海报（含极限词，可跑通流程）", value=up is None)
    if st.button("开始审核海报", type="primary", disabled=(up is None and not use_demo)):
        path = ROOT / "data" / "test_poster.png"
        if not use_demo and up is not None:
            updir = ROOT / "data" / "uploads"
            updir.mkdir(exist_ok=True)
            path = updir / up.name
            path.write_bytes(up.getvalue())
        st.image(str(path), width=300)
        with st.spinner("视觉转写 + 双通道审核中…"):
            try:
                st.session_state["img_report"] = finalize(audit_image(llm, path, index, use_rag=use_rag))
            except Exception as e:
                st.error(f"审核失败：{e}")
    if "img_report" in st.session_state:
        render_report(st.session_state["img_report"])
