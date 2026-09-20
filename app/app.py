"""卡6 · Streamlit Demo：海报/视频合规审核 + 一键生成物料（卡7/8/9/10 全能力）。

启动：.venv/Scripts/python.exe -m streamlit run app/app.py --server.port 8501
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from engine.copywriter import generate_materials, validate_materials  # noqa: E402,F401
from engine.llm_client import LLMClient  # noqa: E402
from engine.loop import closed_loop  # noqa: E402
from engine.pipeline import audit_image, audit_text, audit_video, finalize  # noqa: E402
from engine.rag_layer import LawIndex  # noqa: E402

st.set_page_config(page_title="广告合规 Agent", page_icon="🛡️", layout="wide")

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
            loc = f" · 位置：{f['location']}" if f.get("location") else ""
            color = "red" if f["source"] != "keyword" else "orange"
            st.markdown(f":{color}[**{i}. {f['type']}**]（{src}{loc}） — 命中：**{f['fragment']}**")
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
    tr = report.get("transcript") or {}
    if report.get("input_type") == "image" and tr:
        with st.expander("📋 画面转写（供人工核对）", expanded=True):
            for t in tr.get("texts", []):
                st.markdown(f"- {t}")
            st.caption(f"画面元素：{tr.get('visual_elements', '')}")
    elif report.get("input_type") == "video" and tr:
        with st.expander("📋 视频转写（画面帧 + 口播）", expanded=True):
            for fr in tr.get("frames", []):
                st.markdown(f"**画面 {fr['t']}s**：" + " ｜ ".join(fr.get("texts", [])))
            for seg in tr.get("audio", []):
                st.markdown(f"**口播 {seg['start']}~{seg['end']}s**：{seg['text']}")
    render_findings(report)


llm, index = load_engine()

st.title("🛡️ 广告合规审核 Agent")
st.caption("文案 / 海报 / 视频三形态合规审核（带法条引用）＋ 商品信息一键生成合规物料　｜　语料：《广告法》+《民法典》")

mode = st.sidebar.radio("审核模式", ["双层（关键词 + 法律 RAG）", "仅关键词层"], index=0)
use_rag = "none" if mode.startswith("仅关键词") else "full"
st.sidebar.success(f"供应商：**{llm.provider}**\n\n文本：`{llm.text_model}`\n\n视觉：`{llm.vision_model}`\n\n法条库：{len(index.rows)} 条")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**判定口径**\n"
    "- 🔴 违规：明确命中法条禁止情形\n"
    "- 🟠 疑似：边缘表达，转人工复核\n"
    "- 🟢 合规：双层均无发现")

tab_gen, tab1, tab2, tab3 = st.tabs(["✨ 一键生成", "📝 文案审核", "🖼️ 海报图审核", "🎬 视频审核"])

# ── ✨ 一键生成 ────────────────────────────────────────────
with tab_gen:
    st.markdown("输入商品信息 → 自动生成四平台文案 + 宣传图（附 AI 标识）→ **自动过审，不合规自动改写**（上限 3 轮）")
    g_name = st.text_input("商品名称", value="便携榨汁杯")
    g_info = st.text_area("商品信息 / 卖点", value="USB充电，300ml，杯身可冷冻，母婴级材质，60秒出汁", height=80)
    if st.button("开始一键生成", type="primary", disabled=not g_name.strip()):
        with st.spinner("生成 → 审核 → 改写闭环运行中（约 1~2 分钟）…"):
            try:
                st.session_state["gen_result"] = closed_loop(
                    llm, index, {"name": g_name.strip(), "info": g_info})
            except Exception as e:
                st.error(f"生成失败：{e}")
    if "gen_result" in st.session_state:
        result = st.session_state["gen_result"]
        pack = result["pack"]
        audit = pack["audit"]
        if result["final_compliant"]:
            st.success(f"✅ 生成完成并自动过审（自动改写 {audit['revisions']} 轮，共 {result['rounds']} 轮审核）")
        else:
            st.warning(f"⚠️ {result['rounds']} 轮未完全收敛，建议人工复核")
        for p in pack["platforms"]:
            with st.container(border=True):
                st.markdown(f"**{p['platform']}**")
                st.markdown(p["copy"].replace("\n", "  \n"))
                if p["tags"]:
                    st.caption(" ".join("#" + t.lstrip("#") for t in p["tags"]))
        if pack.get("image_path") and Path(pack["image_path"]).exists():
            c1, c2 = st.columns([1, 2])
            c1.image(pack["image_path"], width=280)
            c2.markdown(f"**生图提示词**：{pack.get('image_prompt')}")
            c2.caption(pack.get("ai_disclosure"))
        with st.expander("审核改写轨迹", expanded=bool(not result["final_compliant"])):
            for t in result["trajectory"]:
                st.markdown(f"- 第 {t['round']} 轮：{t['risk']}（{t['n_findings']} 项）"
                            + ("　" + "；".join(t.get("fragments", [])) if t.get("fragments") else ""))

# ── 📝 文案审核 ────────────────────────────────────────────
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

# ── 🖼️ 海报图审核 ──────────────────────────────────────────
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

# ── 🎬 视频审核 ────────────────────────────────────────────
with tab3:
    vup = st.file_uploader("上传视频（mp4 / mov，建议 ≤2 分钟）", type=["mp4", "mov"])
    use_demo_v = st.checkbox("没有视频？用内置测试视频（画面+口播均含违规点）", value=vup is None)
    if st.button("开始审核视频", type="primary", disabled=(vup is None and not use_demo_v)):
        if use_demo_v:
            vpath = ROOT / "data" / "test_video.mp4"
        else:
            vdir = ROOT / "data" / "uploads"
            vdir.mkdir(exist_ok=True)
            vpath = vdir / vup.name
            vpath.write_bytes(vup.getvalue())
        st.video(str(vpath))
        with st.spinner("抽帧 + 语音转写 + 双通道审核中（约 1 分钟）…"):
            try:
                st.session_state["video_report"] = finalize(audit_video(llm, vpath, index, use_rag=use_rag))
            except Exception as e:
                st.error(f"审核失败：{e}")
    if "video_report" in st.session_state:
        render_report(st.session_state["video_report"])
