#!/usr/bin/env python3
"""
快速验证脚本：检查所有修复是否成功

执行: python verify_fixes.py
"""

import os
import sys
import json
from pathlib import Path

def verify_file_exists(path, description):
    """检查文件是否存在"""
    if os.path.exists(path):
        print(f"✅ {description}: {path}")
        return True
    else:
        print(f"❌ {description}: {path} 不存在")
        return False

def verify_no_syntax_errors(filepath):
    """检查Python文件是否有语法错误"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, filepath, 'exec')
        print(f"✅ {filepath}: 无语法错误")
        return True
    except SyntaxError as e:
        print(f"❌ {filepath}: 语法错误 - {e}")
        return False
    except Exception as e:
        print(f"❌ {filepath}: 编译错误 - {e}")
        return False

def verify_json_valid(filepath):
    """检查JSON文件是否有效"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"✅ {filepath}: JSON有效")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ {filepath}: JSON解析失败 - {e}")
        return False
    except Exception as e:
        print(f"❌ {filepath}: 读取失败 - {e}")
        return False

def check_function_exists(filepath, function_name):
    """检查函数是否存在"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if f"def {function_name}(" in content:
            print(f"✅ {filepath}: 包含函数 {function_name}")
            return True
        else:
            print(f"❌ {filepath}: 缺少函数 {function_name}")
            return False
    except Exception as e:
        print(f"❌ {filepath}: 检查失败 - {e}")
        return False

def main():
    print("=" * 70)
    print("🔍 MAC-ADG 系统修复验证")
    print("=" * 70)
    
    base_dir = Path(__file__).parent
    all_passed = True
    
    # 1. 检查新文件
    print("\n[1] 检查新文件...")
    all_passed &= verify_file_exists(
        base_dir / "data" / "affiliation_synonyms.json",
        "同义词文件"
    )
    all_passed &= verify_json_valid(
        base_dir / "data" / "affiliation_synonyms.json"
    )
    
    # 2. 检查修复后的文件语法
    print("\n[2] 检查Python文件语法...")
    python_files = [
        base_dir / "backend" / "agents" / "vision_agent.py",
        base_dir / "backend" / "agents" / "judge_agent.py",
        base_dir / "pages" / "1_Data_Management.py",
        base_dir / "pages" / "2_Smart_Extraction.py",
    ]
    
    for pf in python_files:
        all_passed &= verify_no_syntax_errors(str(pf))
    
    # 3. 检查关键函数是否存在
    print("\n[3] 检查关键函数...")
    all_passed &= check_function_exists(
        str(base_dir / "backend" / "agents" / "vision_agent.py"),
        "_validate_and_normalize_authors"
    )
    all_passed &= check_function_exists(
        str(base_dir / "backend" / "agents" / "judge_agent.py"),
        "_affiliation_match"
    )
    
    # 4. 检查修复内容
    print("\n[4] 检查修复内容...")
    
    # 检查中文参数名是否已修复
    with open(base_dir / "backend" / "agents" / "vision_agent.py", 'r', encoding='utf-8') as f:
        vision_content = f.read()
    if "def stealth_sync(page):" in vision_content:
        print("✅ Vision Agent: 参数名已改为英文")
    else:
        print("❌ Vision Agent: 参数名仍然有问题")
        all_passed = False
    
    # 检查Judge Agent是否有改进的异常处理
    with open(base_dir / "backend" / "agents" / "judge_agent.py", 'r', encoding='utf-8') as f:
        judge_content = f.read()
    if "json.JSONDecodeError" in judge_content:
        print("✅ Judge Agent: JSON异常处理已改进")
    else:
        print("❌ Judge Agent: 异常处理未改进")
        all_passed = False
    
    # 检查Streamlit文件是否使用了try/finally
    with open(base_dir / "pages" / "1_Data_Management.py", 'r', encoding='utf-8') as f:
        dm_content = f.read()
    if "finally:" in dm_content and "db.close()" in dm_content:
        print("✅ 前端: Session管理已改进")
    else:
        print("❌ 前端: Session管理未改进")
        all_passed = False
    
    # 5. 最终总结
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有验证通过！")
        print("\n下一步: 运行集成测试")
        print("  python test_judge.py")
        print("  python test_judge_matching.py")
        print("  streamlit run main.py")
        return 0
    else:
        print("❌ 有些验证失败，请检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())
