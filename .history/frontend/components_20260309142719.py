# UI 组件库 (上传框、进度条等)

import streamlit as st
import os


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

