import streamlit as st
import pandas as pd
from backend.orchestrator import Orchestrator
from database.connection import get_db
from database.models import Paper
from database.settings import get_duplicate_strategy, set_duplicate_strategy
from backend.utils.schemas import DuplicateStrategy
from backend.utils.rag_memory import build_layout_fingerprint, retrieve_memory_hints
from frontend.components import apply_theme, page_header, begin_card, end_card, render_sidebar

st.set_page_config(page_title="智能提取", page_icon="🚀", layout="wide")
ui_cfg = render_sidebar()
apply_theme(ui_cfg.get("theme_mode", "light"))
page_header(
    "智能提取流水线",
    "一键跑通 DOI 采集、视觉解析与裁决入库。",
    tag="MAC-ADG / 提取",
)

if "extraction_logs" not in st.session_state:
    st.session_state.extraction_logs = []
if "agent_logs" not in st.session_state:
    st.session_state.agent_logs = []
if "last_record" not in st.session_state:
    st.session_state.last_record = None
if "memory_hints" not in st.session_state:
    st.session_state.memory_hints = []


def _add_log(agent: str, message: str, confidence: float) -> None:
    st.session_state.agent_logs.append(
        {
            "agent": agent,
            "message": message,
            "confidence": float(confidence),
        }
    )


def _render_log_stream() -> None:
    if not st.session_state.agent_logs:
        st.info("暂无日志。执行一次流水线即可查看日志流。")
        return
    for item in st.session_state.agent_logs[-30:]:
        agent = item.get("agent", "")
        tag_class = "log-scout" if agent == "Scout" else "log-vision" if agent == "Vision" else "log-judge"
        st.markdown(
            f"""
<div class="log-item">
  <span class="log-tag {tag_class}">[{agent}]</span>
  <span>{item.get('message')}</span>
  <span class="log-conf">置信度 {item.get('confidence'):.2f}</span>
</div>
            """,
            unsafe_allow_html=True,
        )


def _compute_memory_hints(record: dict) -> list:
    if not isinstance(record, dict):
        return []
    vision_data = record.get("vision_data") or {}
    tokens = build_layout_fingerprint(vision_data)
    if not tokens:
        return []
    db = next(get_db())
    try:
        return retrieve_memory_hints(db, tokens)
    finally:
        db.close()


def _fetch_existing_dois(dois: list[str]) -> dict:
    if not dois:
        return {}
    db = next(get_db())
    try:
        papers = db.query(Paper).filter(Paper.doi.in_(dois)).all()
        return {
            p.doi: {
                "status": p.status,
                "title": p.title,
            }
            for p in papers
        }
    finally:
        db.close()


def _load_duplicate_strategy() -> DuplicateStrategy:
    db = next(get_db())
    try:
        return get_duplicate_strategy(db)
    finally:
        db.close()


def _save_duplicate_strategy(strategy: DuplicateStrategy) -> None:
    db = next(get_db())
    try:
        set_duplicate_strategy(db, strategy)
    finally:
        db.close()

begin_card("步骤 1 · 任务注入", "上传 DOI 列表并启动自动处理。")
uploaded_file = st.file_uploader("上传 DOI 列表（Excel/CSV）", type=["xlsx", "csv"])
end_card()

