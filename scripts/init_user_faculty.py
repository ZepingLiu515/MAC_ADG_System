"""
初始化用户自己的 Faculty 信息 - 支持多部门
"""
import os
import json
import sys
from pathlib import Path

# 确保能找到 database 模块
sys.path.insert(0, str(Path(__file__).parent))

from database.models import Faculty, Paper, PaperAuthor
from database.connection import SessionLocal, init_db

def init_user_faculty():
    """初始化你自己的教师记录"""
    db = SessionLocal()
    
    # 删除旧的刘泽萍记录（准备更新）
    old_zeping = db.query(Faculty).filter(Faculty.name_zh == "刘泽萍").first()
    if old_zeping:
        # 先删除相关的 PaperAuthor 记录（断开外键引用）
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
    print(f"\n✅ 插入刘泽萍 (ID: {zeping.id}) - 支持多部门:")
    print(f"   分部门 1: West China School of Medicine, Sichuan University, Chengdu, China")
    print(f"   分部门 2: College of Computer Science, Sichuan University, Chengdu, China")
    print(f"   英文名: Zeping Liu / Z.P. Liu / Liu Zeping / Liu, Zeping")
    
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
    print("\n[数据库初始化]")
    init_db()
    
    # 添加用户信息
    print("\n[用户信息初始化]")
    init_user_faculty()
    
    print("\n" + "="*70)
    print("✅ 数据库初始化完成！")
    print("📊 系统现已支持多部门匹配")
    print("="*70 + "\n")
