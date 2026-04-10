import hashlib
import json

import pandas as pd

def parse_faculty_list(uploaded_file):
    """Parse the Faculty list file (Excel/CSV).

    Required columns: Name, Department
    Optional column: ID (employee_id). If missing or blank, a fallback ID is generated.
    """
    try:
        # Read Excel/CSV, force ID column to string to preserve leading zeros
        filename = ""
        if isinstance(uploaded_file, str):
            filename = uploaded_file.lower()
        else:
            filename = str(getattr(uploaded_file, "name", "")).lower()

        if filename.endswith(".csv"):
            try:
                df = pd.read_csv(
                    uploaded_file,
                    dtype={"ID": str},
                    encoding="utf-8-sig",
                    sep=None,
                    engine="python",
                )
            except Exception:
                df = pd.read_csv(uploaded_file, dtype={"ID": str}, encoding="utf-8-sig")
        else:
            df = pd.read_excel(uploaded_file, dtype={"ID": str})
        
        # Standardize column check
        # NOTE: The file MUST have these English headers
        required_columns = ["Name", "Department"]
        for col in required_columns:
            if col not in df.columns:
                return None, f"Error: Missing required column '{col}'. Please check the Excel/CSV header."

        has_id_column = "ID" in df.columns
        used_ids = set()

        faculty_data = []
        
        for idx, row in df.iterrows():
            # 1. Get basic info
            name_zh = str(row["Name"]).strip()
            dept = str(row["Department"]).strip()

            emp_id = ""
            if has_id_column:
                emp_id = str(row["ID"]).strip()
                if emp_id.lower() == "nan":
                    emp_id = ""

            if not emp_id:
                base = hashlib.md5(f"{name_zh}|{dept}".encode("utf-8")).hexdigest()[:8]
                emp_id = f"gen_{base}"
                suffix = 1
                while emp_id in used_ids:
                    emp_id = f"gen_{base}_{suffix}"
                    suffix += 1
            used_ids.add(emp_id)
            
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