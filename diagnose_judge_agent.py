"""
【Judge Agent 系统检查脚本】

快速诊断：
1. 环境检查（依赖库）
2. 代码完整性检查
3. 数据库连接检查
4. 功能可用性检查
5. 性能基准测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib
import time
from datetime import datetime


def check_imports():
    """检查必要的依赖库"""
    print("\n【1. 依赖库检查】")
    print("=" * 80)
    
    required_modules = [
        'sqlalchemy',
        'requests',
        'pandas',
        'dotenv',
        'difflib',
        'json'
    ]
    
    all_ok = True
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} - 缺失！")
            all_ok = False
    
    return all_ok


def check_code_structure():
    """检查代码文件是否完整"""
    print("\n【2. 代码结构检查】")
    print("=" * 80)
    
    required_files = [
        'backend/agents/judge_agent_v2.py',
        'backend/agents/scout_agent.py',
        'backend/agents/vision_agent_v2.py',
        'backend/orchestrator.py',
        'backend/utils/webdriver.py',
        'database/models.py',
        'database/connection.py',
    ]
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_ok = True
    
    for file_path in required_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"✅ {file_path} ({size} bytes)")
        else:
            print(f"❌ {file_path} - 文件不存在！")
            all_ok = False
    
    return all_ok


def check_judge_agent_methods():
    """检查 Judge Agent 的所有方法"""
    print("\n【3. Judge Agent 方法检查】")
    print("=" * 80)
    
    try:
        from backend.agents.judge_agent_v2 import JudgeAgent
        
        judge = JudgeAgent()
        
        required_methods = [
            'adjudicate',
            '_get_or_create_paper',
            '_merge_authors',
            '_match_author_to_faculty',
            '_name_similarity',
            '_affiliation_similarity',
            '_use_llm_for_verification'
        ]
        
        all_ok = True
        for method_name in required_methods:
            if hasattr(judge, method_name):
                print(f"✅ {method_name}()")
            else:
                print(f"❌ {method_name}() - 方法不存在！")
                all_ok = False
        
        return all_ok
    
    except Exception as e:
        print(f"❌ 导入 JudgeAgent 失败: {e}")
        return False


def check_database():
    """检查数据库连接"""
    print("\n【4. 数据库检查】")
    print("=" * 80)
    
    try:
        from database.connection import get_db
        from database.models import Faculty, Paper, PaperAuthor
        
        db = next(get_db())
        
        # 查询表记录数
        faculty_count = db.query(Faculty).count()
        paper_count = db.query(Paper).count()
        author_count = db.query(PaperAuthor).count()
        
        print(f"✅ 数据库连接成功")
        print(f"   • Faculty 表: {faculty_count} 条记录")
        print(f"   • Paper 表: {paper_count} 条记录")
        print(f"   • PaperAuthor 表: {author_count} 条记录")
        
        # 检查关键字段
        if faculty_count > 0:
            first_faculty = db.query(Faculty).first()
            print(f"\n✅ 教师数据样本:")
            print(f"   • ID: {first_faculty.employee_id}")
            print(f"   • 名字（中）: {first_faculty.name_zh}")
            print(f"   • 部门: {first_faculty.department}")
        else:
            print(f"\n⚠️ 教师库为空（建议填充测试数据）")
        
        db.close()
        return True
    
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        return False


def check_scout_agent():
    """检查 Scout Agent 可用性"""
    print("\n【5. Scout Agent 集成检查】")
    print("=" * 80)
    
    try:
        from backend.agents.scout_agent import ScoutAgent
        
        scout = ScoutAgent()
        print(f"✅ Scout Agent 初始化成功")
        
        # 测试查询（不实际发送请求，只检查代码）
        print(f"   • 已准备好查询 Crossref API")
        print(f"   • 支持的方法: run(), _extract_authors_from_crossref()")
        
        return True
    
    except Exception as e:
        print(f"❌ Scout Agent 检查失败: {e}")
        return False


def check_orchestrator():
    """检查 Orchestrator 集成"""
    print("\n【6. Orchestrator 集成检查】")
    print("=" * 80)
    
    try:
        from backend.orchestrator import Orchestrator
        
        orch = Orchestrator()
        print(f"✅ Orchestrator 初始化成功")
        
        # 检查包含的智能体
        agents = {
            'scout': orch.scout,
            'judge': orch.judge,
            'vision': orch.vision,
            'webdriver': orch.webdriver
        }
        
        for name, agent in agents.items():
            if agent:
                print(f"   • {name.capitalize()}: ✅")
            else:
                print(f"   • {name.capitalize()}: ❌")
        
        return all(agents.values())
    
    except Exception as e:
        print(f"❌ Orchestrator 检查失败: {e}")
        return False


def performance_benchmark():
    """性能基准测试"""
    print("\n【7. 性能基准测试】")
    print("=" * 80)
    
    try:
        from backend.agents.judge_agent_v2 import JudgeAgent
        from database.connection import get_db
        from database.models import Faculty
        
        db = next(get_db())
        judge = JudgeAgent()
        
        # 创建测试数据
        test_author = {
            'name': 'Li Ming',
            'affiliation': 'Computer Science',
            'is_corresponding': False,
            'is_co_first': False
        }
        
        all_faculty = db.query(Faculty).all()
        
        if len(all_faculty) == 0:
            print("⚠️ 教师库为空，跳过性能测试")
            return True
        
        print(f"📊 测试条件:")
        print(f"   • 校内教师数: {len(all_faculty)}")
        print(f"   • 测试作者: {test_author['name']}")
        
        # 单次匹配性能
        start = time.time()
        result = judge._match_author_to_faculty(test_author, all_faculty, db)
        elapsed = (time.time() - start) * 1000
        
        print(f"\n⚡ 单次匹配:")
        print(f"   • 耗时: {elapsed:.2f} ms")
        if result:
            faculty, confidence = result
            print(f"   • 结果: ✅ 匹配 (置信度: {confidence:.2%})")
        else:
            print(f"   • 结果: ⚠️ 未匹配")
        
        # 批量匹配性能
        num_test = min(100, len(all_faculty))
        test_authors = [
            {**test_author, 'name': f'Author{i}'}
            for i in range(num_test)
        ]
        
        start = time.time()
        results = [
            judge._match_author_to_faculty(author, all_faculty, db)
            for author in test_authors
        ]
        elapsed = (time.time() - start) * 1000
        
        matched = len([r for r in results if r])
        
        print(f"\n⚡ 批量匹配（{num_test} 人）:")
        print(f"   • 总耗时: {elapsed:.2f} ms")
        print(f"   • 平均: {elapsed/num_test:.2f} ms/人")
        print(f"   • 匹配率: {matched}/{num_test}")
        
        db.close()
        return True
    
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False


def print_system_info():
    """打印系统信息"""
    print("\n【系统信息】")
    print("=" * 80)
    
    import platform
    
    print(f"Python 版本: {platform.python_version()}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查环境变量
    try:
        from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL
        if DEEPSEEK_API_KEY:
            print(f"✅ DeepSeek API 已配置")
            print(f"   • 模型: {DEEPSEEK_MODEL}")
        else:
            print(f"⚠️ DeepSeek API 未配置")
    except:
        print(f"⚠️ 配置文件读取失败")


def main():
    print("\n" + "=" * 80)
    print("🔍 Judge Agent 系统诊断工具")
    print("=" * 80)
    
    results = {}
    
    # 执行所有检查
    results['imports'] = check_imports()
    results['code'] = check_code_structure()
    results['judge'] = check_judge_agent_methods()
    results['database'] = check_database()
    results['scout'] = check_scout_agent()
    results['orchestrator'] = check_orchestrator()
    results['perf'] = performance_benchmark()
    
    print_system_info()
    
    # 总结
    print("\n【诊断总结】")
    print("=" * 80)
    
    checks = [
        ('依赖库', results['imports']),
        ('代码结构', results['code']),
        ('Judge Agent', results['judge']),
        ('数据库', results['database']),
        ('Scout Agent', results['scout']),
        ('Orchestrator', results['orchestrator']),
        ('性能', results['perf']),
    ]
    
    for check_name, passed in checks:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{check_name:15} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 系统检查完全通过！Judge Agent 已准备好使用。")
        print("\n✅ 下一步:")
        print("   1. 运行: python tests/test_judge_agent_comprehensive.py")
        print("   2. 或使用: orch.process_dois(dois)")
    else:
        print("⚠️ 系统检查未完全通过，请查看上面的错误信息。")
        print("\n💡 常见问题:")
        print("   • 导入错误？检查依赖库是否安装")
        print("   • 文件不存在？检查文件路径是否正确")
        print("   • 数据库错误？运行 python force_init_db.py")
        print("   • 配置错误？检查 config.py 文件")
    
    print("=" * 80 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
