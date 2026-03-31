# MAC-ADG 模块接口与边界速查表

**用途**: 新功能开发、问题诊断、模块调用时的快速参考  
**更新**: 2026年3月10日

---

## 清单1: Agent类标准接口

### ScoutAgent

```python
# 导入
from backend.agents.scout_agent import ScoutAgent

# 初始化
agent = ScoutAgent()

# 主方法
agent.run(doi: str) -> Dict
```

| 方法 | 输入 | 输出 | 异常 | 说明 |
|------|------|------|------|------|
| `run()` | doi: "10.1038/..." | {doi, title, journal, publish_date, url, status} | 无(返回error状态) | 获取基本元数据 |
| `fetch_metadata()` | doi: str | {title, journal, date, url} ∣ None | 无 | 私有辅助，调用Crossref API |

**返回状态值**: `"metadata_ready"` ∣ `"error"`

**示例**:
```python
data = ScoutAgent().run("10.1038/s41586-020-2649-2")
# {
#   "doi": "10.1038/s41586-020-2649-2",
#   "title": "Array programming with NumPy",
#   "journal": "Nature",
#   "publish_date": "2020",
#   "url": "https://doi.org/...",
#   "status": "metadata_ready"
# }
```

---

### VisionAgent

```python
# 导入
from backend.agents.vision_agent import VisionAgent

# 初始化
agent = VisionAgent()

# 主方法
agent.process(file_path: str) -> Dict
```

| 方法 | 输入 | 输出 | 异常 | 说明 |
|------|------|------|------|------|
| `process()` | file_path: str | {text, image_path} | 无 | 主流程，忽视输入，内部用DOI |
| `_capture_webpage()` | doi: str | 文件路径 ∣ None | 无 | 浏览器截图 |
| `_mock_vlm_analysis()` | image_path, doi | {text, image_path} | 无 | Mock VLM(待替换) |

**返回文本示例**:
```
"[MOCK OCR DATA for 10.1038_s41586-020-2649-2.png] 
Authors detected in image. Z.P. Liu*, L. Duan#."
```

**性能**: ~40秒/DOI (浏览器启动)

---

### JudgeAgent

```python
# 导入
from backend.agents.judge_agent import JudgeAgent

# 初始化
agent = JudgeAgent()

# 主方法
agent.adjudicate(scout_data: Dict, vision_data: Dict) -> bool
```

| 方法 | 输入 | 输出 | 异常 | 说明 |
|------|------|------|------|------|
| `adjudicate()` | scout_data, vision_data | True ∣ False | 无 | 身份匹配+DB写入 |

**输入详解**:
```python
# scout_data 应包含
{
    "doi": "10.1038/...",
    "title": "...",
    "journal": "...",
    "publish_date": "...",
    # 可选
    "pdf_path" or "html_path": "..."
}

# vision_data 应包含
{
    "text": "Z.P. Liu*, L. Duan#, ...",  # 包含作者名和标记
    "image_path": "data/visual_slices/..."
}
```

**返回含义**:
- `True`: 处理成功(可能0个或多个匹配)
- `False`: 处理失败(异常或DB错误)

**数据库操作**:
- 创建或更新 Paper 记录
- 创建 PaperAuthor 记录(含匹配标记)
- 自动检查& 避免重复

**性能**: ~100-500ms/DOI

---

## 清单2: Orchestrator接口

```python
# 导入
from backend.orchestrator import Orchestrator

# 初始化
orch = Orchestrator()

# 主方法
orch.process_dois(dois: List[str]) -> List[Dict]
orch.process_excel(excel_file) -> List[Dict]
```

| 方法 | 输入 | 输出 | 异常 |
|------|------|------|------|
| `process_dois()` | ["10.1038/...", "10.1234/..."] | [{result1}, {result2}, ...] | ValueError (如列表为空) |
| `process_excel()` | 文件对象(Streamlit或路径) | [{result1}, {result2}, ...] | ValueError(无DOI列) |

**输出记录示例**:
```python
{
    "doi": "10.1038/s41586-020-2649-2",
    "title": "Array programming with NumPy",
    "journal": "Nature",
    "publish_date": "2020",
    "url": "https://doi.org/...",
    "status": "metadata_ready",           # Scout输出
    "vision_text_length": 245,            # Vision输出
    "image_path": "data/visual_slices/...", # Vision输出
    # 如果异常
    "error": "Error message if any"
}
```

