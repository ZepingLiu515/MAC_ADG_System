import streamlit as st
import pandas as pd
import os
from backend.orchestrator import Orchestrator

# Page Config
st.set_page_config(page_title="Smart Extraction", page_icon="🚀", layout="wide")

st.title("🚀 Smart Document Extraction Pipeline")
st.markdown("Batch process DOIs to extract metadata and download PDFs.")

# Initialize Session State for logs
if "extraction_logs" not in st.session_state:
    st.session_state.extraction_logs = []

# --- Step 1: Upload DOI List ---
st.subheader("1. Upload Task")
st.info("💡 Please upload .xlsx file. Required column: **DOI**")

uploaded_file = st.file_uploader("Upload DOI List (Excel)", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Validate Column
        # We allow 'DOI', 'doi', or 'Doi'
        doi_col = None
        for col in df.columns:
            if col.lower() == 'doi':
                doi_col = col
                break
        
        if not doi_col:
            st.error("❌ Error: Excel must contain a 'DOI' column.")
        else:
            st.success(f"✅ Loaded {len(df)} DOIs.")
            st.dataframe(df.head(), use_container_width=True)
            
            # --- Step 2: Run Extraction ---
            st.divider()
            st.subheader("2. Execute Agents")
            
            if st.button("🚀 Start Extraction Agent", type="primary"):
                orchestrator = Orchestrator()
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []
                dois = [str(r).strip() for r in df[doi_col].tolist() if str(r).strip()]
                total = len(dois)
                table_placeholder = st.empty()

                for idx, doi in enumerate(dois):
                    status_text.text(f"🕵️ Scout Agent is processing: {doi} ...")
                    record = orchestrator.process_dois([doi])[0]
                    results.append(record)
                    progress_bar.progress((idx + 1) / total)
                    current_df = pd.DataFrame(results)
                    table_placeholder.dataframe(current_df, use_container_width=True)

                status_text.text("✅ All tasks completed!")
                st.balloons()
                
                # --- Step 3: Export Results ---
                st.divider()
                st.subheader("3. Export Data")
                
                final_df = pd.DataFrame(results)
                
                # Convert to CSV for download
                csv = final_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Result CSV",
                    data=csv,
                    file_name="extraction_results.csv",
                    mime="text/csv",
                )
                
    except Exception as e:
        st.error(f"Error reading file: {e}")

else:
    st.warning("Waiting for file upload...")