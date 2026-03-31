import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty
from backend.utils.excel_parser import parse_faculty_list

# Page Configuration
st.set_page_config(page_title="Data Management", page_icon="📂", layout="wide")

st.title("📂 Data Management Center")
st.markdown("Upload faculty list or manage local document library.")

# Create Tabs
tab1, tab2 = st.tabs(["👨‍🏫 Faculty List Management", "📚 Local Library Management"])

# --- Tab 1: Faculty List Management ---
with tab1:
    st.info("💡 Please upload .xlsx file. Required columns: **Name**, **ID**, **Department**")
    
    # 1. File Uploader
    uploaded_file = st.file_uploader("Upload Faculty List (Excel)", type=["xlsx"])
    
    if uploaded_file:
        # 2. Call parser
        data_list, error_msg = parse_faculty_list(uploaded_file)
        
        if error_msg:
            st.error(error_msg)
        else:
            st.success(f"Parsing successful! Identified {len(data_list)} faculty members.")
            
            # 3. Preview Data
            preview_df = pd.DataFrame(data_list)
            st.dataframe(preview_df.head(5), use_container_width=True)
            
            # 4. Confirm to Database
            if st.button("🚀 Confirm & Save to Database", type="primary"):
                db: Session = next(get_db())
                try:
                    progress_bar = st.progress(0)
                    added_count = 0
                    
                    for i, item in enumerate(data_list):
                        # Check if ID already exists to prevent duplicates
                        exists = db.query(Faculty).filter(Faculty.employee_id == item["employee_id"]).first()
                        if not exists:
                            new_faculty = Faculty(**item)
                            db.add(new_faculty)
                            added_count += 1
                        
                        # Update progress bar
                        progress_bar.progress((i + 1) / len(data_list))
                    
                    db.commit()
                    st.success(f"✅ Completed! Added {added_count} new records. Skipped {len(data_list) - added_count} duplicates.")
                    
                except Exception as e:
                    db.rollback()
                    st.error(f"Database Error: {str(e)}")
                finally:
                    db.close()

    st.divider()
    
    # 5. View Existing Data
    st.subheader("📊 Current Database Preview")
    db: Session = next(get_db())
    try:
        current_faculty = db.query(Faculty).limit(10).all()
        if current_faculty:
            # Convert to list of dicts for display
            display_data = [{"Name": f.name_zh, "ID": f.employee_id, "Department": f.department} for f in current_faculty]
            st.table(display_data)
            st.caption(f"Showing first 10 records only.")
        else:
            st.warning("Database is empty. Please upload data.")
    finally:
        db.close()

# --- Tab 2: Library Management (Placeholder) ---
with tab2:
    st.write("This module will manage files in `data/pdfs/` after Scout Agent development.")