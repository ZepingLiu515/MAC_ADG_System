# ✨ 去重功能说明

## 概述

MAC-ADG 系统现已支持 **自动去重** 功能。当同一篇论文（相同 DOI）被多次提交时，系统会自动识别并跳过重复处理。

## 工作原理

### 1. **状态追踪**

每篇论文在数据库中有一个 `status` 字段，用于追踪处理状态：

| 状态 | 含义 | 行为 |
|-----|------|------|
| `PENDING` | 初始状态 | （实际不会出现，创建时直接设为 PROCESSING） |
| `PROCESSING` | 正在处理中 | 跳过处理，提示"论文正在处理中" |
| `COMPLETED` | 已完成 | 跳过处理，直接返回缓存结果 |
| `ERROR` | 处理出错 | 显示错误信息，可重新尝试 |

### 2. **处理流程**

```
DOI 提交
   ↓
检查数据库中是否存在该 DOI
   ↓
┌─────────────────────────────────┐
│ 存在吗？                         │
└─────────────────────────────────┘
                ↙        ↘
            是          否
           ↓            ↓
    ┌──────────────┐  ┌──────────────────┐
    │ 检查状态     │  │ 创建新记录       │
    └──────────────┘  │ status=PROCESSING│
         ↓            └──────────────────┘
    ┌─────────────────────────────┐       ↓
    │ COMPLETED?    PROCESSING?   │    执行完整流水线
    │                             │    (Scout→Vision→Judge)
    └─────────────────────────────┘       ↓
       ↙                    ↘         标记为 COMPLETED
      是                    是              ↓
      ↓                    ↓        返回结果
   跳过处理           等待重试
   返回缓存             返回状态
```

### 3. **时间节省**

对于重复的 DOI，跳过以下步骤：
- ❌ 不再查询 Crossref API（节省 ~0.5s）
- ❌ 不再获取网页截图（节省 ~2-3s）
- ❌ 不再执行 OCR 分析（节省 ~1-2s）
- ❌ 不再执行身份匹配（节省 ~0.5s）

**总计节省：4-6 秒/篇重复论文**

## 使用示例

### 单篇论文多次查询

```python
from backend.orchestrator import Orchestrator

orch = Orchestrator()
doi = "10.3390/nu15204383"

# 第一次：完整处理（~6 秒）
result1 = orch.process_dois([doi])
# [Orchestrator] 处理 1/1: 10.3390/nu15204383
# [步骤 1/4] 🕵️ Scout Agent - 获取元数据...
# [步骤 2/4] 🌐 WebDriver - 获取截图...
# ... (完整流程)

print(f"耗时: ~6 秒")
print(result1[0]['status'])  # 'COMPLETED'

# 第二次：跳过处理（~0.1 秒）
result2 = orch.process_dois([doi])
# [Orchestrator] 处理 1/1: 10.3390/nu15204383
# [去重] ✅ 该论文已处理过（2026-03-29 15:30:45）
#        标题: Example Paper Title

print(f"耗时: ~0.1 秒")
print(result2[0]['skipped'])  # True
print(result2[0]['status'])   # 'COMPLETED'
```

### 批量处理含重复 DOI

```python
dois = [
    "10.3390/nu15204383",      # 第一次处理
    "10.3934/publichealth.2026006",  # 第一次处理
    "10.3390/nu15204383",      # 跳过（重复）
    "10.3934/publichealth.2026006",  # 跳过（重复）
    "10.1038/s41586-020-2649-2",     # 第一次处理
]

results = orch.process_dois(dois)

# 统计
new_processed = sum(1 for r in results if not r.get('skipped'))  # 3
skipped = sum(1 for r in results if r.get('skipped'))             # 2

print(f"新处理：{new_processed}，跳过：{skipped}")
# 新处理：3，跳过：2
```

### 从 Excel 导入（自动去重）

```python
# test_dois.xlsx 中有 10 个 DOI，其中 5 个重复
results = orch.process_excel('test_dois.xlsx')

# 只会处理 5 个新的 DOI，其余 5 个自动跳过
for r in results:
    status = "⏭️ 已跳过" if r.get('skipped') else "✅ 已处理"
    print(f"{r['doi']}: {status}")
```

