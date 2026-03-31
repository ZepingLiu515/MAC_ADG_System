import pandas as pd
import json

def parse_faculty_list(uploaded_file):
    """
    Function: Parse the Faculty List Excel uploaded by user.
    Input: Streamlit uploaded file object.
    Output: List of dictionaries corresponding to the Faculty model.
    """
    try:
        # Read Excel, force ID column to string to preserve leading zeros
        df = pd.read_excel(uploaded_file, dtype={"ID": str})
        
        # Standardize column check
        # NOTE: The Excel file MUST have these English headers
        required_columns = ["Name", "ID", "Department"]
        for col in required_columns:
            if col not in df.columns:
                return None, f"Error: Missing required column '{col}'. Please check the Excel header."

        faculty_data = []
        
        for _, row in df.iterrows():
            # 1. Get basic info
            name_zh = str(row["Name"]).strip()
            emp_id = str(row["ID"]).strip()
            dept = str(row["Department"]).strip()
            
            # 2. Generate English name variants (Placeholder for now)
            # e.g. "Liu Zeping" -> ["Zeping Liu", "Z.P. Liu"]
            name_en_list = generate_name_variants(name_zh)
            
            # 3. Construct dictionary for Faculty model
            faculty_data.append({
                "employee_id": emp_id,
                "name_zh": name_zh,
                "name_en_list": json.dumps(name_en_list), # Store as JSON string
                "department": dept
            })
            
        return faculty_data, None

    except Exception as e:
        return None, f"Unknown error during parsing: {str(e)}"

def generate_name_variants(name_str):
    """Generate plausible English name variants from a Chinese full name.

    Attempts to use ``pypinyin`` if available to convert characters to pinyin.
    Fallback returns an empty list (the JudgeAgent will still match on
    Chinese name).  Examples produced:
        刘泽萍 -> ['Zeping Liu', 'L. Zeping']
    """
    variants = []
    try:
        from pypinyin import lazy_pinyin
        parts = lazy_pinyin(name_str)
        if parts:
            # assume last syllable is family name
            family = parts[0].capitalize()
            given = " ".join(p.capitalize() for p in parts[1:])
            if given:
                variants.append(f"{given} {family}")
                initials = " ".join(p[0].upper() + "." for p in parts[1:])
                variants.append(f"{initials} {family}")
    except ImportError:
        # pypinyin not installed; variants stay empty
        pass
    return variants