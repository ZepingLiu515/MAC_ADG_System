import os
import json
from typing import Optional
import streamlit as st
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Paper, PaperAuthor, Faculty
from frontend.components import apply_theme, page_header, begin_card, end_card, stat_grid, render_sidebar

st.set_page_config(
    page_title="系统概览",
    page_icon="🏠",
    layout="wide",
)

ui_cfg = render_sidebar()
apply_theme(ui_cfg.get("theme_mode", "light"))
page_header(
    "MAC-ADG 科研成果治理系统",
    "多智能体驱动的科研成果采集、审核与统计平台。",
    tag="MAC-ADG / 概览",
)

# 基础指标概览
db: Session = next(get_db())
total_papers = db.query(Paper).count()
total_authors = db.query(PaperAuthor).count()
completed = db.query(Paper).filter(Paper.status == "COMPLETED").count()
needs_review = db.query(Paper).filter(Paper.status == "NEEDS_REVIEW").count()
total_faculty = db.query(Faculty).count()
recent_papers = db.query(Paper).order_by(Paper.created_at.desc()).limit(5).all()
db.close()

if ui_cfg.get("show_stats", True):
    stat_grid(
        [
            ("论文总数", total_papers),
            ("作者条目", total_authors),
            ("已完成", completed),
            ("待复核", needs_review),
            ("教师库", total_faculty),
        ]
    )


def _find_latest_screenshot() -> Optional[str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.join(base_dir, "data", "visual_slices")
    if not os.path.exists(root):
        return None
    candidates = [
        os.path.join(root, f)
        for f in os.listdir(root)
        if f.endswith(".png") and not f.endswith("_blocked.png")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def _load_sidecar_text(image_path: str) -> str:
    base = os.path.splitext(os.path.basename(image_path))[0]
    sidecar = os.path.join(os.path.dirname(image_path), f"{base}_ocr_sidecar.json")
    if not os.path.exists(sidecar):
        return ""
    try:
        with open(sidecar, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("ocr_text") or "")
    except Exception:
        return ""


def _render_visual_panel() -> None:
    if not ui_cfg.get("show_visual_panel", True):
        return
    begin_card("证据感知区（视觉）", "展示 OCR 截图与原始文本，便于人工核验。")
    screenshot = _find_latest_screenshot()
    if screenshot:
        st.image(screenshot, caption="最新截图", width="stretch")
        if ui_cfg.get("show_ocr_text", True):
            ocr_text = _load_sidecar_text(screenshot)
            if ocr_text:
                st.markdown("**OCR 原始文本**")
                st.code(ocr_text[:1200])
    else:
        st.info("暂无截图记录，请先运行智能提取。")
    end_card()


def _render_semantic_panel() -> None:
    if not ui_cfg.get("show_semantic_panel", True):
        return
    begin_card("决策提取区（语义）", "结构化结果与决策链路展示。")
    if recent_papers:
        latest = recent_papers[0]
        st.markdown(f"**当前论文**：{latest.doi}")
        if latest.title:
            st.markdown(f"**题名**：{latest.title[:80]}")
        st.markdown(f"**状态**：{latest.status}")
    else:
        st.info("暂无论文记录。")

    if ui_cfg.get("show_decision_chain", True):
        with st.status("Orchestrator 决策链路", expanded=True):
            st.write("1. 侦察：抓取 Crossref 元数据")
            st.write("2. 视觉：网页截图 + OCR")
            st.write("3. 仲裁：融合证据，判定通讯/共一")
            st.write("4. 入库：写入论文与作者记录")
    end_card()


if ui_cfg.get("layout_mode") == "单栏":
    _render_visual_panel()
    _render_semantic_panel()
else:
    col_left, col_right = st.columns([1.2, 1])
    with col_left:
        _render_visual_panel()
    with col_right:
        _render_semantic_panel()

if ui_cfg.get("show_quickstart", True):
    begin_card("快速开始", "按照下面顺序走完一次完整流程。")
    st.markdown(
        """
1. **数据管理**：上传教师名单，确认学院/部门字段完整。
2. **智能提取**：导入 DOI 列表，执行自动流水线。
3. **统计报表**：查看匹配结果，导出学院统计报表。
        """
    )
    st.markdown("提示：如果页面访问受限，系统会保留截图缓存供后续复核。")
    end_card()

if ui_cfg.get("show_shortcuts", True):
    begin_card("快捷入口", "点击按钮直达对应模块。")

    def _nav_button(label: str, target: str) -> None:
        if st.button(label, width="stretch"):
            try:
                st.switch_page(target)
            except Exception:
                st.info("请通过左侧导航栏进入对应模块。")

    _nav_button("📂 数据管理", "frontend/pages/1_Data_Management.py")
    _nav_button("🚀 智能提取", "frontend/pages/2_Smart_Extraction.py")
    _nav_button("📊 统计报表", "frontend/pages/3_Analytics_Reports.py")
    end_card()

if ui_cfg.get("show_recent", True):
    begin_card("最近处理", "最近 5 条任务状态概览。")
    if recent_papers:
        rows = [
            {
                "DOI": p.doi,
                "状态": p.status,
                "标题": (p.title or "")[:60],
            }
            for p in recent_papers
        ]
        st.dataframe(rows, width="stretch")
    else:
        st.info("暂无记录。请先运行智能提取。")
    end_card()
