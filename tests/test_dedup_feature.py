"""
【去重功能演示】

演示 Orchestrator 的自动去重机制：
1. 第一次查询一个 DOI → 完全处理
2. 第二次查询同一个 DOI → 跳过处理，直接返回缓存结果
3. 查询多个 DOI，其中有重复 → 自动识别并跳过
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestrator import Orchestrator
import time


def test_dedup_feature():
    print("=" * 80)
    print("🔄 去重功能演示")
    print("=" * 80)
    
    orchestrator = Orchestrator()
    
    # 测试 DOI
    test_dois = [
        "10.3390/nu15204383",  # 第一次处理
        "10.3390/nu15204383",  # 第二次处理同一个 → 应该跳过
        "10.3934/publichealth.2026006",  # 新的 DOI → 处理
        "10.3390/nu15204383",  # 第三次处理第一个 → 应该跳过
    ]
    
    print("\n📋 待处理 DOI 列表:")
    for idx, doi in enumerate(test_dois, 1):
        print(f"   {idx}. {doi}")
    
    print("\n" + "=" * 80)
    print("第一轮：处理所有 DOI（包括重复的）")
    print("=" * 80)
    
    start_time = time.time()
    results = orchestrator.process_dois(test_dois)
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 80)
    print("📊 处理结果统计")
    print("=" * 80)
    
    skipped_count = sum(1 for r in results if r.get('skipped'))
    processed_count = sum(1 for r in results if not r.get('skipped'))
    
    print(f"\n✅ 总任务数: {len(results)}")
    print(f"🔄 新处理: {processed_count}")
    print(f"⏭️ 跳过（重复）: {skipped_count}")
    print(f"⏱️ 总耗时: {elapsed:.1f}秒")
    
    print("\n详细结果:\n")
    for idx, (doi, result) in enumerate(zip(test_dois, results), 1):
        skipped = result.get('skipped', False)
        status = result.get('status', 'UNKNOWN')
        
        if skipped:
            print(f"{idx}. [{doi}]")
            print(f"   状态: ⏭️ 跳过（已处理过）")
            print(f"   已匹配作者: {result.get('matched_authors', '?')}")
            print(f"   总作者数: {result.get('total_authors', '?')}\n")
        else:
            error = result.get('error')
            if error:
                print(f"{idx}. [{doi}]")
                print(f"   状态: ❌ 错误")
                print(f"   错误: {error}\n")
            else:
                print(f"{idx}. [{doi}]")
                print(f"   状态: ✅ {status}")
                print(f"   标题: {result.get('title', 'N/A')}")
                print(f"   期刊: {result.get('journal', 'N/A')}")
                print(f"   作者数: {len(result.get('authors', []))}\n")
    
    print("=" * 80)
    print("🎯 去重机制的优势")
    print("=" * 80)
    print("""
✨ 节省时间：
   - 避免重复查询 Crossref API
   - 避免重复获取截图
   - 避免重复 OCR 分析
   - 避免重复身份匹配

✨ 数据一致性：
   - 相同 DOI 始终返回相同结果
   - 防止数据库中出现重复记录
   - 便于追踪论文处理历史

✨ 支持的状态：
   - COMPLETED: 论文已完全处理，直接返回缓存
   - PROCESSING: 论文正在处理中，等待完成
   - ERROR: 论文处理出错，可重新尝试
   - PENDING: 初始状态（实际不会看到）

💡 实现原理：
   1. 每个 DOI 对应一条 Paper 记录
   2. Paper.status 追踪处理状态
   3. 处理前检查：如果 status=COMPLETED 则跳过
   4. 处理中设置 status=PROCESSING
   5. 完成后设置 status=COMPLETED
""")
    
    print("=" * 80)
    print("✅ 演示完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_dedup_feature()