**完整流程示例**:
```python
orch = Orchestrator()  # 单次初始化

# 处理DOI列表
results = orch.process_dois([
    "10.1038/s41586-020-2649-2",
    "10.1038/nature12373"
])

for result in results:
    if result.get("error"):
        print(f"❌ {result['doi']}: {result['error']}")
    else:
        print(f"✅ {result['doi']}")
        print(f"   标题: {result['title']}")
        print(f"   文本长度: {result['vision_text_length']}")
```

---

## 清单3: 数据库模型接口

### Faculty (教职员工表)

```python
from database.models import Faculty
from database.connection import get_db

db = next(get_db())
```

| 操作 | 代码 | 说明 |
|------|------|------|
| **创建** | `Faculty(employee_id="E001", name_zh="刘泽萍", name_en_list='["Zeping Liu"]', department="计算机")` | 新建默认status="PENDING" |
| **查询单个** | `db.query(Faculty).filter(Faculty.employee_id == "E001").first()` | 返回一条或None |
| **查询全部** | `db.query(Faculty).all()` | 返回列表 |
| **更新** | `fac.name_zh = "新名字"; db.commit()` | 直接修改对象 |
| **删除** | `db.delete(fac); db.commit()` | 级联删除matched_records |

**关键约束**:
- `employee_id` 是UNIQUE索引
- `name_en_list` 存储为JSON字符串(需json.loads()解析)
- 删除时级联删除PaperAuthor.matched_faculty_id

---

### Paper (论文表)

```python
from database.models import Paper
```

| 操作 | 代码 | 说明 |
|------|------|------|
| **创建** | `Paper(doi="10.1038/...", title="...", journal="...", status="PENDING")` | 必填字段: doi, title, journal |
| **按DOI查** | `db.query(Paper).filter(Paper.doi == "10.1038/...").first()` | 常用于避免重复 |
| **按状态查** | `db.query(Paper).filter(Paper.status == "COMPLETED").all()` | 统计完成的论文 |
| **访问作者** | `paper.authors` | 返回PaperAuthor列表 |
| **获取记录数** | `len(paper.authors)` | 该论文有多少作者 |

**关键约束**:
- `doi` 是PRIMARY KEY
- `status` 有效值: "PENDING", "PROCESSING", "COMPLETED", "ERROR"
- `created_at` 自动设置为当前时间

---

### PaperAuthor (论文作者匹配表)

```python
from database.models import PaperAuthor
```

| 操作 | 代码 | 说明 |
|------|------|------|
| **创建** | `PaperAuthor(paper_doi="10.1038/...", rank=1, raw_name="Z.P. Liu", matched_faculty_id=1, is_corresponding=True)` | match_faculty_id可为NULL |
| **避免重复** | `db.query(PaperAuthor).filter(PaperAuthor.paper_doi=="...", PaperAuthor.matched_faculty_id==1).first()` | 检查是否已存在 |
| **按论文查** | `db.query(PaperAuthor).filter(PaperAuthor.paper_doi=="...").all()` | 某论文的所有作者 |
| **访问论文** | `author.paper` | PaperAuthor→Paper逆向关系 |
| **访问教职** | `author.matched_faculty` | PaperAuthor→Faculty逆向关系(可为None) |

**关键约束**:
- `paper_doi` 必填(FK到Paper.doi)
- `rank` 必填(作者排序)
- `matched_faculty_id` 可为NULL(未匹配)
- `is_corresponding`/`is_co_first` 布尔值，默认False

---

## 清单4: 工具函数接口

### pdf_loader

```python
from backend.utils.pdf_loader import (
    ensure_cache_dir,
    download_file,
    fetch_pdf_by_doi
)
```

| 函数 | 签名 | 返回 | 说明 |
|------|------|------|------|
| `ensure_cache_dir()` | `() -> None` | N/A | 创建PDF_CACHE_DIR目录 |
| `download_file()` | `(url, save_path) -> str \| None` | 文件路径或None | 下载文件(幂等) |
| `fetch_pdf_by_doi()` | `(doi, pdf_url) -> str \| None` | 文件路径或None | 便利函数，自动转换DOI为文件名 |

**缓存文件名规则**:
```
doi "10.1038/s41586-020-2649-2" 
  → "10.1038_s41586-020-2649-2.pdf"
```

