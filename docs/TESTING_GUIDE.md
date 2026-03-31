# 🧪 MAC-ADG 系统测试指南

## 0️⃣ 前置条件

### 环境准备

```bash
# 1. 进入项目目录
cd MAC_ADG_System

# 2. 创建虚拟环境（可选）
python -m venv venv
# Windows: venv\Scripts\activate
# Unix/Mac: source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装浏览器自动化工具
pip install playwright
playwright install

# 5. 初始化数据库
python force_init_db.py

# 预期输出:
# --- Force Initializing Database ---
# Dropped old tables.
# [INFO] Database initialized at: .../data/mac_adg.db
# ✅ SUCCESS: Database tables created successfully!
```

### 必需的 API Keys（可选，用于完整功能）
```bash
# 创建 .env 文件
cat > .env << EOF
DEEPSEEK_API_KEY=sk_xxxxxxxxxxxx  # 用于 Vision + Judge LLM 功能
EOF
```

---

## ✅ Phase 3.1: 数据库与初始化测试

### Test 3.1.1: 表初始化验证

**脚本**: `test_db_init.py`

```python
from database.models import Faculty, Paper, PaperAuthor
from database.connection import SessionLocal, engine
from sqlalchemy import inspect

def test_tables_exist():
    """验证三张表已创建"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert "faculty" in tables, "Faculty 表不存在"
    assert "papers" in tables, "Papers 表不存在"
    assert "paper_authors" in tables, "PaperAuthor 表不存在"
    
    print("✅ 所有表已成功创建")

def test_table_columns():
    """验证关键字段"""
    inspector = inspect(engine)
    
    faculty_cols = [col['name'] for col in inspector.get_columns("faculty")]
    assert "employee_id" in faculty_cols
    assert "name_zh" in faculty_cols
    assert "name_en_list" in faculty_cols
    
    print("✅ Faculty 表字段完整")

if __name__ == "__main__":
    test_tables_exist()
    test_table_columns()
    print("✅ Phase 3.1 测试通过")
```

**运行**: 
```bash
python test_db_init.py
```

**预期输出**:
```
✅ 所有表已成功创建
✅ Faculty 表字段完整
✅ Phase 3.1 测试通过
```

---

## 🕵️ Phase 3.2: Scout Agent 测试

### Test 3.2.1: Crossref API 查询

**脚本**: `test_scout.py` (已有)

```bash
python test_scout.py
```

**预期输出**:
```
--- Testing Scout Agent ---
DEBUG: Agent initialized.
DEBUG: Running agent for DOI: 10.1038/s41586-020-2649-2
[Scout] Processing DOI: 10.1038/s41586-020-2649-2
[Scout] Metadata fetched successfully
✅ Scout Agent 返回元数据完整性检查通过
```

**验证点**:
- ✅ 返回的 `status` 为 `success_pdf` 或 `metadata_only`
- ✅ 包含 `title`, `journal`, `publish_date` 字段
- ✅ 可选项：`pdf_path` 存在且文件可访问

### Test 3.2.2: PDF 缓存机制

**脚本**: `test_pdf_cache.py` (新建)

```python
import os
from backend.agents.scout_agent import ScoutAgent
from config import PDF_CACHE_DIR

def test_pdf_cache():
    """验证 PDF 缓存和重复下载检测"""
    scout = ScoutAgent()
    doi = "10.1038/s41586-020-2649-2"
    
    # 首次下载
    result1 = scout.run(doi)
    path1 = result1.get("pdf_path")
    assert path1 and os.path.exists(path1), "PDF 未下载"
    
    # 记录文件修改时间
    mtime1 = os.path.getmtime(path1)
    
    # 等待 1 秒，再次调用（应该直接返回缓存）
    import time
    time.sleep(1)
    result2 = scout.run(doi)
    path2 = result2.get("pdf_path")
    
    # 文件修改时间应该不变（说明未重新下载）
    mtime2 = os.path.getmtime(path2)
    assert mtime1 == mtime2, "缓存机制失效，文件被重新下载"
    
    print("✅ PDF 缓存机制工作正常")

if __name__ == "__main__":
    test_pdf_cache()
```

