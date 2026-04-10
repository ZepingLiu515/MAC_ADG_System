# UI 组件库 (上传框、进度条等)

import streamlit as st
import os


def apply_theme(theme_mode: str = "light"):
    """注入“Rigorous & Deep”学术风格主题（支持深色）。"""
    mode = str(theme_mode or "light").strip().lower()
    if mode not in {"light", "dark", "auto", "system"}:
        mode = "light"
    if mode == "system":
        mode = "auto"

    light_vars = {
        "bg": "#f8f9fa",
        "ink": "#343a40",
        "title": "#081c3b",
        "muted": "#6c757d",
        "card": "#ffffff",
        "border": "#dee2e6",
        "accent": "#0d3b66",
        "accent_2": "#1b5c52",
        "shadow": "0 16px 32px rgba(8, 28, 59, 0.06)",
        "uploader_bg": "#fcfcfc",
    }
    dark_vars = {
        "bg": "#0b1220",
        "ink": "#e5e7eb",
        "title": "#cfe1ff",
        "muted": "#94a3b8",
        "card": "#111827",
        "border": "#1f2937",
        "accent": "#2563eb",
        "accent_2": "#1b5c52",
        "shadow": "0 16px 32px rgba(0, 0, 0, 0.35)",
        "uploader_bg": "#0f172a",
    }

    vars_use = dark_vars if mode == "dark" else light_vars

    css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: __BG__;
  --ink: __INK__;
  --title: __TITLE__;
  --muted: __MUTED__;
  --card: __CARD__;
  --border: __BORDER__;
  --accent: __ACCENT__;
  --accent-2: __ACCENT_2__;
  --shadow: __SHADOW__;
    --uploader-bg: __UPLOADER_BG__;
}

html, body, [class*="stApp"] {
    font-family: "Inter", "Segoe UI", "Roboto", sans-serif;
    color: var(--ink);
    background: var(--bg);
}

h1, h2, h3, h4 {
    color: var(--title);
    letter-spacing: 0.01em;
}

.hero {
    padding: 22px 26px;
    border-radius: 12px;
    background: var(--card);
    border: 1px solid var(--border);
    box-shadow: var(--shadow);
    animation: fadeUp 0.5s ease both;
}

.hero .tag {
    display: inline-block;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 8px;
}

.hero h1 {
    margin: 0;
    font-size: 28px;
}

.hero p {
    margin: 6px 0 0 0;
    font-size: 14px;
    color: var(--muted);
}

.card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 18px;
    box-shadow: 0 8px 18px rgba(8, 28, 59, 0.06);
    animation: fadeUp 0.5s ease both;
}

.card + .card {
    margin-top: 14px;
}

.card-title {
    font-weight: 600;
    font-size: 15px;
    margin-bottom: 6px;
}

.card-sub {
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 12px;
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
}

.stat {
    padding: 12px 14px;
    border-radius: 8px;
    background: #ffffff;
    border: 1px solid var(--border);
}

.stat .label {
    font-size: 12px;
    color: var(--muted);
}

.stat .value {
    font-size: 18px;
    font-weight: 700;
    color: var(--title);
}

div[data-testid="stFileUploader"] {
    border-radius: 8px;
    padding: 12px;
    border: 1px dashed var(--border);
    background: var(--uploader-bg);
}

.stButton > button {
    border-radius: 2px;
    border: 1px solid var(--border);
    background: var(--accent);
    color: white;
    font-weight: 600;
    padding: 0.5rem 1.1rem;
    box-shadow: none;
}

.stButton > button:hover {
    filter: brightness(0.98);
}

div[data-testid="stDataFrame"] {
    border-radius: 8px;
    border: 1px solid var(--border);
    overflow: hidden;
}

section[data-testid="stSidebarNav"] a {
    border-radius: 6px;
    padding: 6px 10px;
    margin-bottom: 4px;
}

section[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: #081c3b;
    color: #ffffff;
    font-weight: 600;
}

.log-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
}

.log-tag {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: white;
}

