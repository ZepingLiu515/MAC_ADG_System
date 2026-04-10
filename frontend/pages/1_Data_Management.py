import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty
from backend.utils.excel_parser import parse_faculty_list
from frontend.components import apply_theme, page_header, begin_card, end_card, stat_grid, render_sidebar

# Page Configuration
st.set_page_config(page_title="数据管理", page_icon="📂", layout="wide")
ui_cfg = render_sidebar()
apply_theme(ui_cfg.get("theme_mode", "light"))
page_header(
    "数据管理中心",
    "维护教师名单与本地文献库，让后续匹配更稳更准。",
    tag="MAC-ADG / 数据",
)

db: Session = next(get_db())
total_faculty = db.query(Faculty).count()
with_dept = db.query(Faculty).filter(Faculty.department.isnot(None)).count()
db.close()

stat_grid(
    [
        ("教师条目", total_faculty),
        ("含单位信息", with_dept),
        ("待导入", "0"),
    ]
)

# Create Tabs
tab1, tab2 = st.tabs(["👨‍🏫 教师名单管理", "📚 本地文献库"])

# --- Tab 1: Faculty List Management ---
with tab1:
    begin_card("教师名单上传", "上传 Excel 名单并同步到本地数据库。")
    st.info("💡 必填列：**Name**、**Department**（ID 可选）")

    uploaded_file = st.file_uploader("上传教师名单（Excel/CSV）", type=["xlsx", "csv"])

    if uploaded_file:
        data_list, error_msg = parse_faculty_list(uploaded_file)

        if error_msg:
            st.error(error_msg)
        else:
            st.success(f"解析成功！识别到 {len(data_list)} 位教师。")
            preview_df = pd.DataFrame(data_list)
            preview_df = preview_df.rename(
                columns={
                    "name_zh": "姓名",
                    "employee_id": "工号",
                    "department": "单位",
                    "name_en_list": "英文名",
                }
            )
            st.dataframe(preview_df.head(5), width="stretch")

            if st.button("🚀 确认并写入数据库", type="primary"):
                db: Session = next(get_db())
                try:
                    progress_bar = st.progress(0)
                    added_count = 0

                    for i, item in enumerate(data_list):
                        exists = db.query(Faculty).filter(Faculty.employee_id == item["employee_id"]).first()
                        if not exists:
                            new_faculty = Faculty(**item)
                            db.add(new_faculty)
                            added_count += 1
                        progress_bar.progress((i + 1) / len(data_list))

                    db.commit()
                    st.success(
                        f"✅ 写入完成！新增 {added_count} 条，跳过 {len(data_list) - added_count} 条重复记录。"
                    )
                except Exception as e:
                    db.rollback()
                    st.error(f"数据库错误：{str(e)}")
                finally:
                    db.close()
    end_card()

    st.divider()
    begin_card("数据预览", "查看最新的教师条目。")
    db: Session = next(get_db())
    try:
        current_faculty = db.query(Faculty).limit(10).all()
        if current_faculty:
            display_data = [
                {"姓名": f.name_zh, "工号": f.employee_id, "单位": f.department}
                for f in current_faculty
            ]
            st.table(display_data)
            st.caption("仅显示前 10 条记录。")
        else:
            st.warning("数据库为空，请先上传名单。")
    finally:
        db.close()
    end_card()

# --- Tab 2: Library Management (Placeholder) ---
with tab2:
    begin_card("本地文献库", "后续将管理 data/pdfs 下的文件。")
    st.write("该模块用于管理已缓存的 PDF 与附件。")
    end_card()