**运行**:
```bash
python test_pdf_cache.py
```

---

## 👁️ Phase 3.3: Vision Agent 测试

### Test 3.3.1: PDF 转图片

**脚本**: 已有 `test_vision.py`

```bash
python test_vision.py
```

**预期输出**:
```
--- Testing Vision Agent ---
Step 1: Scout getting a file...
✅ File ready: .../data/pdf_cache/10.1038_s41586-020-2649-2.pdf

Step 2: Vision Agent processing...
[Extracted Text Preview]: This is the peer review process...
✅ Text Extraction: PASS
✅ Image Snapshot: PASS (.../data/visual_slices/10.1038_s41586-020-2649-2.png)
```

**验证点**:
- ✅ 文本长度 > 50 字符
- ✅ 图片文件存在且可显示
- ✅ DPI ≥ 150 保证可读性

### Test 3.3.2: 文本提取完整性

**脚本**: `test_vision_comprehensive.py` (新建)

```python
from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent

def test_vision_text_quality():
    """验证提取文本包含关键字段"""
    scout = ScoutAgent()
    vision = VisionAgent()
    
    doi = "10.1038/s41586-020-2649-2"
    scout_result = scout.run(doi)
    file_path = scout_result.get("pdf_path")
    
    vision_result = vision.process(file_path)
    text = vision_result["text"].lower()
    
    # 检查关键字
    assert "author" in text or "author" in scout_result.get("title", "").lower(), \
        "未提取到作者相关信息"
    
    print(f"✅ 提取文本长度: {len(vision_result['text'])} 字符")
    print(f"✅ 图片快照: {vision_result['image_path']}")

if __name__ == "__main__":
    test_vision_text_quality()
```

---

## ⚖️ Phase 3.4: Judge Agent 测试

### Test 3.4.1: 身份匹配基础

**脚本**: `test_judge.py` (新建)

```python
from database.models import Faculty
from database.connection import SessionLocal
from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent
import json

def test_judge_matching():
    """验证 Judge Agent 能匹配教师身份"""
    
    # 1. 先插入测试教师
    db = SessionLocal()
    test_faculty = Faculty(
        employee_id="20230001",
        name_zh="刘泽萍",
        name_en_list=json.dumps(["Zeping Liu", "Z.P. Liu", "Liu Zeping"]),
        department="计算机学院"
    )
    
    # 检查是否已存在
    existing = db.query(Faculty).filter(Faculty.employee_id == "20230001").first()
    if not existing:
        db.add(test_faculty)
        db.commit()
    db.close()
    
    # 2. 运行完整流水线
    scout = ScoutAgent()
    vision = VisionAgent()
    judge = JudgeAgent()
    
    doi = "10.1038/s41586-020-2649-2"
    scout_data = scout.run(doi)
    file_path = scout_data.get("pdf_path") or scout_data.get("html_path")
    vision_data = vision.process(file_path)
    
    # 3. Judge 进行匹配
    success = judge.adjudicate(scout_data, vision_data)
    assert success, "Judge adjudicate 返回 False"
    
    # 4. 检查数据库中是否写入了记录
    db = SessionLocal()
    records = db.query(Faculty).filter(Faculty.employee_id == "20230001").first()
    assert records, "教师记录未保存"
    print(f"✅ Judge Agent 成功处理并保存数据")
    db.close()

if __name__ == "__main__":
    test_judge_matching()
```

**运行**:
```bash
python test_judge.py
```

---

## 📊 Phase 3.5: Orchestrator 集成测试

### Test 3.5.1: 完整流水线

**脚本**: 已有 `test_orchestrator.py`

```bash
python test_orchestrator.py
```

**预期输出**:
```
--- Testing Orchestrator Pipeline ---
Results: [{'doi': '10.1038/s41586-020-2649-2', 'title': '...',  'status': 'success_pdf', ...}]
✅ Orchestrator 返回期望的记录
```

### Test 3.5.2: 批量处理

**脚本**: `test_orchestrator_batch.py` (新建)