if uploaded_file:
    try:
        filename = str(getattr(uploaded_file, "name", "")).lower()
        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(
                    uploaded_file,
                    encoding="utf-8-sig",
                    sep=None,
                    engine="python",
                )
            except Exception:
                df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        else:
            df = pd.read_excel(uploaded_file)
        doi_col = next((col for col in df.columns if col.lower() == 'doi'), None)
        
        if not doi_col:
            st.error("❌ 错误：文件中未发现 'DOI' 列")
        else:
            dois = [str(r).strip() for r in df[doi_col].tolist() if str(r).strip()]
            st.info(f"✅ 识别到 {len(dois)} 个目标。")

            existing_map = _fetch_existing_dois(dois)
            existing_done = {
                doi: info
                for doi, info in existing_map.items()
                if info.get("status") in {"COMPLETED", "SKIPPED", "NEEDS_REVIEW"}
            }

            begin_card("步骤 2 · 执行流水线", "实时展示每条 DOI 的处理状态。")

            current_strategy = _load_duplicate_strategy()
            strategy_labels = {
                DuplicateStrategy.PROMPT: "每次询问",
                DuplicateStrategy.OVERWRITE: "总是重新识别",
                DuplicateStrategy.SKIP: "总是跳过",
            }
            label_to_strategy = {v: k for k, v in strategy_labels.items()}

            policy_label = st.selectbox(
                "重复 DOI 处理策略",
                list(label_to_strategy.keys()),
                index=list(label_to_strategy.keys()).index(strategy_labels[current_strategy]),
                key="reprocess_policy",
            )
            selected_strategy = label_to_strategy[policy_label]
            if selected_strategy != current_strategy:
                _save_duplicate_strategy(selected_strategy)
                current_strategy = selected_strategy

            choice = "本次跳过"
            remember = False

            has_existing_done = bool(existing_done)
            if has_existing_done:
                st.warning(f"检测到 {len(existing_done)} 个 DOI 已处理过")
                with st.expander("查看已处理 DOI"):
                    rows = [
                        {
                            "DOI": doi,
                            "状态": info.get("status"),
                            "标题": (info.get("title") or "")[:80],
                        }
                        for doi, info in existing_done.items()
                    ]
                    st.dataframe(rows, width="stretch")

                if current_strategy == DuplicateStrategy.PROMPT:
                    choice = st.radio(
                        "本次处理策略",
                        ["本次重新识别", "本次跳过"],
                        index=1,
                        key="reprocess_choice",
                    )
                    remember = st.checkbox("以后都选这个", key="reprocess_remember")
            if st.button("🚀 启动全自动流水线", type="primary"):
                orchestrator = Orchestrator()
                progress_bar = st.progress(0)
                status_box = st.empty()
                results = []
                table_placeholder = st.empty()

                total = len(dois)
                runtime_strategy = current_strategy
                if current_strategy == DuplicateStrategy.PROMPT and has_existing_done:
                    runtime_strategy = (
                        DuplicateStrategy.OVERWRITE if choice == "本次重新识别" else DuplicateStrategy.SKIP
                    )
                    _save_duplicate_strategy(runtime_strategy)

                try:
                    for idx, doi in enumerate(dois):
                        status_box.text(f"🌐 正在驱动浏览器处理：{doi} ...")
                        try:
                            record = orchestrator.process_dois([doi])[0]
                        except Exception as e:
                            # ✅ 添加错误处理：单个DOI失败不中断整个流程
                            record = {
                                "doi": doi,
                                "error": str(e),
                                "status": "error"
                            }
                            print(f"[Orchestrator Error] {doi}: {e}")

                        # --- 更新状态映射逻辑 (适配 Web GUI Agent) ---
                        gui_status = "❌ 失败"
                        
                        # 优先判断是否发生了错误
                        if record.get("error"):
                            gui_status = "❌ 错误"
                        elif record.get("screenshot_status") == "BLOCKED_OR_FAILED":
                            gui_status = "⚠️ 截图失败"
                        elif isinstance(record.get("vision_data"), dict) and record.get("vision_data").get("ocr_failed"):
                            gui_status = "⚠️ OCR失败"
                        # 优先判断 Vision 是否成功截取了网页图片
                        elif record.get("screenshot_path") or record.get("image_path"):
                            gui_status = "📸 网页已截图"
                        # 如果没截到图，但 Scout 成功获取了元数据
                        elif record.get("status") == "metadata_ready":
                            gui_status = "⚠️ 仅元数据"
                            
                        record["状态"] = gui_status
                        
                        # 简化视觉提取结果的展示
                        vlm_text = ""
                        if isinstance(record.get("vision_data"), dict):
                            vlm_text = str(record.get("vision_data", {}).get("text") or "")
                        record["视觉解析"] = "有结果" if len(vlm_text) > 5 else "无"

                        results.append(record)
                        progress_bar.progress((idx + 1) / total)

                        # --- 动态刷新表格 ---
                        current_df = pd.DataFrame(results)
                        cols = ["doi", "title", "journal", "状态", "视觉解析"]
                        valid_cols = [c for c in cols if c in current_df.columns]
                        display_df = current_df[valid_cols].rename(
                            columns={
                                "doi": "DOI",
                                "title": "标题",
                                "journal": "期刊",
                            }
                        )
                        table_placeholder.dataframe(display_df, width="stretch")

                        scout_conf = 0.9 if record.get("title") else 0.6
                        vision_conf = 0.85 if record.get("vision_authors") else 0.55
                        judge_conf = 0.9 if record.get("status") == "COMPLETED" else 0.65
                        _add_log("Scout", f"完成元数据抓取：{doi}", scout_conf)
                        _add_log("Vision", "完成 OCR 解析与作者识别", vision_conf)
                        _add_log("Judge", f"完成裁决：{record.get('status', 'UNKNOWN')}", judge_conf)

                finally:
                    if current_strategy == DuplicateStrategy.PROMPT and has_existing_done and not remember:
                        _save_duplicate_strategy(DuplicateStrategy.PROMPT)

                status_box.success("✅ 全流程执行完毕！网页截图已存入 visual_slices，数据已写入数据库。")
                st.session_state.last_record = results[-1] if results else None
                if results:
                    st.session_state.memory_hints = _compute_memory_hints(st.session_state.last_record)
                else:
                    st.session_state.memory_hints = []
            end_card()
                
    except Exception as e:
        st.error(f"错误：{e}")