**幂等性**: 如果文件已存在，直接返回路径(不重复下载)

---

### excel_parser

```python
from backend.utils.excel_parser import (
    parse_faculty_list,
    generate_name_variants
)
```

| 函数 | 签名 | 返回 | 说明 |
|------|------|------|------|
| `parse_faculty_list()` | `(uploaded_file) -> (List[Dict], str \| None)` | (数据列表, 错误信息) 或 (None, 错误) | 解析Excel文件 |
| `generate_name_variants()` | `(name_str) -> List[str]` | ["Zeping Liu", "Z.P. Liu"] | 生成英文名变体 |

**parse_faculty_list()输出示例**:
```python
(
    [
        {
            "employee_id": "E001",
            "name_zh": "刘泽萍",
            "name_en_list": '["Zeping Liu", "Z.P. Liu"]',  # JSON字符串!
            "department": "计算机学院"
        },
        ...
    ],
    None  # 无错误
)
```

**generate_name_variants()示例**:
```python
# 需要pypinyin库
generate_name_variants("刘泽萍")
# → ["Zeping Liu", "Z.P. Liu"]

# 无pypinyin时
generate_name_variants("刘泽萍")
# → []  (空列表，但不报错)
```

---

## 清单5: Streamlit UI接口

### 文件上传

```python
import streamlit as st

# 文件上传
uploaded_file = st.file_uploader("上传Excel", type=["xlsx"])

if uploaded_file is not None:
    # 方式1: 用工具函数
    from backend.utils.excel_parser import parse_faculty_list
    faculty_data, error = parse_faculty_list(uploaded_file)
    
    # 方式2: 用Orchestrator
    from backend.orchestrator import Orchestrator
    results = Orchestrator().process_excel(uploaded_file)
```

### Orchest调用

```python
# 单次初始化
orch = Orchestrator()

# 处理DOI列表
results = orch.process_dois(dois)

# 实时更新UI
for idx, doi in enumerate(dois):
    result = orch.process_dois([doi])[0]
    progress_bar.progress((idx + 1) / total)
    table_placeholder.dataframe(pd.DataFrame(results))
```

### 组件库

```python
from frontend.components import pdf_preview, labeled_progress

# PDF显示
pdf_preview("data/pdf_cache/file.pdf")

# 进度+标签
text_elem, progress_elem = labeled_progress("处理中...")
progress_elem.progress(0.5)
text_elem.text("已完成50%")
```

---

## 清单6: 状态转移与返回值

### Scout Agent 状态

```
返回 status 字段:
  "metadata_ready"  ✓ 成功获取元数据
  "error"           ✗ 获取失败
```

### Judge Agent 返回

```
返回 bool:
  True  ✓ 成功(可能0个或多个匹配)
  False ✗ 异常(回滚数据库)
```

### Paper.status

```
"PENDING"     初始状态
  ↓
"PROCESSING"  处理中(可选)
  ↓
"COMPLETED"   完成
  ↕ (异常)
"ERROR"       错误
```

### Orchestrator 输出记录状态

```
record.get("status")  # Scout返回的status
record.get("error")   # 异常消息(可选)
record.get("image_path")  # Vision返回的截图路径(可选)
record.get("vision_text_length")  # Vision返回的文本长度(可选)
```

---

## 清单7: 通用错误处理模式

### 模式1: 安全调用Agent(无异常抛出)

```python
def safe_run_agent(agent_func, *args, **kwargs):
    """任何Agent调用都应包装这样的模式"""
    try:
        return agent_func(*args, **kwargs)
    except Exception as e:
        return {"error": str(e)}
```

### 模式2: 数据库操作(with try-finally)

```python
from database.connection import get_db

db = next(get_db())
try:
    # 查询/修改
    result = db.query(Model).filter(...).first()
    if condition:
        db.commit()
    else:
        db.rollback()
finally:
    db.close()  # 确保关闭
```

### 模式3: Orchestrator使用(单次初始化)

```python
# ✅ 正确
orch = Orchestrator()
for doi in dois:
    result = orch.process_dois([doi])[0]

# ❌ 错误(浪费资源)
for doi in dois:
    orch = Orchestrator()  # 每次初始化
    result = orch.process_dois([doi])[0]
```

---

## 清单8: 依赖导入速查

### 后端核心