```python
from backend.orchestrator import Orchestrator

def test_batch_processing():
    """验证批量处理多个 DOI"""
    orchestrator = Orchestrator()
    
    dois = [
        "10.1038/s41586-020-2649-2",
        "10.3934/publichealth.2026006",
    ]
    
    results = orchestrator.process_dois(dois)
    
    assert len(results) == 2, "结果数量不匹配"
    assert all("status" in r for r in results), "缺少 status 字段"
    assert all(r.get("doi") in dois for r in results), "DOI 不匹配"
    
    print(f"✅ 成功处理 {len(results)} 个 DOI")
    for r in results:
        print(f"  - {r['doi']}: {r['status']}")

if __name__ == "__main__":
    test_batch_processing()
```

---

## 🎨 Phase 3.6: 前端 UI 测试

### Test 3.6.1: Streamlit 应用启动

**命令**:
```bash
streamlit run main.py
```

**预期**:
- 浏览器自动打开 `http://localhost:8501`
- 页面显示标题和导航菜单
- 侧边栏显示三个页面选项

### Test 3.6.2: 教师名单上传

**步骤**:
1. 打开 `http://localhost:8501`
2. 侧边栏点击"📂 Data Management"
3. 在"👨‍🏫 Faculty List Management"标签页中：
   - 上传示例教师名单 Excel 文件（需包含 Name, ID, Department 列）
   - 点击"🚀 Confirm & Save to Database"
   - 验证进度条完整且不报错

**预期**:
```
✅ Parsing successful! Identified X faculty members.
✅ Completed! Added Y new records...
```

### Test 3.6.3: DOI 批量提取

**步骤**:
1. 侧边栏点击"🤖 Smart Extraction" (来自 pages/ 目录) 
2. 上传包含 DOI 列的 Excel 文件
3. 点击"🚀 启动全自动流水线"
4. 观察：
   - 进度条推进
   - 实时表格更新
   - 最后显示"✅ 全流程执行完毕！"

**预期表格列**:
```
| doi | title | journal | 状态 | 文本长度 |
|----|-------|---------|------|---------|
| 10.1038/... | Nature... | Nature | ✅ PDF | 12450 |
```

### Test 3.6.4: 统计报表

**步骤**:
1. 侧边栏点击"📊 Analytics Reports"
2. 验证：
   - KPI 卡片显示数字（匹配的论文数、教师数）
   - 数据表可按学院筛选
   - 图表显示论文分布

**预期**:
```
📚 Total Matched Papers: 5
👨‍🏫 Contributing Faculty: 3
🏆 Top Department: 计算机学院
```

---

## 🔬 集成测试脚本

### Test ALL: 端到端完整流程

**脚本**: `test_complete_pipeline.py` (新建)

```python
import pandas as pd
import tempfile
import os
from backend.orchestrator import Orchestrator
from database.connection import SessionLocal
from database.models import Paper, Faculty, PaperAuthor

def test_complete_pipeline():
    """模拟完整用户流程"""
    print("=" * 60)
    print("🧪 端到端集成测试开始")
    print("=" * 60)
    
    # 测试 DOI 列表
    test_dois = ["10.1038/s41586-020-2649-2"]
    
    # 1. 初始化 Orchestrator
    print("\n[1] 初始化 Orchestrator...")
    orchestrator = Orchestrator()
    print("✅ Orchestrator 创建成功")
    
    # 2. 运行流水线
    print("\n[2] 运行 Scout → Vision → Judge 流水线...")
    results = orchestrator.process_dois(test_dois)
    print(f"✅ 处理完成，结果数: {len(results)}")
    
    # 3. 验证结果
    print("\n[3] 验证结果...")
    for r in results:
        print(f"  - DOI: {r['doi']}")
        print(f"    Status: {r['status']}")
        print(f"    Title: {r.get('title', 'N/A')[:50]}...")
    
    # 4. 验证数据库写入
    print("\n[4] 验证数据库...")
    db = SessionLocal()
    paper_count = db.query(Paper).count()
    print(f"✅ Papers 表记录数: {paper_count}")
    
    # 5. 验证输出文件
    print("\n[5] 验证输出文件...")
    for r in results:
        if r.get("pdf_path"):
            assert os.path.exists(r["pdf_path"]), f"PDF 不存在: {r['pdf_path']}"
            print(f"✅ PDF 文件存在: {r['pdf_path']}")
    
    db.close()
    print("\n" + "=" * 60)
    print("✅ 端到端集成测试全部通过！")
    print("=" * 60)

if __name__ == "__main__":
    test_complete_pipeline()
```

