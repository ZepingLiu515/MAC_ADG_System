import streamlit as st
import pandas as pd
from backend.orchestrator import Orchestrator

# we'll reuse the orchestrator to keep pipeline logic in one place

st.set_page_config(page_title="Agent Console", page_icon="🤖", layout="wide")

st.title("🤖 智能体工作台 (Agent Console)")
st.markdown("全自动流水线：侦察 (Scout) -> 视觉 (Vision) -> 裁决 (Judge)")

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

                # convert dataframe to list of DOIs allowing empty rows
                dois = [str(r).strip() for r in df[doi_col].tolist() if str(r).strip()]
                total = len(dois)

                for idx, doi in enumerate(dois):
                    status_box.text(f"正在处理: {doi} ...")
                    record = orchestrator.process_dois([doi])[0]

                    # map status to nice label for display
                    raw_status = record.get("status", "failed")
                    gui_status = "❌ 失败"
                    if raw_status == "success_pdf": gui_status = "✅ PDF"
                    elif raw_status == "success_html": gui_status = "📄 HTML"
                    elif raw_status == "metadata_only": gui_status = "⚠️ Meta"
                    record["状态"] = gui_status

                    results.append(record)
                    progress_bar.progress((idx + 1) / total)

                    current_df = pd.DataFrame(results)
                    cols = ["doi", "title", "journal", "状态", "vision_text_length"]
                    valid_cols = [c for c in cols if c in current_df.columns]
                    table_placeholder.dataframe(current_df[valid_cols], use_container_width=True)

                status_box.success(f"✅ 全流程执行完毕！数据已写入数据库。")
                
    except Exception as e:
        st.error(f"Error: {e}")