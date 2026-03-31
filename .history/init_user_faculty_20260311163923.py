"""
初始化用户自己的 Faculty 信息 - 支持多部门
"""
import os
import json
from database.connection import SessionLocal
from database.models import Faculty, Paper, PaperAuthor

def init_user_faculty():
    """初始化你自己的教师记录"""
    db = SessionLocal()
    
    # 删除旧的刘泽萍记录（准备更新）
    old_zeping = db.query(Faculty).filter(Faculty.name_zh == "刘泽萍").first()
    if old_zeping:
        # 先删除相关的 PaperAuthor 记录
        db.query(PaperAuthor).filter(PaperAuthor.matched_faculty_id == old_zeping.id).update(
            {"matched_faculty_id": None}
        )
        db.delete(old_zeping)
        db.commit()
        print("✅ 删除旧的刘泽萍记录")
    
    # 插入新的刘泽萍记录 - 支持多部门
    zeping = Faculty(
        employee_id="E-ZEP-001",
        name_zh="刘泽萍",
        name_en_list=json.dumps([
            "Zeping Liu", 
            "Z.P. Liu", 
            "Liu Zeping",
            "Liu, Zeping"
        ]),
        # 主部门（向后兼容）
        department="West China School of Medicine, Sichuan University",
        # V2.0: 多部门列表
        departments=json.dumps([
            "West China School of Medicine, Sichuan University, Chengdu, China",
            "College of Computer Science, Sichuan University, Chengdu, China"
        ])
    )
    db.add(zeping)
    db.commit()
    print(f"✅ 插入刘泽萍 (ID: {zeping.id}) - 支持 2 个部门")
    print(f"   - West China School of Medicine, Sichuan University")
    print(f"   - College of Computer Science, Sichuan University")
    
    # 也保留原有的测试教师以传统格式运行
    # （可选）
    
    db.close()

if __name__ == "__main__":
    # 首先删除旧数据库
    db_path = os.path.join(
        os.path.dirname(__file__), 
        'data', 
        'mac_adg.db'
    )
    
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  删除旧数据库: {db_path}")
    
    # 初始化数据库
    from database.connection import init_db
    init_db()
    
    # 添加用户信息
    init_user_faculty()
    
    print("\n" + "="*70)
    print("初始化完成！数据库已更新为支持多部门")
    print("="*70)
