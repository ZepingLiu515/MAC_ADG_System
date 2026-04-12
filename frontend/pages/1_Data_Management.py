import streamlit as st
import pandas as pd
import re
from typing import List, Optional
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
tab1, tab2 = st.tabs(["教师名单管理", "本地文献库"])

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

            if st.button("确认并写入数据库", type="primary"):
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
                        f"√ 写入完成！新增 {added_count} 条，跳过 {len(data_list) - added_count} 条重复记录。"
                    )
                except Exception as e:
                    db.rollback()
                    st.error(f"数据库错误：{str(e)}")
                finally:
                    db.close()
    end_card()

    st.divider()
    begin_card("职工信息维护", "支持按条件查询、手动新增、编辑与删除教师记录。")

    def _norm_empty(v: str) -> str:
        return str(v or "").strip()

    def _empty_to_none(v: str) -> Optional[str]:
        s = _norm_empty(v)
        return s if s else None

    def _parse_list_text(v: str) -> Optional[List[str]]:
        s = _norm_empty(v)
        if not s:
            return None
        parts = re.split(r"[\n,;，；\|/]+", s)
        cleaned = [p.strip() for p in parts if p and p.strip()]
        return cleaned or None

    col_q1, col_q2, col_q3, col_q4 = st.columns([2, 2, 3, 1])
    with col_q1:
        q_name = st.text_input("姓名包含", value=st.session_state.get("faculty_q_name", ""), key="faculty_q_name")
    with col_q2:
        q_emp = st.text_input("工号（精确）", value=st.session_state.get("faculty_q_emp", ""), key="faculty_q_emp")
    with col_q3:
        q_dept = st.text_input("单位包含", value=st.session_state.get("faculty_q_dept", ""), key="faculty_q_dept")
    with col_q4:
        do_query = st.button("查询", type="primary")

    # Query runs on button click, but also reuses last results if present.
    if do_query or ("faculty_query_results" not in st.session_state):
        db: Session = next(get_db())
        try:
            query = db.query(Faculty)
            if _norm_empty(q_name):
                query = query.filter(Faculty.name_zh.contains(_norm_empty(q_name)))
            if _norm_empty(q_emp):
                query = query.filter(Faculty.employee_id == _norm_empty(q_emp))
            if _norm_empty(q_dept):
                query = query.filter(Faculty.department.contains(_norm_empty(q_dept)))

            total = query.count()
            rows = query.order_by(Faculty.id.desc()).limit(200).all()
            st.session_state.faculty_query_total = int(total)
            st.session_state.faculty_query_results = rows
        finally:
            db.close()

    results = st.session_state.get("faculty_query_results", [])
    total = int(st.session_state.get("faculty_query_total", 0))

    st.caption(f"共 {total} 条结果（最多展示 200 条）")
    if results:
        df = pd.DataFrame(
            [
                {
                    "ID": f.id,
                    "工号": f.employee_id,
                    "姓名": f.name_zh,
                    "单位": f.department,
                    "多单位": ("; ".join(f.departments) if isinstance(f.departments, list) else ""),
                    "英文名": ("; ".join(f.name_en_list) if isinstance(f.name_en_list, list) else ""),
                }
                for f in results
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("暂无结果。你可以先查询或直接新增。")

    st.divider()

    def _invalidate_query_cache() -> None:
        for k in ["faculty_query_results", "faculty_query_total"]:
            if k in st.session_state:
                del st.session_state[k]

    pick_options = {"➕ 新建记录": None}
    if results:
        for f in results:
            pick_options[
                f"{f.name_zh} | {f.employee_id or '无工号'} | {f.department or '无单位'} (ID={f.id})"
            ] = f.id

    picked_label = st.selectbox(
        "选择要操作的记录",
        options=list(pick_options.keys()),
        key="faculty_picked_label",
    )
    picked_id = pick_options.get(picked_label)

    default_emp = ""
    default_name = ""
    default_dept = ""
    default_depts_text = ""
    default_en_text = ""

    if picked_id is not None:
        db: Session = next(get_db())
        try:
            target = db.query(Faculty).filter(Faculty.id == int(picked_id)).first()
            if target is None:
                st.warning("记录不存在，可能已被删除。请重新查询。")
                picked_id = None
            else:
                default_emp = target.employee_id or ""
                default_name = target.name_zh or ""
                default_dept = target.department or ""
                default_depts_text = "; ".join(target.departments) if isinstance(target.departments, list) else ""
                default_en_text = "; ".join(target.name_en_list) if isinstance(target.name_en_list, list) else ""
        finally:
            db.close()

    with st.form("faculty_crud_form", clear_on_submit=False):
        emp_id = st.text_input("工号（可空）", value=default_emp)
        name_zh = st.text_input("姓名（必填）", value=default_name)
        dept = st.text_input("单位（可空）", value=default_dept)
        depts_text = st.text_area(
            "多单位（可空，逗号/分号/换行分隔）",
            value=default_depts_text,
            height=80,
        )
        en_text = st.text_area(
            "英文名变体（可空，逗号/分号/换行分隔）",
            value=default_en_text,
            height=80,
        )

        confirm_delete = st.checkbox("确认删除（不可恢复）", value=False)
        col_a, col_b = st.columns([1, 1])
        with col_a:
            submit_save = st.form_submit_button("保存", type="primary")
        with col_b:
            submit_delete = st.form_submit_button(
                "删除",
                disabled=(picked_id is None) or (not confirm_delete),
            )

    if submit_save:
        if not _norm_empty(name_zh):
            st.error("姓名不能为空。")
        else:
            db: Session = next(get_db())
            try:
                if picked_id is None:
                    new_emp = _empty_to_none(emp_id)
                    if new_emp:
                        exists = db.query(Faculty).filter(Faculty.employee_id == new_emp).first()
                        if exists is not None:
                            st.error("工号已存在，请选择该记录后保存（更新），或清空工号再新增。")
                            raise RuntimeError("duplicate employee_id")
                    row = Faculty(
                        employee_id=_empty_to_none(emp_id),
                        name_zh=_norm_empty(name_zh),
                        department=_empty_to_none(dept),
                        departments=_parse_list_text(depts_text),
                        name_en_list=_parse_list_text(en_text),
                    )
                    db.add(row)
                else:
                    target = db.query(Faculty).filter(Faculty.id == int(picked_id)).first()
                    if target is None:
                        st.error("要更新的记录不存在。")
                        raise RuntimeError("missing target")
                    new_emp = _empty_to_none(emp_id)
                    if new_emp:
                        dup = db.query(Faculty).filter(
                            Faculty.employee_id == new_emp,
                            Faculty.id != target.id,
                        ).first()
                        if dup is not None:
                            st.error("工号已被其他记录占用，请更换工号。")
                            raise RuntimeError("duplicate employee_id")

                    target.employee_id = new_emp
                    target.name_zh = _norm_empty(name_zh)
                    target.department = _empty_to_none(dept)
                    target.departments = _parse_list_text(depts_text)
                    target.name_en_list = _parse_list_text(en_text)

                db.commit()
                st.success("√ 已保存")
                _invalidate_query_cache()
                st.rerun()
            except RuntimeError:
                db.rollback()
            except Exception as e:
                db.rollback()
                st.error(f"数据库错误：{str(e)}")
            finally:
                db.close()

    if submit_delete:
        if picked_id is None:
            st.warning("请选择要删除的记录。")
        else:
            db: Session = next(get_db())
            try:
                target = db.query(Faculty).filter(Faculty.id == int(picked_id)).first()
                if target is None:
                    st.warning("未找到要删除的记录。")
                else:
                    db.delete(target)
                    db.commit()
                    st.success("√ 已删除")
                    _invalidate_query_cache()
                    st.rerun()
            except Exception as e:
                db.rollback()
                st.error(f"数据库错误：{str(e)}")
            finally:
                db.close()

    end_card()

# --- Tab 2: Library Management (Placeholder) ---
with tab2:
    begin_card("本地文献库", "后续将管理 data/pdfs 下的文件。")
    st.write("该模块用于管理已缓存的 PDF 与附件。")
    end_card()
