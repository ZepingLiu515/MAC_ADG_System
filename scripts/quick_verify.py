"""
快速验证脚本：运行所有测试前的环境检查
执行: python quick_verify.py
"""

import os
import sys
import json
from pathlib import Path

def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python 版本过低: {version.major}.{version.minor}")
        return False

def check_required_packages():
    """检查必需的依赖包"""
    required = ['streamlit', 'sqlalchemy', 'pandas', 'requests', 'fitz']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (缺失)")
            missing.append(package)
    
    return len(missing) == 0

def check_directories():
    """检查必需的目录"""
    base_dir = Path(__file__).parent
    required_dirs = [
        'backend/agents',
        'backend/utils',
        'database',
        'frontend/pages',
        'pages',
        'data',
    ]
    
    all_exist = True
    for d in required_dirs:
        path = base_dir / d
        if path.exists():
            print(f"✅ {d}/")
        else:
            print(f"❌ {d}/ (缺失)")
            all_exist = False
    
    return all_exist

def check_files():
    """检查关键文件"""
    base_dir = Path(__file__).parent
    required_files = [
        'config.py',
        'main.py',
        'requirements.txt',
        'backend/orchestrator.py',
        'backend/agents/scout_agent.py',
        'backend/agents/vision_agent.py',
        'backend/agents/judge_agent.py',
        'database/models.py',
        'database/connection.py',
    ]
    
    all_exist = True
    for f in required_files:
        path = base_dir / f
        if path.exists():
            print(f"✅ {f}")
        else:
            print(f"❌ {f} (缺失)")
            all_exist = False
    
    return all_exist

def check_config():
    """检查配置文件"""
    try:
        from config import PDF_CACHE_DIR, HEADERS
        print(f"✅ config.py 加载成功")
        print(f"   - PDF_CACHE_DIR: {PDF_CACHE_DIR}")
        return True
    except Exception as e:
        print(f"❌ config.py 加载失败: {e}")
        return False

def check_database():
    """检查数据库连接"""
    try:
        from database.connection import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if len(tables) >= 3:
            print(f"✅ 数据库连接成功，找到 {len(tables)} 张表")
            return True
        else:
            print(f"⚠️  数据库存在但表数量不足 ({len(tables)} < 3)")
            print(f"   建议运行: python force_init_db.py")
            return False
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print(f"   建议运行: python force_init_db.py")
        return False

def main():
    print("=" * 60)
    print("🔍 MAC-ADG 系统环境验证")
    print("=" * 60)
    
    checks = [
        ("Python 版本", check_python_version),
        ("依赖包", check_required_packages),
        ("目录结构", check_directories),
        ("代码文件", check_files),
        ("配置文件", check_config),
        ("数据库", check_database),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n[{name}]")
        result = check_func()
        results.append((name, result))
        print()
    
    # 总结
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    if passed == total:
        print(f"✅ 所有检查通过! ({passed}/{total})\n")
        print("下一步: 运行以下命令进行单元测试")
        print("  python test_scout.py")
        print("  python test_vision.py")
        print("  python test_orchestrator.py")
        print("\n或启动 Streamlit UI:")
        print("  streamlit run main.py")
    else:
        print(f"⚠️  有 {total - passed} 项检查未通过\n")
        print("请查看上面的 ❌ 项目并修复")
    print("=" * 60)

if __name__ == "__main__":
    main()