**运行**:
```bash
python test_complete_pipeline.py
```

---

## 📈 性能与压力测试

### Test PERF: 批量处理性能

**脚本**: `test_performance.py` (新建)

```python
import time
from backend.orchestrator import Orchestrator

def test_performance():
    """测试处理速度和资源占用"""
    orchestrator = Orchestrator()
    
    # 模拟 10 个 DOI
    test_dois = [
        "10.1038/s41586-020-2649-2",
        "10.3934/publichealth.2026006",
    ] * 5  # 重复组成 10 个
    
    print(f"处理 {len(test_dois)} 个 DOI...")
    start = time.time()
    results = orchestrator.process_dois(test_dois)
    elapsed = time.time() - start
    
    success_count = sum(1 for r in results if r["status"] != "error")
    
    print(f"\n性能指标:")
    print(f"  - 总耗时: {elapsed:.2f} 秒")
    print(f"  - 平均时间/DOI: {elapsed/len(test_dois):.2f} 秒")
    print(f"  - 成功率: {success_count}/{len(test_dois)} ({100*success_count//len(test_dois)}%)")

if __name__ == "__main__":
    test_performance()
```

---

## 📋 测试清单 (Checklist)

### 快速验证列表

```bash
# 基础设施
[ ] python test_db_init.py              # Phase 3.1
[ ] python force_init_db.py              # 确保数据库初始化

# Scout Agent
[ ] python test_scout.py                 # Phase 3.2.1
[ ] python test_pdf_cache.py             # Phase 3.2.3

# Vision Agent  
[ ] python test_vision.py                # Phase 3.3.1

# Judge Agent
[ ] python test_judge.py                 # Phase 3.4.1

# Orchestrator
[ ] python test_orchestrator.py           # Phase 3.5.1
[ ] python test_orchestrator_batch.py    # Phase 3.5.2

# 集成测试
[ ] python test_complete_pipeline.py     # 端到端测试

# 性能测试
[ ] python test_performance.py           # 性能基准

# UI 测试
[ ] streamlit run main.py                # Phase 3.6
  - [ ] 上传教师名单
  - [ ] 批量提取 DOI
  - [ ] 查看统计报表
```

---

## 🐛 调试技巧

### 启用详细日志

在任何测试前设置环境变量：
```bash
export PYTHONUNBUFFERED=1  # 立即打印日志
python test_scout.py
```

### 检查数据库内容

```python
from database.connection import SessionLocal
from database.models import Faculty, Paper, PaperAuthor

db = SessionLocal()

# 查看所有教师
faculties = db.query(Faculty).all()
print(f"Faculty 表: {len(faculties)} 条记录")

# 查看所有论文
papers = db.query(Paper).all()
print(f"Papers 表: {len(papers)} 条记录")

# 查看所有作者匹配
authors = db.query(PaperAuthor).all()
print(f"PaperAuthor 表: {len(authors)} 条记录")

db.close()
```

### 清除缓存重新测试

```bash
# 删除 pdf 缓存
rm -rf data/pdf_cache/*

# 删除图片缓存
rm -rf data/visual_slices/*

# 重新初始化数据库
python force_init_db.py
```

---

## ✅ 验收标准

| 功能 | 验收标准 | 优先级 |
|-----|--------|--------|
| Scout Agent | ✅ 能从 Crossref 获取元数据且成功率 > 90% | P0 |
| Vision Agent | ✅ 能从 PDF 提取文本长度 > 500 字符 | P0 |
| Judge Agent | ✅ 能匹配教师身份且无数据库错误 | P0 |
| Orchestrator | ✅ 能批量处理 100+ DOI 无崩溃 | P1 |
| UI - 教师名单 | ✅ 能上传、预览、保存 | P1 |
| UI - DOI 提取 | ✅ 进度条更新、表格实时显示 | P1 |
| UI - 统计报表 | ✅ 能显示数据、可筛选、可导出 | P1 |

