import streamlit as st
import pandas as pd
from backend.orchestrator import Orchestrator

st.set_page_config(page_title="Agent Console", page_icon="🤖", layout="wide")

st.title("🤖 智能体工作台 (Agent Console)")
st.markdown("全自动流水线：侦察 (Scout API) -> 视觉 (Vision GUI Screenshot) -> 裁决 (Judge DB)")

if "extraction_logs" not in st.session_state:
    st.session_state.extraction_logs = []

st.subheader("1. 任务注入")
uploaded_file = st.file_uploader("请上传包含 DOI 的任务列表", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        doi_col = next((col for col in df.columns if col.lower() == 'doi'), None)
        
        if not doi_col:
            st.error("❌ 错误：文件中未发现 'DOI' 列")
        else:
            st.info(f"✅ 识别到 {len(df)} 个目标。")
            
            if st.button("🚀 启动全自动流水线 (Start Pipeline)", type="primary"):
                orchestrator = Orchestrator()
                progress_bar = st.progress(0)
                status_box = st.empty()
                results = []
                table_placeholder = st.empty()

                # Convert dataframe to list of DOIs allowing empty rows
                dois = [str(r).strip() for r in df[doi_col].tolist() if str(r).strip()]
                total = len(dois)

                for idx, doi in enumerate(dois):
                    status_box.text(f"🌐 正在驱动浏览器处理: {doi} ...")
                    record = orchestrator.process_dois([doi])[0]

                    # --- 更新状态映射逻辑 (适配 Web GUI Agent) ---
                    gui_status = "❌ 失败"
                    
                    # 优先判断 Vision 是否成功截取了网页图片
                    if record.get("image_path"):
                        gui_status = "📸 网页已截图"
                    # 如果没截到图，但 Scout 成功获取了元数据
                    elif record.get("status") == "metadata_ready":
                        gui_status = "⚠️ 仅元数据"
                        
                    record["状态"] = gui_status
                    
                    # 简化视觉提取结果的展示
                    vlm_text = record.get("text", "")
                    record["VLM分析"] = "有结果" if len(vlm_text) > 5 else "无"

                    results.append(record)
                    progress_bar.progress((idx + 1) / total)

                    # --- 动态刷新表格 ---
                    current_df = pd.DataFrame(results)
                    cols = ["doi", "title", "journal", "状态", "VLM分析"]
                    valid_cols = [c for c in cols if c in current_df.columns]
                    table_placeholder.dataframe(current_df[valid_cols], use_container_width=True)

                status_box.success("✅ 全流程执行完毕！网页截图已存入 visual_slices，数据已写入数据库。")
                
    except Exception as e:
        st.error(f"Error: {e}")