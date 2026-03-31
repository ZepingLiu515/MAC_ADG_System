import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Paper, Faculty, PaperAuthor

# Page Config
st.set_page_config(page_title="Analytics Reports", page_icon="📊", layout="wide")

st.title("📊 Research Analytics Dashboard")
st.markdown("Review extracted data, analyze faculty contributions, and export final reports.")

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
st.subheader("1. Overview")

col1, col2, col3 = st.columns(3)

# Metric 1: Total Matched Papers (Unique DOIs)
total_papers = df["DOI"].nunique() if not df.empty else 0
col1.metric("📚 Total Matched Papers", total_papers)

# Metric 2: Contributing Faculty (Unique IDs)
total_faculty = df["Employee ID"].nunique() if not df.empty else 0
col2.metric("👨‍🏫 Contributing Faculty", total_faculty)

# Metric 3: Department Coverage
top_dept = df["Department"].mode()[0] if not df.empty else "N/A"
col3.metric("🏆 Top Department", top_dept)

st.divider()

# --- Section 2: Detailed Data View ---
st.subheader("2. Detailed Match Records")

if df.empty:
    st.info("ℹ️ No matches found yet. Please run the 'Smart Extraction' pipeline first.")
else:
    # Interactive Filters
    selected_dept = st.multiselect(
        "Filter by Department:", 
        options=df["Department"].unique(),
        default=df["Department"].unique()
    )
    
    # Apply Filter
    filtered_df = df[df["Department"].isin(selected_dept)]
    
    # Show Table
    st.dataframe(
        filtered_df,
        use_container_width=True,
        column_config={
            "DOI": st.column_config.TextColumn("DOI", help="Paper Unique ID"),
            "Title": st.column_config.TextColumn("Paper Title", width="large"),
            "Faculty Name": st.column_config.TextColumn("Matched Faculty", width="medium"),
        },
        hide_index=True
    )

    # --- Section 3: Visualization ---
    st.divider()
    st.subheader("3. Contribution Analysis")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.caption("Papers by Department")
        if not filtered_df.empty:
            dept_counts = filtered_df["Department"].value_counts()
            st.bar_chart(dept_counts)
            
    with col_chart2:
        st.caption("Top 5 Active Faculty")
        if not filtered_df.empty:
            faculty_counts = filtered_df["Faculty Name"].value_counts().head(5)
            st.bar_chart(faculty_counts)

    # --- Section 4: Final Export ---
    st.divider()
    st.subheader("4. Export Report")
    
    st.write("Download the cleaned data for official submission.")
    
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Final Report (CSV)",
        data=csv,
        file_name="final_faculty_research_report.csv",
        mime="text/csv",
        type="primary"
    )