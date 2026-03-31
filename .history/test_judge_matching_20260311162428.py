#!/usr/bin/env python
"""诊断 Judge Agent 的匹配逻辑"""
from database.connection import SessionLocal
from database.models import Faculty
from difflib import SequenceMatcher

db = SessionLocal()

print("=" * 80)
print("🧪 Judge Agent 匹配诊断")
print("=" * 80)

# 1. 显示数据库中的所有教师
print("\n📚 数据库中的教师:")
faculties = db.query(Faculty).all()
for f in faculties:
    print(f"  - {f.name_zh or f.name_en_list} (ID: {f.id}, 部门: {f.department})")

# 2. 测试匹配逻辑
test_names = ["刘泽萍", "王小明", "测试教师"]
print("\n✅ 模糊匹配测试 (阈值 0.6):")

for test_name in test_names:
    print(f"\n  测试：{test_name}")
    for f in faculties:
        # 获取变体列表
        variants = []
        if f.name_en_list:
            try:
                import json
                variants = json.loads(f.name_en_list)
            except:
                pass
        
        candidates = []
        if f.name_zh:
            candidates.append(f.name_zh)
        candidates.extend(variants)
        
        # 计算最高分
        best_score = 0.0
        matched_variant = None
        
        for variant in candidates:
            if not variant:
                continue
            var = variant.lower()
            nm = test_name.lower()
            
            # 完全匹配
            if var == nm:
                best_score = 1.0
                matched_variant = variant
                break
            
            # 包含匹配
            if var in nm or nm in var:
                score = 0.95
                if score > best_score:
                    best_score = score
                    matched_variant = variant
            else:
                # 模糊匹配
                score = SequenceMatcher(None, var, nm).ratio()
                if score > best_score:
                    best_score = score
                    matched_variant = variant
        
        status = "✅" if best_score > 0.6 else "❌"
        print(f"    {status} {f.name_zh} (中文) vs {matched_variant or candidates[0]}: {best_score:.2f}")

# 3. 测试 Mock 数据
print("\n\n🎯 Mock 数据匹配模拟:")
mock_authors = [
    {
        "name": "刘泽萍",
        "affiliation": "四川大学物理学院",
        "position": 1,
        "is_corresponding": True,
        "is_co_first": False
    },
    {
        "name": "王小明", 
        "affiliation": "四川大学计算机学院",
        "position": 2,
        "is_corresponding": False,
        "is_co_first": True
    }
]

for author in mock_authors:
    pname = author['name']
    print(f"\n  作者：{pname}")
    
    candidates = []
    for faculty in faculties:
        # 这里复用上面的 _quick_match 逻辑
        variants = []
        if faculty.name_en_list:
            try:
                import json
                variants = json.loads(faculty.name_en_list)
            except:
                pass
        
        can_list = []
        if faculty.name_zh:
            can_list.append(faculty.name_zh)
        can_list.extend(variants)
        
        best_score = 0.0
        for variant in can_list:
            if not variant:
                continue
            var = variant.lower()
            nm = pname.lower()
            
            if var == nm:
                best_score = 1.0
                break
            if var in nm:
                best_score = 0.95
            else:
                score = SequenceMatcher(None, var, nm).ratio()
                if score > best_score:
                    best_score = score
        
        if best_score > 0.6:
            candidates.append((faculty, best_score))
    
    print(f"    L1 候选者 (>0.6): {len(candidates)} 人")
    for fac, score in candidates:
        print(f"      - {fac.name_zh}: {score:.2f}")

db.close()
print("\n" + "=" * 80)