.log-scout { background: #0d3b66; }
.log-vision { background: #1b5c52; }
.log-judge { background: #6c4f2a; }

.log-conf {
    color: var(--muted);
    font-size: 12px;
}

@keyframes fadeUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (prefers-color-scheme: dark) {
  .stButton > button {
    background: var(--accent);
  }
}
</style>
    """

    auto_css = ""
    if mode == "auto":
        auto_css = """
@media (prefers-color-scheme: dark) {
  :root {
    --bg: __D_BG__;
    --ink: __D_INK__;
    --title: __D_TITLE__;
    --muted: __D_MUTED__;
    --card: __D_CARD__;
    --border: __D_BORDER__;
    --accent: __D_ACCENT__;
    --accent-2: __D_ACCENT_2__;
    --shadow: __D_SHADOW__;
    --uploader-bg: __D_UPLOADER_BG__;
  }
}
"""

    if auto_css:
        css = css.replace("</style>", auto_css + "</style>")
    css = (
        css.replace("__BG__", vars_use["bg"])
        .replace("__INK__", vars_use["ink"])
        .replace("__TITLE__", vars_use["title"])
        .replace("__MUTED__", vars_use["muted"])
        .replace("__CARD__", vars_use["card"])
        .replace("__BORDER__", vars_use["border"])
        .replace("__ACCENT__", vars_use["accent"])
        .replace("__ACCENT_2__", vars_use["accent_2"])
        .replace("__SHADOW__", vars_use["shadow"])
        .replace("__UPLOADER_BG__", vars_use["uploader_bg"])
        .replace("__D_BG__", dark_vars["bg"])
        .replace("__D_INK__", dark_vars["ink"])
        .replace("__D_TITLE__", dark_vars["title"])
        .replace("__D_MUTED__", dark_vars["muted"])
        .replace("__D_CARD__", dark_vars["card"])
        .replace("__D_BORDER__", dark_vars["border"])
        .replace("__D_ACCENT__", dark_vars["accent"])
        .replace("__D_ACCENT_2__", dark_vars["accent_2"])
        .replace("__D_SHADOW__", dark_vars["shadow"])
        .replace("__D_UPLOADER_BG__", dark_vars["uploader_bg"])
    )
    st.markdown(css, unsafe_allow_html=True)


def page_header(title: str, subtitle: str, tag: str = "MAC-ADG"):
    st.markdown(
        f"""
<section class="hero">
  <div class="tag">{tag}</div>
  <h1>{title}</h1>
  <p>{subtitle}</p>
</section>
        """,
        unsafe_allow_html=True,
    )


def begin_card(title: str = "", subtitle: str = ""):
    st.markdown(
        f"""
<div class="card">
  {f'<div class="card-title">{title}</div>' if title else ''}
  {f'<div class="card-sub">{subtitle}</div>' if subtitle else ''}
        """,
        unsafe_allow_html=True,
    )


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def stat_grid(stats):
    parts = []
    for label, value in stats:
        parts.append(
            f"""
<div class="stat">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
</div>
            """
        )
    st.markdown(
        "<div class=\"stat-grid\">" + "".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


def render_sidebar():
    """渲染侧边栏控制中心并返回 UI 配置。"""
    if "ui_config" not in st.session_state:
        st.session_state.ui_config = {
            "layout_mode": "双栏",
            "show_stats": True,
            "show_quickstart": True,
            "show_shortcuts": True,
            "show_recent": True,
            "show_visual_panel": True,
            "show_semantic_panel": True,
            "show_ocr_text": True,
            "show_decision_chain": True,
            "show_log_stream": True,
            "show_memory_insight": True,
            "theme_mode": "auto",
        }

    with st.sidebar:
        st.markdown("### 控制中心")
        st.caption("系统配置与界面显示控制")

        st.markdown("**系统配置**")
        st.selectbox("OCR 引擎", ["PaddleOCR"], index=0, key="ui_ocr_engine")
        st.selectbox("解析模式", ["规则优先", "视觉优先"], index=0, key="ui_parse_mode")
        st.toggle("启用 RAG 记忆", value=True, key="ui_rag_enabled")
        st.toggle("保存 OCR Sidecar", value=True, key="ui_sidecar_enabled")

        st.divider()
        st.markdown("**界面显示**")
        current_mode = st.session_state.ui_config.get("theme_mode", "auto")
        if current_mode == "dark":
            theme_index = 2
        elif current_mode == "light":
            theme_index = 1
        else:
            theme_index = 0
        theme_label = st.selectbox(
            "界面主题",
            ["跟随系统", "浅色", "深色"],
            index=theme_index,
            key="ui_theme_label",
        )
        if theme_label == "深色":
            theme_mode = "dark"
        elif theme_label == "浅色":
            theme_mode = "light"
        else:
            theme_mode = "auto"
        st.session_state.ui_theme = theme_mode
        layout_mode = st.selectbox("布局模式", ["双栏", "单栏"], index=0, key="ui_layout_mode")
        show_stats = st.toggle("显示总览指标", value=True, key="ui_show_stats")
        show_quickstart = st.toggle("显示快速开始", value=True, key="ui_show_quickstart")
        show_shortcuts = st.toggle("显示快捷入口", value=True, key="ui_show_shortcuts")
        show_recent = st.toggle("显示最近处理", value=True, key="ui_show_recent")
        show_visual_panel = st.toggle("显示视觉证据区", value=True, key="ui_show_visual")
        show_semantic_panel = st.toggle("显示语义决策区", value=True, key="ui_show_semantic")
        show_ocr_text = st.toggle("显示 OCR 原文", value=True, key="ui_show_ocr")
        show_decision_chain = st.toggle("显示决策链路", value=True, key="ui_show_chain")
        show_log_stream = st.toggle("显示日志流", value=True, key="ui_show_logs")
        show_memory_insight = st.toggle("显示记忆提示", value=True, key="ui_show_memory")

        st.divider()
        st.markdown("**多智能体状态**")
        st.progress(0.85, text="Scout 连接")
        st.progress(0.72, text="Vision 识别")
        st.progress(0.64, text="Judge 仲裁")

    cfg = {
        "layout_mode": layout_mode,
        "show_stats": show_stats,
        "show_quickstart": show_quickstart,
        "show_shortcuts": show_shortcuts,
        "show_recent": show_recent,
        "show_visual_panel": show_visual_panel,
        "show_semantic_panel": show_semantic_panel,
        "show_ocr_text": show_ocr_text,
        "show_decision_chain": show_decision_chain,
        "show_log_stream": show_log_stream,
        "show_memory_insight": show_memory_insight,
        "rag_enabled": st.session_state.get("ui_rag_enabled", True),
        "theme_mode": theme_mode,
    }
    st.session_state.ui_config = cfg
    return cfg


def pdf_preview(file_path: str, width: int = 600):
    """Display an embedded PDF preview (if the browser supports it)."""
    if not file_path or not os.path.exists(file_path):
        st.warning("无法预览：文件不存在")
        return
    try:
        with open(file_path, "rb") as f:
            st.download_button("📄 打开 PDF", f, file_name=os.path.basename(file_path))
    except Exception as e:
        st.error(f"PDF 预览失败: {e}")


def labeled_progress(label: str):
    """Return a progress bar with a descriptive text element."""
    container = st.container()
    text = container.text(label)
    bar = container.progress(0)
    return text, bar