```python
# Agent
from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent

# 编排
from backend.orchestrator import Orchestrator

# 工具
from backend.utils.pdf_loader import fetch_pdf_by_doi
from backend.utils.excel_parser import parse_faculty_list, generate_name_variants
```

### 数据库

```python
# 连接
from database.connection import get_db, init_db, SessionLocal

# 模型
from database.models import Faculty, Paper, PaperAuthor, Base

# ORM
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
```

### 配置

```python
from config import (
    BASE_DIR,
    DATA_DIR,
    PDF_CACHE_DIR,
    HTML_CACHE_DIR,
    VISUAL_SLICE_DIR,
    DB_PATH,
    HEADERS
)
```

### 前端

```python
import streamlit as st
import pandas as pd
from frontend.components import pdf_preview, labeled_progress
```

---

## 清单9: 常见调用场景

### 场景1: 处理单个DOI

```python
from backend.orchestrator import Orchestrator

orch = Orchestrator()
result = orch.process_dois(["10.1038/..."])[0]

if "error" in result:
    print(f"失败: {result['error']}")
else:
    print(f"成功: {result['title']}")
```

### 场景2: 导入教职员工列表

```python
from backend.utils.excel_parser import parse_faculty_list
from database.connection import get_db
from database.models import Faculty

faculty_data, error = parse_faculty_list(excel_file)
if error:
    print(f"解析失败: {error}")
else:
    db = next(get_db())
    try:
        for data in faculty_data:
            existing = db.query(Faculty).filter(
                Faculty.employee_id == data['employee_id']
            ).first()
            if not existing:
                db.add(Faculty(**data))
        db.commit()
    finally:
        db.close()
```

### 场景3: 查看某篇论文的作者

```python
from database.connection import get_db
from database.models import Paper

db = next(get_db())
try:
    paper = db.query(Paper).filter(Paper.doi == "10.1038/...").first()
    if paper:
        for author in paper.authors:
            faculty_name = author.matched_faculty.name_zh if author.matched_faculty else "未匹配"
            print(f"{author.raw_name} → {faculty_name}")
finally:
    db.close()
```

### 场景4: 统计匹配结果

```python
from database.connection import get_db
from database.models import PaperAuthor

db = next(get_db())
try:
    all_authors = db.query(PaperAuthor).all()
    matched = sum(1 for a in all_authors if a.matched_faculty_id is not None)
    print(f"总作者数: {len(all_authors)}")
    print(f"已匹配: {matched} ({100*matched/len(all_authors):.1f}%)")
finally:
    db.close()
```

---

## 清单10: 边界检查清单(开发前必读)

### 在调用任何功能前实施的检查

```python
# ✅ Check 1: 导入路径正确
from backend.agents.scout_agent import ScoutAgent  # ✓
# from agents.scout_agent import ScoutAgent  # ✗ 错误路径

# ✅ Check 2: 使用正确的初始化方式
db = next(get_db())  # ✓
# db = SessionLocal()  # ✗ 缺少关闭逻辑

# ✅ Check 3: Agent 避免重复初始化
orch = Orchestrator()
for doi in dois:
    orch.process_dois([doi])  # ✓ 复用
# 而不是 Orchestrator().process_dois(...)  # ✗ 每次初始化

# ✅ Check 4: 状态值使用常数
status = "COMPLETED"  # ✓
# status = "complete"  # ✗ 错误拼写

# ✅ Check 5: 异常处理
try:
    result = agent.run(...)  # 不会抛异常
except Exception as e:
    ...  # 实际上这里不会执行
    
# 而不是
result = agent.run(...)
if result.get("error"):  # ✓ 检查返回值
    handle_error(result["error"])

# ✅ Check 6: 重复检查
existing = db.query(PaperAuthor).filter(...).first()
if not existing:  # ✓
    db.add(PaperAuthor(...))
# 而不是直接 db.add  # ✗ 可能重复

# ✅ Check 7: 会话关闭
finally:
    db.close()  # ✓ 必须
```

---

## 参考文档

| 文档 | 用途 |
|------|------|
| ARCHITECTURE_MAP.md | 深度架构分析 |
| DEVELOPER_QUICK_GUIDE.md | 日常开发参考 |
| CODE_REVIEW_REPORT.md | 审查总结与改进建议 |
| 本文件 | 接口与边界速查 |

---

**最后更新**: 2026年3月10日  
**版本**: 1.0  
**维护者**: MAC-ADG 技术团队