else:
    st.warning("等待上传文件...")

st.divider()
# 视觉-语义对齐区：左图右表
begin_card("视觉-语义对齐", "左侧核验视觉证据，右侧查看结构化结果。")
record = st.session_state.last_record

def _render_visual_panel() -> None:
    st.markdown("**证据感知区（视觉）**")
    if not ui_cfg.get("show_visual_panel", True):
        st.info("视觉证据区已在侧边栏关闭。")
        return
    if isinstance(record, dict):
        screenshot_path = record.get("screenshot_path") or record.get("image_path")
        if screenshot_path:
            st.image(screenshot_path, width="stretch")
        else:
            st.info("暂无截图，请先运行流程。")
        if ui_cfg.get("show_ocr_text", True):
            ocr_text = ""
            if record.get("vision_data"):
                ocr_text = str(record.get("vision_data", {}).get("text") or "")
            if ocr_text:
                st.markdown("**OCR 原始文本**")
                st.code(ocr_text)
    else:
        st.info("暂无数据。")


def _render_semantic_panel() -> None:
    st.markdown("**决策提取区（语义）**")
    if not ui_cfg.get("show_semantic_panel", True):
        st.info("语义决策区已在侧边栏关闭。")
        return
    authors = []
    if isinstance(record, dict):
        authors = record.get("vision_authors") or record.get("authors") or []
    if authors:
        df = pd.DataFrame(authors)
        df = df.rename(
            columns={
                "name": "作者",
                "affiliation": "单位",
                "is_corresponding": "通讯",
                "is_co_first": "共一",
            }
        )
        keep_cols = [c for c in ["作者", "单位", "通讯", "共一"] if c in df.columns]
        st.dataframe(df[keep_cols], width="stretch")
    else:
        st.info("暂无结构化作者数据。")

    if ui_cfg.get("show_decision_chain", True):
        with st.status("Orchestrator 决策链路", expanded=True):
            st.write("1. 侦察：抓取 Crossref 元数据")
            st.write("2. 视觉：网页截图 + OCR")
            st.write("3. 仲裁：融合证据，判定通讯/共一")
            st.write("4. 入库：写入论文与作者记录")

    if ui_cfg.get("show_memory_insight", True):
        if st.session_state.memory_hints and ui_cfg.get("rag_enabled", True):
            st.markdown("🧠 **RAG 记忆已启发本次解析**")
            with st.expander("查看匹配的历史案例指纹"):
                for hint in st.session_state.memory_hints:
                    st.write(
                        f"- 命中 {hint.get('error_type')} | 相似度 {hint.get('score'):.2f}"
                    )
        else:
            st.caption("未命中历史记忆。")
end_card()

if ui_cfg.get("layout_mode") == "单栏":
    _render_visual_panel()
    _render_semantic_panel()
else:
    left, right = st.columns([1.1, 1])
    with left:
        _render_visual_panel()
    with right:
        _render_semantic_panel()

if ui_cfg.get("show_log_stream", True):
    begin_card("智能体日志流", "展示 Scout / Vision / Judge 的执行轨迹与置信度。")
    _render_log_stream()
    end_card()
