# MAC-ADG 开发者快速参考指南

**最后更新**: 2026年3月10日

---

## 快速导航

### 🎯 我想要...

#### 处理新的DOI列表
```python
from backend.orchestrator import Orchestrator

orch = Orchestrator()
results = orch.process_dois(["10.1038/...", "10.1234/..."])
# 结果: List[Dict] 包含所有阶段的数据
```

#### 获取数据库会话
```python
from database.connection import get_db
from sqlalchemy.orm import Session

db: Session = next(get_db())
try:
    # 查询/修改
    papers = db.query(Paper).filter(Paper.status == "COMPLETED").all()
finally:
    db.close()
```

#### 上传教职员工列表
```python
from backend.utils.excel_parser import parse_faculty_list

faculty_data, error = parse_faculty_list(uploaded_file)
if error:
    print(f"错误: {error}")
else:
    # faculty_data 是可以直接插入Faculty表的字典列表
    for data in faculty_data:
        faculty = Faculty(**data)
        db.add(faculty)
    db.commit()
```

#### 调试某个特定DOI
```python
# 方式1: 用Orchestrator（推荐）
from backend.orchestrator import Orchestrator
results = Orchestrator().process_dois(["10.1038/s41586-020-2649-2"])
print(results[0])

# 方式2: 逐阶段调试
from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent

scout_data = ScoutAgent().run("10.1038/s41586-020-2649-2")
print("Scout:", scout_data)

vision_data = VisionAgent().process(scout_data.get("pdf_path"))
print("Vision:", vision_data)

judge_result = JudgeAgent().adjudicate(scout_data, vision_data)
print("Judge:", judge_result)
```

#### 手动创建Paper记录
```python
from database.models import Paper, PaperAuthor
from database.connection import get_db

db = next(get_db())
try:
    paper = Paper(
        doi="10.1234/test",
        title="Test Paper",
        journal="Test Journal",
        publish_date="2024",
        status="COMPLETED"
    )
    db.add(paper)
    db.flush()  # 获取ID（如果需要）
    
    # 创建作者记录
    author = PaperAuthor(
        paper_doi=paper.doi,
        rank=1,
        raw_name="John Doe",
        is_corresponding=True
    )
    db.add(author)
    db.commit()
finally:
    db.close()
```

#### 查询匹配结果
```python
db = next(get_db())
try:
    # 查看某篇论文的所有作者
    paper = db.query(Paper).filter(Paper.doi == "10.1038/...").first()
    for author in paper.authors:
        print(f"{author.raw_name} -> {author.matched_faculty.name_zh if author.matched_faculty else '未匹配'}")
    
    # 查看某个教职员工的所有论文
    faculty = db.query(Faculty).filter(Faculty.name_zh == "刘泽萍").first()
    for match in faculty.matched_records:
        print(f"{match.paper.title}")
finally:
    db.close()
```

#### 初始化或重置数据库
```python
from database.connection import init_db

init_db()  # 会创建所有表（如果不存在）
```

#### 添加新的配置常数
编辑 `config.py`:
```python
# 添加新路径
NEW_CACHE_DIR = os.path.join(DATA_DIR, 'new_cache')

# 或新的HTTP头规则
HEADERS_WITH_COOKIE = {
    **HEADERS,  # 继承现有headers
    "Cookie": "..."
}
```

---

## 常用命令

### 测试&验证

```bash
# 运行Scout Agent测试
python test_scout.py

# 运行Vision Agent测试
python test_vision.py

# 运行Judge Agent测试
python test_judge.py

# 运行完整管道测试
python test_orchestrator.py

# 快速验证系统状态
python quick_verify.py

# 启动Streamlit UI
streamlit run main.py
```

### 数据库操作

```bash
# 从Python交互shell重置数据库
python -c "from database.connection import init_db; init_db()"

# 导出数据库数据（待实现）
# python export_data.py  (output: exports/data.xlsx)
```

---

## 状态参考表

### Paper.status 状态转移

```
PENDING ──Scout── PROCESSING ──Vision── PROCESSING ──Judge── COMPLETED
                        │                                          │
                        └──────────────────────────────────────────┘
                                    (发生错误)
                        │                        │
                        └────────────────────────┴──────→ ERROR
```

### Vision Agent 返回状态

| 值 | 意义 | 后续处理 |
|----|------|---------|
| `success_pdf` | 成功下载PDF | Vision处理PDF |
| `success_html` | 获得HTML缓存 | Vision处理HTML |
| `metadata_only` | 仅有元数据 | 跳过Vision（无法处理） |
| `error` | 获取失败 | 记录错误，跳过后续 |

### Judge Agent 匹配标记

| 标记 | 含义 | 数据库字段 |
|------|------|----------|
| `*` | 对应作者 (Corresponding Author) | `is_corresponding=True` |
| `#` | 共同第一作者 (Co-First Author) | `is_co_first=True` |
| 无标记 | 普通作者 | 两字段都为`False` |

---

## 文件结构速查

