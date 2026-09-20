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

# ── 主题：全屏摄影背景 + 深色玻璃面板 + 白色排版（参考 网页设计/风格参考） ──
import base64

_BG = ROOT / "app" / "assets" / "bg.jpg"
if _BG.exists():
    _b64 = base64.b64encode(_BG.read_bytes()).decode()
    _bg_css = f'url("data:image/jpeg;base64,{_b64}")'
else:
    _bg_css = "linear-gradient(160deg, #0b1220 0%, #16233b 60%, #0b1220 100%)"

st.markdown(
    f"""
    <style>
    /* 全屏背景 + 压暗渐变，保证白色文字可读 */
    .stApp {{
        background: linear-gradient(rgba(7,11,20,.42), rgba(7,11,20,.66)), {_bg_css};
        background-size: cover;
        background-position: center 30%;
        background-attachment: fixed;
        color: #E9EDF4;
    }}
    header[data-testid="stHeader"] {{ background: transparent; height: 2.6rem; }}
    /* 隐藏右上角 Deploy 原生菜单，保持极简 */
    div[data-testid="stToolbar"] {{ visibility: hidden; }}

    /* Hero 头部：小字距 kicker + 大标题（参考风格） */
    .hero-kicker {{
        letter-spacing: .42em; font-size: .82rem; font-weight: 500;
        color: rgba(255,255,255,.72); text-transform: uppercase; margin: 1.2rem 0 .6rem;
    }}
    .hero-title {{
        font-size: 3.4rem; font-weight: 900; letter-spacing: .12em;
        color: #FFFFFF; margin: 0 0 .5rem; line-height: 1.15;
        text-shadow: 0 2px 24px rgba(0,0,0,.45);
    }}
    .hero-sub {{
        color: rgba(233,237,244,.82); font-size: .95rem; margin-bottom: .4rem;
    }}
    .hero-rule {{
        height: 1px; border: 0; margin: 1.1rem 0 1.4rem;
        background: linear-gradient(90deg, rgba(233,184,114,.9), rgba(255,255,255,.08));
    }}

    /* 侧栏：深色玻璃 */
    section[data-testid="stSidebar"] {{
        background: rgba(7,11,20,.58);
        backdrop-filter: blur(14px);
        border-right: 1px solid rgba(255,255,255,.12);
    }}
    section[data-testid="stSidebar"] * {{ color: #E9EDF4 !important; }}
    section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.15); }}

    /* 主区文字基色 */
    .block-container {{ padding-top: 1.6rem; max-width: 1180px; }}
    h1, h2, h3 {{ color: #FFFFFF !important; }}

    /* 玻璃输入件 */
    .stTextArea textarea, .stTextInput input {{
        background: rgba(8,13,24,.55) !important;
        color: #F2F5FA !important;
        border: 1px solid rgba(255,255,255,.24) !important;
        border-radius: 8px !important;
    }}
    .stTextArea textarea::placeholder, .stTextInput input::placeholder {{ color: rgba(233,237,244,.45) !important; }}
    div[data-testid="stFileUploader"] section {{
        background: rgba(8,13,24,.45); border: 1px dashed rgba(255,255,255,.28); border-radius: 10px;
    }}

    /* 按钮：日出金 */
    .stButton > button {{
        background: linear-gradient(180deg, #EFC98B, #DFA95C);
        color: #241703; font-weight: 700; border: none; border-radius: 8px;
        padding: .45rem 1.3rem;
        box-shadow: 0 4px 18px rgba(0,0,0,.35);
    }}
    .stButton > button:hover {{ filter: brightness(1.06); }}

    /* Tabs：白色文字 + 金色选中下划线 */
    div[data-testid="stTabs"] button {{ color: rgba(255,255,255,.62) !important; font-weight: 600; }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{ color: #FFFFFF !important; }}
    div[data-testid="stTabs"] button[aria-selected="true"] p {{
        border-bottom: 2px solid #E9B872;
    }}

    /* 玻璃容器 / 折叠面板 */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: rgba(7,11,20,.5); backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,.16) !important; border-radius: 12px;
    }}
    div[data-testid="stExpander"] {{
        background: rgba(7,11,20,.45); border: 1px solid rgba(255,255,255,.14);
        border-radius: 10px;
    }}
    details summary {{ color: #E9EDF4 !important; }}

    /* 提示条：深色玻璃 + 彩色描边 */
    div[data-testid="stAlert"] {{
        background: rgba(7,11,20,.55); backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,.14); border-radius: 10px;
    }}

    /* 图片：轻描边 */
    img {{ border-radius: 10px; }}

    /* 组件标签与代码药丸（系统浅色主题兜底） */
    [data-testid="stWidgetLabel"] p {{ color: #E9EDF4 !important; }}
    .stApp code {{
        background: rgba(255,255,255,.14) !important;
        color: #FFD9A0 !important; border-radius: 6px; padding: 2px 8px;
    }}
    div[data-testid="stTabs"] button p {{
        color: rgba(255,255,255,.62) !important; font-weight: 600;
    }}
    div[data-testid="stTabs"] button[aria-selected="true"] p {{
        color: #FFFFFF !important;
    }}
    .stApp h1, .stApp h2, .stApp h3, .stApp strong {{ color: #FFFFFF !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <p class="hero-kicker">Ad Compliance · 法律合规审核</p>
    <p class="hero-title">广告合规审核 Agent</p>
    <p class="hero-sub">文案 / 海报 / 视频三形态合规审核（带法条引用）＋ 商品信息一键生成合规物料　｜　语料：《广告法》+《民法典》</p>
    <hr class="hero-rule">
    """,
    unsafe_allow_html=True,
)
st.caption("提示：右上角「审核模式」与判定口径见左侧栏；所有审核结果均由引擎实时生成。")


@st.cache_resource(show_spinner="加载引擎（首次构建法条向量库约半分钟）…")
def load_engine():
    llm = LLMClient()
    idx = LawIndex(k=5)
    idx.build()
    return llm, idx


llm, index = load_engine()

mode = st.sidebar.radio("审核模式", ["双层（关键词 + 法律 RAG）", "仅关键词层"], index=0)
use_rag = "none" if mode.startswith("仅关键词") else "full"
st.sidebar.markdown(f"**供应商**：`{llm.provider}`\n\n文本：`{llm.text_model}`\n\n视觉：`{llm.vision_model}`\n\n法条库：{len(index.rows)} 条")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**判定口径**\n"
    "- 🔴 违规：明确命中法条禁止情形\n"
    "- 🟠 疑似：边缘表达，转人工复核\n"
    "- 🟢 合规：双层均无发现")

RISK = {"violation": ("违规", "red"), "suspicious": ("疑似违规", "orange"), "compliant": ("合规", "green")}
SOURCE_LABEL = {"keyword": "关键词层", "rag": "法律RAG", "visual": "视觉判定"}

SAMPLES = {
    "违规：极限词（全网最低价）": "全网最低价，行业第一品牌，点击抢购！",
    "违规：医疗功效（根治痘痘）": "根治痘痘，消炎杀菌一步到位",
    "违规：贬损竞品（吊打同行）": "吊打同行，别家都是假货，我们才是正品",
    "合规：正常促销": "新店开业，全场9折，欢迎进店选购",
    "陷阱：第一人称（应判合规）": "第一人称视角实拍，所见即所得",
}


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