## 结果示例

### 新论文（首次处理）
```json
{
    "doi": "10.3390/nu15204383",
    "title": "Nutritional Epidemiology of Obesity",
    "journal": "Nutrients",
    "publish_date": "2024-10-15",
    "status": "COMPLETED",
    "authors": 5,
    "matched_authors": 2,
    "skipped": false
}
```

### 重复论文（已处理）
```json
{
    "doi": "10.3390/nu15204383",
    "title": "Nutritional Epidemiology of Obesity",
    "journal": "Nutrients",
    "publish_date": "2024-10-15",
    "status": "COMPLETED",
    "matched_authors": 2,
    "total_authors": 5,
    "skipped": true  // 关键：这次被跳过了
}
```

### 处理中的论文（并发保护）
```json
{
    "doi": "10.3390/nu15204383",
    "status": "PROCESSING",
    "skipped": true
}
```

## 高级特性

### 1. **并发安全**

如果同一 DOI 被多个进程同时处理，系统会：
- 第一个进程：设置 `status=PROCESSING` 并开始处理
- 其他进程：检测到 `PROCESSING` 状态，自动等待或返回处理中状态

### 2. **错误恢复**

如果论文处理失败（`status=ERROR`）：
- 状态会被标记为 ERROR
- 下次提交时会被重新处理（允许重试）
- 不会被当作已完成而跳过

### 3. **手动重新处理**

如果需要重新处理已完成的论文：

```python
from database.connection import get_db
from database.models import Paper

db = next(get_db())

# 重置 DOI 的状态
doi = "10.3390/nu15204383"
paper = db.query(Paper).filter(Paper.doi == doi).first()
if paper:
    paper.status = "PENDING"
    db.commit()

# 下次提交时会被重新处理
```

## 数据库统计

查看去重效果：

```python
from database.connection import get_db
from database.models import Paper

db = next(get_db())

total = db.query(Paper).count()
completed = db.query(Paper).filter(Paper.status == "COMPLETED").count()
processing = db.query(Paper).filter(Paper.status == "PROCESSING").count()
errors = db.query(Paper).filter(Paper.status == "ERROR").count()

print(f"总论文数: {total}")
print(f"已完成: {completed}")
print(f"处理中: {processing}")
print(f"错误: {errors}")

# 示例输出：
# 总论文数: 47
# 已完成: 45
# 处理中: 1
# 错误: 1
```

## 常见问题

### Q: 如果我上传的 Excel 中有 50 个 DOI，其中 30 个已处理过，会怎样？

**A:** 系统会：
1. 自动检测这 30 个已处理过的 DOI
2. 跳过它们（不再查询 Crossref、不再截图、不再 OCR）
3. 只处理新的 20 个 DOI
4. 返回的结果中，前 30 个会被标记为 `"skipped": true`

### Q: 能否限制去重，强制重新处理某些论文？

**A:** 可以。在数据库中找到对应的 Paper 记录，将其 status 改为 PENDING，然后重新提交。

### Q: 去重后的结果会不会过期？

**A:** 系统返回的是数据库中完整的记录，包括所有已匹配的作者和置信度。如果源数据（Crossref、网页内容）更新了，可以手动重置状态来重新处理。

### Q: 两个不同的 DOI 但内容完全相同怎么办？

**A:** 系统是基于 DOI 进行去重的，不同的 DOI 会被视为不同的论文并各自处理一次。这是正确的行为。

## 测试去重功能

运行演示脚本：

```bash
python tests/test_dedup_feature.py
```

这个脚本会：
1. 提交包含重复 DOI 的列表
2. 第一次处理：完整处理所有唯一的 DOI
3. 统计结果，展示时间节省

## 总结

✅ **启用条件**：自动启用，无需配置
✅ **节省时间**：每篇重复论文节省 4-6 秒
✅ **提高稳定性**：避免重复查询外部 API
✅ **智能管理**：自动追踪处理状态
✅ **易于恢复**：出错时可轻松重试