```
MAC_ADG_System/
├── config.py                    # 全局配置 ⭐⭐⭐
├── main.py                      # Streamlit入口
├── requirements.txt             # 依赖列表
│
├── database/
│   ├── connection.py           # DB引擎、SessionLocal ⭐⭐
│   ├── models.py               # Faculty、Paper、PaperAuthor ⭐⭐⭐
│   └── __init__.py
│
├── backend/
│   ├── orchestrator.py         # 主编排器 ⭐⭐⭐
│   ├── agents/
│   │   ├── scout_agent.py      # Crossref API ⭐⭐
│   │   ├── vision_agent.py     # Playwright截图 ⭐⭐
│   │   ├── judge_agent.py      # 身份匹配 ⭐⭐⭐
│   │   └── __init__.py
│   ├── utils/
│   │   ├── pdf_loader.py       # 文件下载缓存 ⭐
│   │   ├── excel_parser.py     # Excel解析 ⭐⭐
│   │   └── __init__.py
│   └── __init__.py
│
├── frontend/
│   ├── components.py           # UI组件库
│   ├── pages/
│   │   ├── 1_Data_Management.py
│   │   ├── 2_Smart_Extraction.py
│   │   └── 3_Export_Reports.py
│   └── __init__.py
│
├── pages/
│   ├── 1_Data_Management.py
│   ├── 2_Smart_Extraction.py   # ⭐ 主工作页面
│   └── 3_Analytics_Reports.py
│
├── data/
│   ├── pdf_cache/              # PDF本地缓存
│   ├── html_cache/             # HTML本地缓存
│   ├── visual_slices/          # 网页截图
│   ├── exports/                # 导出报告
│   └── mac_adg.db              # SQLite数据库文件
│
├── test/
├── test_scout.py               # Scout测试
├── test_vision.py              # Vision测试
├── test_judge.py               # Judge测试
├── test_orchestrator.py        # 管道测试
├── quick_verify.py             # 快速检查
└── ARCHITECTURE_MAP.md         # 本架构文档
```

**⭐ 标记**: 星数越多越重要。3星=必读，2星=常用，1星=参考

---

## 常见问题排查

### Q1: Scout Agent返回 {"status": "error"}

**可能原因**:
- DOI格式错误
- Crossref API服务异常
- 网络超时

**调试**:
```python
from backend.agents.scout_agent import ScoutAgent
agent = ScoutAgent()
result = agent.fetch_metadata("10.1038/s41586-020-2649-2")
print(result)  # 检查是否为None
```

**解决**:
- 验证DOI格式 (通常是 `10.xxxx/xxxxx`)
- 尝试在浏览器中访问 `https://api.crossref.org/works/{doi}` 测试连接

---

### Q2: Vision Agent超时或失败

**可能原因**:
- Target网站无法访问（国内IP被限制）
- Playwright配置问题
- 浏览器进程未正确关闭

**调试**:
```python
from backend.agents.vision_agent import VisionAgent
agent = VisionAgent()
image_path = agent._capture_webpage("10.1038/s41586-020-2649-2")
print(f"Image: {image_path}")  # 检查是否为None
```

**解决**:
- 检查网络连接，尤其是到`https://doi.org/`的访问
- 增加超时时间 (修改 `vision_agent.py` 中的 `timeout=45000`)
- 确保已安装 `playwright` 和 `playwright-stealth`:
  ```bash
  pip install playwright playwright-stealth
  playwright install chromium
  ```

---

### Q3: Judge Agent匹配率低

**可能原因**:
- Faculty表为空
- 教职员工名字变体不完整
- Vision Agent返回的文本格式异常

**调试**:
```python
from database.connection import get_db
from database.models import Faculty

db = next(get_db())
faculties = db.query(Faculty).all()
print(f"Faculty count: {len(faculties)}")
for fac in faculties[:3]:
    print(f"  {fac.name_zh} -> {fac.name_en_list}")
db.close()
```

**解决**:
1. 确保Faculty表已导入教职员工列表
2. 检查名字变体生成 (使用 `generate_name_variants()` 测试)
   ```python
   from backend.utils.excel_parser import generate_name_variants
   print(generate_name_variants("刘泽萍"))  # 应输出转换后的英文名
   ```
3. 检查Vision Agent返回的文本格式

---

### Q4: 数据库锁定错误 (database is locked)

**可能原因**:
- 多个进程同时访问SQLite
- 前一个会话未正确关闭

**解决**:
```python
# ✅ 正确做法
from database.connection import get_db

db = next(get_db())
try:
    # 操作
    db.commit()
finally:
    db.close()  # 确保关闭
```

---

### Q5: 文件路径问题 (FileNotFoundError)

**可能原因**:
- `data/` 文件夹不存在
- 使用了相对路径而非绝对路径

**解决**:
```python
# ✅ 正确：使用config.py中的常数
from config import PDF_CACHE_DIR
import os
os.makedirs(PDF_CACHE_DIR, exist_ok=True)

# ❌ 错误：硬编码相对路径
file_path = "data/cache/file.pdf"
```

