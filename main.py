import streamlit as st

st.set_page_config(
    page_title="MAC-ADG 科研成果治理系统",
    page_icon="🎓",
    layout="wide",
)

with st.sidebar:
    st.markdown("### ⧉ LOGO")
    st.caption("MAC-ADG | 多智能体协同文档治理")

page_home = st.Page("frontend/pages/home.py", title="系统概览", icon=":material/home:")
page_data = st.Page("frontend/pages/1_Data_Management.py", title="数据管理", icon=":material/storage:")
page_extract = st.Page("frontend/pages/2_Smart_Extraction.py", title="智能感知提取", icon=":material/auto_awesome:")
page_report = st.Page("frontend/pages/3_Analytics_Reports.py", title="统计决策报表", icon=":material/analytics:")

nav = st.navigation(
    [page_home, page_data, page_extract, page_report],
    position="sidebar",
)
nav.run()
