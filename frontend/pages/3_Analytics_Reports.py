import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Paper, Faculty, PaperAuthor
from frontend.components import apply_theme, page_header, begin_card, end_card, render_sidebar

st.set_page_config(page_title="统计报表", page_icon="📊", layout="wide")
ui_cfg = render_sidebar()
apply_theme(ui_cfg.get("theme_mode", "light"))
page_header(
    "统计报表中心",
    "查看匹配结果、分析贡献度并导出最终报表。",
    tag="MAC-ADG / 报表",
)

# 1. Fetch Data from Database
db: Session = next(get_db())

# Join Query: Paper <-> PaperAuthor <-> Faculty
# We want to see: Which Paper was written by Which Faculty from Which Department
results = db.query(
    Paper.doi,
    Paper.title,
    Paper.journal,
    Paper.publish_date,
    Faculty.name_zh,
    Faculty.employee_id,
    Faculty.department,
    PaperAuthor.rank
).join(PaperAuthor, Paper.doi == PaperAuthor.paper_doi)\
 .join(Faculty, PaperAuthor.matched_faculty_id == Faculty.id)\
 .all()

db.close()

# Convert to DataFrame
if results:
    df = pd.DataFrame(results, columns=[
        "DOI", "Title", "Journal", "Date", 
        "Faculty Name", "Employee ID", "Department", "Author Rank"
    ])
else:
    df = pd.DataFrame()

# --- Section 1: KPI Cards ---
st.subheader("1. 总览")

col1, col2, col3 = st.columns(3)

# Metric 1: Total Matched Papers (Unique DOIs)
total_papers = df["DOI"].nunique() if not df.empty else 0
col1.metric("📚 匹配论文数", total_papers)

# Metric 2: Contributing Faculty (Unique IDs)
total_faculty = df["Employee ID"].nunique() if not df.empty else 0
col2.metric("👨‍🏫 贡献教师数", total_faculty)

# Metric 3: Department Coverage
top_dept = df["Department"].mode()[0] if not df.empty else "N/A"
col3.metric("🏆 最高频单位", top_dept)

st.divider()

# --- Section 2: Detailed Data View ---
st.subheader("2. 匹配详情")

if df.empty:
    st.info("ℹ️ 暂无匹配记录，请先运行“智能提取”流程。")
else:
    # Interactive Filters
    selected_dept = st.multiselect(
        "按单位筛选：",
        options=df["Department"].unique(),
        default=df["Department"].unique()
    )
    
    # Apply Filter
    filtered_df = df[df["Department"].isin(selected_dept)]
    
    # Show Table
    st.dataframe(
        filtered_df,
        width="stretch",
        column_config={
            "DOI": st.column_config.TextColumn("DOI", help="论文唯一标识"),
            "Title": st.column_config.TextColumn("论文题名", width="large"),
            "Faculty Name": st.column_config.TextColumn("匹配教师", width="medium"),
            "Journal": st.column_config.TextColumn("期刊"),
            "Date": st.column_config.TextColumn("发表时间"),
            "Department": st.column_config.TextColumn("单位"),
            "Author Rank": st.column_config.NumberColumn("作者顺序"),
        },
        hide_index=True
    )

    # --- Section 3: Visualization ---
    st.divider()
    st.subheader("3. 贡献度分析")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.caption("按单位统计论文数量")
        if not filtered_df.empty:
            dept_counts = filtered_df["Department"].value_counts()
            st.bar_chart(dept_counts)
            
    with col_chart2:
        st.caption("Top 5 活跃教师")
        if not filtered_df.empty:
            faculty_counts = filtered_df["Faculty Name"].value_counts().head(5)
            st.bar_chart(faculty_counts)

    # --- Section 4: Final Export ---
    st.divider()
    st.subheader("4. 导出报表")
    st.write("导出清洗后的数据用于最终报送。")
    
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 下载最终报表（CSV）",
        data=csv,
        file_name="final_faculty_research_report.csv",
        mime="text/csv",
        type="primary"
    )