---

## 性能优化建议

### 当前瓶颈

1. **Vision Agent**: ~40秒/DOI (浏览器启动最耗时)
   - 优化方向: 复用浏览器进程、并发控制

2. **Judge Agent**: ~100-500ms/DOI (取决于Faculty数量)
   - 优化方向: 添加全文索引、批量查询

3. **Scout Agent**: ~1秒/DOI (网络延迟)
   - 优化方向: 缓存、批量API

### 快速优化

```python
# 优化1: 缓存Scout结果
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_fetch_metadata(doi):
    # Scout Agent调用
    pass

# 优化2: 批量Judge操作
def batch_adjudicate(paper_list):
    """一次性处理多篇论文的匹配，共用一个DB连接"""
    db = next(get_db())
    try:
        for paper_data in paper_list:
            JudgeAgent().adjudicate(paper_data, ...)
        db.commit()  # 一次提交
    finally:
        db.close()
```

---

## 常用代码片段库

### 片段1: 导入所有必要模块
```python
# 前端
import streamlit as st
import pandas as pd

# 后端
from backend.orchestrator import Orchestrator
from backend.agents.scout_agent import ScoutAgent
from backend.agents.vision_agent import VisionAgent
from backend.agents.judge_agent import JudgeAgent

# 数据库
from database.connection import get_db, init_db
from database.models import Faculty, Paper, PaperAuthor
from sqlalchemy.orm import Session

# 工具
from backend.utils.excel_parser import parse_faculty_list, generate_name_variants
from backend.utils.pdf_loader import fetch_pdf_by_doi

# 配置
from config import BASE_DIR, PDF_CACHE_DIR, DB_PATH, HEADERS
```

### 片段2: 完整的DOI处理+数据库保存
```python
doi = "10.1038/s41586-020-2649-2"
orch = Orchestrator()
result = orch.process_dois([doi])[0]

if result.get("error"):
    print(f"处理失败: {result['error']}")
else:
    print(f"✅ 成功处理 {result['doi']}")
    print(f"  标题: {result['title']}")
    print(f"  文本长度: {result.get('vision_text_length')} chars")
    
    # 查看数据库结果
    db = next(get_db())
    try:
        paper = db.query(Paper).filter(Paper.doi == doi).first()
        print(f"  数据库记录数: {len(paper.authors)}")
    finally:
        db.close()
```

### 片段3: 批量导入教职员工&测试匹配
```python
import io
import openpyxl

# 假设已有Streamlit上传的Excel文件
faculty_data, error = parse_faculty_list(uploaded_file)

if not error:
    db = next(get_db())
    try:
        for data in faculty_data:
            # 检查重复
            existing = db.query(Faculty).filter(
                Faculty.employee_id == data['employee_id']
            ).first()
            
            if not existing:
                faculty = Faculty(**data)
                db.add(faculty)
        
        db.commit()
        st.success(f"✅ 导入{len(faculty_data)}名教职员工")
    except Exception as e:
        db.rollback()
        st.error(f"❌ 导入失败: {e}")
    finally:
        db.close()
```

---

## 扩展和修改指南

### 如何添加新的Agent类型

```python
# 1. 创建文件 backend/agents/new_agent.py
class NewAgent:
    def __init__(self):
        pass
    
    def run(self, input_data):
        """
        标准接口：接受输入，返回Dict
        """
        result = {}
        try:
            # 处理逻辑
            result["status"] = "success"
        except Exception as e:
            result["error"] = str(e)
        return result

# 2. 在 Orchestrator 中集成
class Orchestrator:
    def __init__(self):
        # ...
        self.new_agent = NewAgent()
    
    def process_dois(self, dois):
        for doi in dois:
            # ...
            new_data = self.new_agent.run(previous_data)

# 3. 在 __init__.py 中导出
# backend/agents/__init__.py
from .new_agent import NewAgent
```

### 如何修改数据模型

```python
# 1. 编辑 database/models.py，添加新列
class Paper(Base):
    # ... 现有列 ...
    custom_field = Column(String, nullable=True)

# 2. 删除旧数据库（开发环境）
import os
os.remove("data/mac_adg.db")

# 3. 重新初始化
from database.connection import init_db
init_db()
```

### 如何添加新的Streamlit页面

```python
# 1. 创建 pages/4_New_Feature.py
import streamlit as st

st.set_page_config(page_title="New Feature", layout="wide")
st.title("🆕 New Feature")

# 页面逻辑...

# 2. Streamlit会自动识别并添加到左侧导航栏
```

---

## 资源链接

- [Streamlit文档](https://docs.streamlit.io/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20/)
- [Playwright API](https://playwright.dev/python/)
- [Crossref API](https://github.com/CrossRef/rest-api-doc)
- [Python Type Hints](https://peps.python.org/pep-0484/)

---

**更新日期**: 2026年3月10日  
**维护者**: MAC-ADG技术团队  
**下一次审查**: 2026年4月（或新功能发布时）
