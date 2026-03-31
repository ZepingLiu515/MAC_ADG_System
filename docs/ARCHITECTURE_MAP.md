# MAC-ADG 系统完整代码地图与架构分析

**生成日期**: 2026年3月10日  
**项目**: MAC-ADG 科研文献关键信息智能提取系统  
**状态**: 完整分析（基于当前代码库v1.0）

---

## 目录

1. [全局架构](#全局架构)
2. [代码分层详解](#代码分层详解)
3. [模块依赖关系](#模块依赖关系)
4. [数据流向图](#数据流向图)
5. [实现约束清单](#实现约束清单)

---

## 全局架构

```
┌─────────────────────────────────────────────────────────────┐
│                       STREAMLIT 前端层                       │
│  (pages/2_Smart_Extraction.py + frontend/components.py)     │
│                 负责：UI交互、文件上传、结果展示              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    编排层 (ORCHESTRATOR)                      │
│            backend/orchestrator.py 协调三阶段流水线           │
│            负责：流程控制、异常处理、结果汇总                 │
└──────────────┬─────────┬─────────┬──────────────────────────┘
               │         │         │
      ┌────────▼──┐ ┌───▼──────┐ ┌▼────────────┐
      │  Scout    │ │ Vision   │ │   Judge     │
      │   Agent   │ │  Agent   │ │   Agent     │
      │           │ │          │ │             │
      │• Metadata │ │• 浏览器  │ │• 身份匹配   │
      │  HTTP API │ │  自动化  │ │• 数据库持久化
      │• crossref │ │• 截图   │ │• Faculty匹配│
      │  /unpywl │ │• 图像保存│ │• 标记检测   │
      └────┬───────┘ └───┬──────┘ └▼────────────┘
           │             │         │
           └─────────────┼─────────┘
                         │
      ┌──────────────────▼──────────────────┐
      │     工具库 (BACKEND/UTILS)          │
      │  • excel_parser      名字转换        │
      │  • pdf_loader        文件缓存管理    │
      └──────────────────────────────────────┘
               │                  │
      ┌────────▼──────┐  ┌────────▼────────┐
      │   Faculty     │  │   Paper Author  │
      │  Data Cache   │  │   Database      │
      │ (内存/文件)    │  │  (SQLite DB)    │
      └───────────────┘  └─────────────────┘
```

---

## 代码分层详解

### 第1层：配置层 (config.py)

**位置**: `config.py`  
**职责**: 全局配置管理

#### 关键配置项

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `BASE_DIR` | str | 项目根目录路径 |
| `DATA_DIR` | str | 数据文件夹 (`data/`) |
| `DB_PATH` | str | SQLite数据库路径 |
| `PDF_CACHE_DIR` | str | PDF缓存文件夹 |
| `HTML_CACHE_DIR` | str | HTML缓存文件夹 |
| `VISUAL_SLICE_DIR` | str | 网页截图文件夹 |
| `EXPORT_DIR` | str | 报告导出文件夹 |
| `HEADERS` | dict | Chrome浏览器User-Agent等HTTP头 |

#### 代码示例

```python
from config import PDF_CACHE_DIR, HEADERS, DB_PATH

# 直接使用路径常数
pdf_local = os.path.join(PDF_CACHE_DIR, "paper.pdf")

# 使用HTTP头规避反爬虫
requests.get(url, headers=HEADERS)
```

**当前状态**: ✅ 完整实现，包含反爬虫头配置

---

### 第2层：数据库层

#### 2.1 连接管理 (database/connection.py)

**职责**: 数据库引擎、会话工厂、初始化

```python
# 核心对象
engine              # SQLAlchemy引擎（SQLite）
SessionLocal        # session工厂类
get_db()            # 依赖注入函数（返回Generator）
init_db()           # 初始化表结构
```

**关键方法签名**:
```python
def get_db() -> Generator[Session, None, None]:
    """获取数据库会话，确保关闭"""
    
def init_db() -> None:
    """创建所有表，确保data/目录存在"""
```

**当前状态**: ✅ 实现完整

#### 2.2 数据模型 (database/models.py)

**三表结构设计**:

##### 表1: Faculty（教职员工参考表）
```python
class Faculty(Base):
    __tablename__ = 'faculty'
    
    id                  # PK: 自增ID
    employee_id (unique)# 工号（唯一，用于防重复）
    name_zh            # 中文名
    name_en_list (JSON)# 英文名变量列表 ["Zeping Liu", "Z.P. Liu"]
    department         # 部门
    
    # 外键关系
    matched_records    # 反向关系 → PaperAuthor.matched_faculty
```

**用途**: Judge Agent的匹配数据源

##### 表2: Paper（论文基本信息）
```python
class Paper(Base):
    __tablename__ = 'papers'
    
    doi (PK)           # 唯一标识符
    title              # 论文题目
    journal            # 期刊名
    publish_date       # 发表日期
    pdf_path           # 本地PDF/HTML路径
    status             # 处理状态 [PENDING/PROCESSING/COMPLETED/ERROR]
    created_at         # 创建时间戳
    
    # 外键关系
    authors            # 正向关系 → PaperAuthor
```

**关键约束**:
- `status` 值定义: `"PENDING"` → `"PROCESSING"` → `"COMPLETED"` | `"ERROR"`
- `created_at` 自动时间戳

##### 表3: PaperAuthor（论文作者匹配记录）
```python
class PaperAuthor(Base):
    __tablename__ = 'paper_authors'
    
    id (PK)
    paper_doi (FK)     # 关联到Paper.doi
    rank               # 作者排序 (1, 2, 3...)
    raw_name           # 原始名字（来自VisionAgent）
    raw_affiliation    # 原始单位
    
    # 贡献标记（由Vision Agent设置）
    is_corresponding   # 对应作者标记 (*)
    is_co_first        # 共同第一作者标记 (#)
    
    # 身份匹配（由Judge Agent设置）
    matched_faculty_id (FK) # 关联到Faculty.id
    
    # 外键关系
    paper              # 反向关系 → Paper.authors
    matched_faculty    # 反向关系 → Faculty.matched_records
```

**关键约束**:
- `rank` 必填，表示作者在论文中的顺序
- `is_corresponding` / `is_co_first` 由Vision Agent根据符号检测设置
- `matched_faculty_id` 可为NULL（未匹配的作者）

**当前状态**: ✅ 三表完整，关系定义清晰

---

### 第3层：代理层 (backend/agents/)

#### 3.1 Scout Agent (scout_agent.py)

**职责**: 获取论文基本元数据（从Crossref API）

**核心方法**

```python
class ScoutAgent:
    def run(doi: str) -> Dict:
        """
        输入: DOI字符串，如 "10.1038/s41586-020-2649-2"
        输出: 
            {
                "doi": str,
                "title": str,
                "journal": str,
                "publish_date": str,
                "url": str,
                "status": "metadata_ready"  # 固定值
            }
        抛出: 无（返回error状态）
        """
        
    def fetch_metadata(doi: str) -> Dict | None:
        """
        步骤:
        1. 调用 https://api.crossref.org/works/{doi}
        2. 解析JSON，提取title/journal/date
        3. 返回字典或None
        """
```

**关键特性**:
- ✅ 使用全局 `HEADERS` 规避反爬虫
- ✅ 10秒超时防止卡顿
- ✅ 错误时返回 `{"status": "error", ...}` 而非抛出异常

**当前状态**: ✅ 精简版（只获取元数据，不下载PDF）

**性能**: 每个DOI ~1秒 (Crossref API延迟)

---

#### 3.2 Vision Agent (vision_agent.py)

**职责**: 驱动浏览器截图，模拟VLM解析作者信息

**核心方法**

```python
class VisionAgent:
    def process(file_path: str) -> Dict:
        """
        输入: 文件路径（PDF或HTML，但目前不使用）
             实际使用DOI: self._capture_webpage()会重新拼接
        输出:
            {
                "text": str,           # 模拟VLM提取的文本
                "image_path": str,     # 截图保存路径
            }
        """
        
    def _capture_webpage(doi: str) -> str | None:
        """
        步骤:
        1. 使用 playwright 启动无头浏览器
        2. 注入 playwright_stealth 以规避反爬虫
        3. 导航到 https://doi.org/{doi}
        4. 等待页面加载 + 额外4秒
        5. 截图并保存到 VISUAL_SLICE_DIR/{safe_doi}.png
        6. 返回文件路径或None
        
        超时: 45秒（wait_until="domcontentloaded"）
        """
        
    def _mock_vlm_analysis(image_path: str, doi: str) -> Dict:
        """
        当前: 直接返回Mock数据
        
        未来集成:
        - 调用 DeepSeek-VL API
        - 发送截图
        - 获取OCR结果（包含作者名、对应作者标记*、共同一作标记#）
        """
```

**关键特性**:
- ✅ Playwright + Stealth 规避反爬虫
- ✅ 截图分辨率 1920x1080，确保清晰度
- ⚠️ 当前使用Mock VLM（生产前需接入DeepSeek-VL）

**当前状态**: ⚠️ 半完成（截图成功，VLM集成待完成）

**性能**: 每个DOI ~30-50秒 (浏览器启动+导航+截图)

**已知问题**:
- DeepSeek-VL 集成未实现，目前返回Mock数据
- 需要在生产前集成真实VLM API调用

---

#### 3.3 Judge Agent (judge_agent.py)

**职责**: 身份匹配、数据库持久化

**核心方法**

```python
class JudgeAgent:
    def adjudicate(scout_data: Dict, vision_data: Dict) -> bool:
        """
        输入:
            scout_data: {doi, title, journal, publish_date, ...}
            vision_data: {text: str (包含作者名), image_path: str}
        
        处理步骤:
        1. 从 vision_data.text 中提取作者列表（VLM已完成）
        2. 在Faculty表中查找匹配
        3. 检测 * (对应作者) 和 # (共同一作) 标记
        4. 创建Paper + PaperAuthor记录
        5. 提交事务
        
        返回: True（成功）| False（失败）
        """
```

**匹配算法**

```
For each faculty in Faculty表:
    For each name_variant in name_en_list + name_zh:
        if name_variant in vision_data.text.lower():
            found = True
            # 检测标记
            snippet = vision_data.text[...found_name周围...]
            is_corresponding = "*" in snippet
            is_co_first = "#" in snippet
            
            # 创建匹配记录
            PaperAuthor(
                matched_faculty_id=faculty.id,
                is_corresponding=is_corresponding,
                is_co_first=is_co_first,
                ...
            )
```

**关键特性**:
- ✅ 支持中文/英文名匹配
- ✅ 检测 `*` 和 `#` 标记
- ✅ 避免重复记录（检查existing_link）
- ✅ 所有操作在单个事务内

**当前状态**: ✅ 完整实现

**性能**: ~100-500ms （取决于Faculty数量）

**当前局限**:
- 字符串匹配基于 `in` 操作符（大小写不敏感）
- 不支持模糊匹配 (Levenshtein distance)
- 不支持拼音缩写识别（如"ZP"→"Zeping"）

---

### 第4层：编排层 (backend/orchestrator.py)

**职责**: 协调Scout→Vision→Judge三阶段流水线

**核心类**

```python
class Orchestrator:
    """中央协调器，统一管理端到端流程"""
    
    def __init__(self):
        self.scout = ScoutAgent()
        self.vision = VisionAgent()
        self.judge = JudgeAgent()
    
    def process_dois(dois: List[str]) -> List[Dict]:
        """
        输入: ["10.1038/...", "10.1234/..."]
        
        流程:
        For each doi:
            1. Scout.run(doi) -> scout_data
            2. Vision.process() -> vision_data
            3. Judge.adjudicate(scout_data, vision_data) -> True/False
        
        输出: List[Dict]
            每条记录包含:
            - doi, title, journal, publish_date (来自Scout)
            - vision_text_length (来自Vision)
            - error (如果异常)
        """
        
    def process_excel(excel_file) -> List[Dict]:
        """
        步骤:
        1. pd.read_excel(excel_file)
        2. 自动找到 "DOI" 列
        3. 调用 process_dois()
        
        异常: ValueError("Excel file must contain a 'DOI' column")
        """
```

**设计特点**:
- 🎯 **中央化**: 避免Streamlit页面重复流程逻辑
- 🔄 **可重用**: CLI、API、Streamlit都可调用
- 🛡️ **容错**: 单个DOI失败不阻断整个流程

**当前状态**: ✅ 完整实现，已集成Streamlit页面

---

### 第5层：工具库 (backend/utils/)

#### 5.1 PDF Loader (pdf_loader.py)

**职责**: 文件下载、缓存管理（DRY原则）

```python
def ensure_cache_dir() -> None:
    """确保PDF_CACHE_DIR目录存在"""
    
def download_file(url: str, save_path: str) -> str | None:
    """
    步骤:
    1. 如果文件已存在，直接返回（幂等性）
    2. GET请求，流式下载
    3. 保存到save_path
    4. 返回save_path或None（失败）
    
    特性: 支持大文件（流式）、超时30秒、禁用SSL验证
    """
    
def fetch_pdf_by_doi(doi: str, pdf_url: str) -> str | None:
    """
    便利函数：直接用DOI和URL获取PDF
    
    缓存文件名规则: doi.replace("/", "_") + ".pdf"
    示例: "10.1038_s41586-020-2649-2.pdf"
    """
```

**当前状态**: ✅ 完整实现

**使用场景**:
```python
# Scout Agent中使用
from backend.utils.pdf_loader import fetch_pdf_by_doi
local_path = fetch_pdf_by_doi(doi, pdf_url)
```

#### 5.2 Excel Parser (excel_parser.py)

**职责**: 教职员工列表解析、名字转换

```python
def parse_faculty_list(uploaded_file) -> Tuple[List[Dict], str | None]:
    """
    输入: Streamlit上传的Excel文件对象
    
    处理:
    1. 读取Excel（ID列强制为字符串）
    2. 检查必需列: ["Name", "ID", "Department"]
    3. 为每个教职员工生成英文名变量
    4. 返回字典列表 (适配Faculty模型)
    
    输出:
        ([{employee_id, name_zh, name_en_list, department}, ...], None)  # 成功
        (None, "错误消息")  # 失败
    """
    
def generate_name_variants(name_str: str) -> List[str]:
    """
    输入: 中文全名 "刘泽萍"
    输出: ["Zeping Liu", "Z.P. Liu"]
    
    算法:
    1. 尝试使用pypinyin库转换：lazy_pinyin(name_str)
    2. 假设最后一个音节是姓氏
    3. 生成变体:
       - "名字 姓氏" (e.g., "Zeping Liu")
       - "缩写. 姓氏" (e.g., "Z.P. Liu")
    4. 如果pypinyin不可用，返回空列表（Judge会用中文名匹配）
    """
```

**当前状态**: ✅ 完整实现，包含pypinyin依赖处理

**关键改进** (vs 初版):
- 支持pinyin转换（需要 `pypinyin` 库）
- 生成多个变体提高匹配成功率
- 优雅降级（无pypinyin时不报错）

---

### 第6层：前端层

#### 6.1 Streamlit 页面 (pages/2_Smart_Extraction.py)

**职责**: 用户界面、任务提交、结果展示

**核心流程**

```python
st.file_uploader(...)  # 1. 上传Excel文件

if st.button("🚀 启动流水线"):
    # 2. 初始化Orchestrator
    orchestrator = Orchestrator()
    
    # 3. 逐行处理DOI
    for doi in dois:
        record = orchestrator.process_dois([doi])[0]
        
        # 4. 状态映射（适配UI）
        if record.get("image_path"):
            gui_status = "📸 网页已截图"
        elif record.get("status") == "metadata_ready":
            gui_status = "⚠️ 仅元数据"
        else:
            gui_status = "❌ 失败"
        
        # 5. 动态更新表格
        table_placeholder.dataframe(...)
```

**关键UI元素**:
- 文件上传器 (type=["xlsx"])
- 进度条 (progress_bar)
- 动态表格 (dataframe)
- 状态框 (st.empty())

**当前状态**: ✅ 完整实现，已优化为使用Orchestrator

#### 6.2 组件库 (frontend/components.py)

**当前实现**:

```python
def pdf_preview(file_path: str, width: int = 600) -> None:
    """展示PDF下载按钮（不支持嵌入式预览）"""
    
def labeled_progress(label: str) -> Tuple[TextElement, ProgressBar]:
    """返回文本+进度条对，便于动态更新"""
```

**当前状态**: ⚠️ 最小化实现（仅2个函数）

**建议增强**:
- 添加任务历史表格展示
- 添加错误日志查看器
- 添加导出功能（PDF报告）

---

## 模块依赖关系

### 依赖图

```
main.py
    └─→ pages/2_Smart_Extraction.py
         └─→ backend.orchestrator (Orchestrator)
              ├─→ backend.agents.scout_agent (ScoutAgent)
              │    └─→ config (HEADERS)
              │
              ├─→ backend.agents.vision_agent (VisionAgent)
              │    └─→ config (VISUAL_SLICE_DIR)
              │
              └─→ backend.agents.judge_agent (JudgeAgent)
                   ├─→ database.connection (get_db, SessionLocal)
                   ├─→ database.models (Faculty, Paper, PaperAuthor)
                   └─→ config (无直接依赖)

backend.utils.pdf_loader
    └─→ config (PDF_CACHE_DIR, HEADERS)

backend.utils.excel_parser
    └─→ database.models (Faculty模型定义)
    └─→ (可选) pypinyin (名字转换)

database.models
    └─→ sqlalchemy

database.connection
    └─→ database.models
    └─→ sqlalchemy
```

### 导入规范

| 模块 | 导入方式 | 场景 |
|------|--------|------|
| config | `from config import ...` | 全局常数 |
| models | `from database.models import Faculty, Paper, PaperAuthor` | ORM对象 |
| connection | `from database.connection import get_db, SessionLocal, init_db` | DB会话 |
| Orchestrator | `from backend.orchestrator import Orchestrator` | 主流程 |
| Agent | `from backend.agents.{agent} import {Agent}Class` | 子流程 |
| Utils | `from backend.utils.{util} import function` | 工具函数 |

---

## 数据流向图

### 完整端到端流水线

```
┌─────────────────┐
│  用户上传Excel  │  含DOI列表
├─────────────────┤
│  Streamlit UI   │
│  pages/2_*.py   │
└────────┬────────┘
         │
         │ DOI列表
         ▼
┌─────────────────────────────────────┐
│  Orchestrator.process_excel()       │
│  Orchestrator.process_dois([...]）  │
└────┬───────────────┬───────────────┬┘
     │               │               │
     │ DOI           │               │
     ▼               │               │
┌──────────────┐    │               │
│ Scout Agent  │    │               │
│  .run(doi)   │    │               │
└───────┬──────┘    │               │
        │           │               │
        │ scout_data{'title','journal'...}
        │           │               │
        ▼           ▼               │
    ┌─────────────────────┐         │
    │ Vision Agent        │         │
    │ .process()          │         │
    └──────┬──────────────┘         │
           │                        │
           │ vision_data=           │
           │  {text: ...,           │
           │   image_path: ...}     │
           │                        │
           └────────┬───────────────┘
                    │
                    │ (scout_data, vision_data)
                    ▼
            ┌─────────────────────┐
            │ Judge Agent         │
            │ .adjudicate()       │
            └──────┬──────────────┘
                   │
                   │ 数据库操作
                   ▼
        ┌────────────────────────┐
        │ SQLite Database        │
        │  - Faculty             │
        │  - Papers              │
        │  - PaperAuthor         │
        │  (+ 匹配记录)          │
        └────────────────────────┘
```

### 关键数据模式

#### Scout Agent 输出格式

```json
{
    "doi": "10.1038/s41586-020-2649-2",
    "title": "Array programming with NumPy",
    "journal": "Nature",
    "publish_date": "2020",
    "url": "https://doi.org/...",
    "status": "metadata_ready"
}
```

#### Vision Agent 输出格式

```json
{
    "text": "[MOCK OCR DATA] Authors detected in image. Z.P. Liu*, L. Duan#.",
    "image_path": "data/visual_slices/10.1038_s41586-020-2649-2.png"
}
```

#### Judge Agent 数据库写入

```
Faculty表: id=1, employee_id="E001", name_zh="刘泽萍", name_en_list=["Zeping Liu", "Z.P. Liu"], ...
Paper表:   doi="10.1038/...", title="Array...", journal="Nature", status="COMPLETED", ...
PaperAuthor表:
    - rank=1, raw_name="Z.P. Liu", matched_faculty_id=1, 
      is_corresponding=True, is_co_first=False
    - rank=2, raw_name="L. Duan", matched_faculty_id=2,
      is_corresponding=False, is_co_first=True
```

---

## 实现约束清单

### ✅ 已实现的核心功能（勿重复实现）

#### Backend基础设施
- [x] **config.py**: 全局配置、路径管理、HTTP头设置
- [x] **database/connection.py**: SQLite引擎、会话工厂、初始化逻辑
- [x] **database/models.py**: 三表结构（Faculty、Paper、PaperAuthor）、ORM关系定义
- [x] **backend/orchestrator.py**: Scout→Vision→Judge三阶段编排、异常处理

#### Scout Agent
- [x] **scout_agent.py**: Crossref API元数据获取、错误处理

#### Vision Agent
- [x] **vision_agent.py**: Playwright浏览器自动化、截图、Mock VLM

#### Judge Agent
- [x] **judge_agent.py**: 身份匹配、数据库CRUD、事务管理、标记检测（*、#）

#### 工具库
- [x] **pdf_loader.py**: 文件下载、缓存管理、幂等性保证
- [x] **excel_parser.py**: Excel解析、名字转换（pypinyin集成）

#### 前端
- [x] **pages/2_Smart_Extraction.py**: Streamlit UI、文件上传、结果展示
- [x] **frontend/components.py**: 基础UI组件（pdf_preview、labeled_progress）

---

### 📋 命名规范（必须遵守）

#### 文件名
```
snake_case.py  (e.g., scout_agent.py, pdf_loader.py)
```

#### 类名
```
PascalCase     (e.g., ScoutAgent, VisionAgent, JudgeAgent, Orchestrator)
```

#### 函数名 / 方法名
```
snake_case     (e.g., process_dois(), generate_name_variants(), fetch_metadata())
```

#### 常数名
```
UPPER_SNAKE_CASE  (e.g., PDF_CACHE_DIR, BASE_DIR, HEADERS)
```

#### 数据库列名
```
snake_case     (e.g., employee_id, name_zh, is_corresponding)
```

#### 数据库状态值
```
UPPER_WITH_UNDERSCORE  (e.g., "PENDING", "PROCESSING", "COMPLETED", "ERROR")
```

---

### 🔗 函数签名约定

#### Agent 类标准方法

```python
# Scout Agent
def run(self, doi: str) -> Dict:
    """处理单个DOI，返回元数据字典"""
    
def fetch_metadata(self, doi: str) -> Dict | None:
    """获取元数据或返回None"""

# Vision Agent
def process(self, file_path: str) -> Dict:
    """处理文件（当前忽视路径，通过内部逻辑获取DOI），返回{text, image_path}"""
    
def _capture_webpage(self, doi: str) -> str | None:
    """私有方法，返回截图路径或None"""
    
def _mock_vlm_analysis(self, image_path: str, doi: str) -> Dict:
    """私有方法，模拟VLM"""

# Judge Agent
def adjudicate(self, scout_data: Dict, vision_data: Dict) -> bool:
    """处理身份匹配，返回True/False"""

# Orchestrator
def process_dois(self, dois: List[str]) -> List[Dict]:
    """处理DOI列表，返回结果列表"""
    
def process_excel(self, excel_file) -> List[Dict]:
    """处理Excel文件，自动提取DOI"""
```

#### 工具函数标准签名

```python
# pdf_loader
def ensure_cache_dir() -> None
def download_file(url: str, save_path: str) -> str | None
def fetch_pdf_by_doi(doi: str, pdf_url: str) -> str | None

# excel_parser
def parse_faculty_list(uploaded_file) -> Tuple[List[Dict], str | None]
def generate_name_variants(name_str: str) -> List[str]
```

---

### 📊 数据流向规范

#### 阶段1: Scout → Vision
- **输入**: scout_data (Dict with keys: doi, title, journal, ...)
- **使用**: `file_path = scout_data.get("pdf_path") or scout_data.get("html_path")`
- **输出**: vision_data (Dict with keys: text, image_path)

#### 阶段2: Vision → Judge
- **输入**: scout_data + vision_data
- **关键字段**: 
  - `vision_data["text"]`: 包含作者信息，Judge从中提取名字
  - `scout_data["doi"]`: 用于创建Paper记录

#### 阶段3: Judge → Database
- **检查重复**: 
  ```python
  existing_paper = db.query(Paper).filter(Paper.doi == doi).first()
  ```
- **创建/更新**:
  ```python
  if existing_paper:
      paper = existing_paper
  else:
      paper = Paper(doi=doi, title=title, ...)
      db.add(paper)
      db.flush()  # 获取ID
  ```
- **匹配逻辑**:
  ```python
  for faculty in all_faculty:
      for name in [faculty.name_zh] + json.loads(faculty.name_en_list):
          if name.lower() in full_text.lower():
              # 创建PaperAuthor记录
  ```

---

### 🗄️ 数据库操作标准用法

#### 会话管理

```python
# ✅ 正确：使用get_db()生成器
from database.connection import get_db
db: Session = next(get_db())
try:
    # ... 操作
    db.commit()
except Exception:
    db.rollback()
finally:
    db.close()

# ❌ 错误：直接使用SessionLocal
from database.connection import SessionLocal
db = SessionLocal()  # 没有finally关闭风险
```

#### 创建记录

```python
# 新建对象
paper = Paper(
    doi="10.1038/...",
    title="...",
    journal="...",
    status="COMPLETED"
)
db.add(paper)
db.flush()  # 立即获取ID或外键关系

# 创建关联
author = PaperAuthor(
    paper_doi=paper.doi,  # 外键
    rank=1,
    raw_name="...",
    matched_faculty_id=faculty.id
)
db.add(author)
db.commit()
```

#### 查询&检查重复

```python
# 检查是否存在
existing = db.query(Paper).filter(Paper.doi == doi).first()
if existing:
    # 更新状态
    existing.status = "PROCESSING"
    db.commit()
else:
    # 创建新记录
    paper = Paper(...)
    db.add(paper)
    db.commit()

# 查询所有（迭代）
all_faculty = db.query(Faculty).all()
for faculty in all_faculty:
    # process
```

#### 关系操作

```python
# 访问正向关系
paper = db.query(Paper).filter(Paper.doi == "...").first()
for author in paper.authors:  # PaperAuthor对象列表
    print(author.raw_name)

# 访问反向关系
faculty = db.query(Faculty).filter(Faculty.id == 1).first()
for match in faculty.matched_records:  # PaperAuthor对象列表
    print(match.paper.title)
```

---

### ⚙️ 配置管理清单

#### 路径变量（config.py）

| 常数 | 值 | 说明 |
|------|-----|------|
| BASE_DIR | os.path.dirname(...) | 项目根目录 |
| DATA_DIR | BASE_DIR/data | 数据文件夹 |
| PDF_CACHE_DIR | DATA_DIR/pdf_cache | PDF缓存 |
| HTML_CACHE_DIR | DATA_DIR/html_cache | HTML缓存 |
| VISUAL_SLICE_DIR | DATA_DIR/visual_slices | 截图文件夹 |
| EXPORT_DIR | DATA_DIR/exports | 导出文件夹 |
| DB_PATH | DATA_DIR/mac_adg.db | 数据库文件 |

#### HTTP头（config.py）

- 必须设置 `"User-Agent"` 为真实Chrome浏览器UA
- 必须设置 `"Accept"`, `"Accept-Encoding"` 等标准headers
- 用于规避 403 Forbidden 错误

#### 状态值约定（database/models.py）

| 字段 | 可能值 | 说明 |
|------|-------|------|
| Paper.status | "PENDING" | 初始化 |
| | "PROCESSING" | 处理中 |
| | "COMPLETED" | 完成 |
| | "ERROR" | 错误 |

#### API端点（scout_agent.py）

- Crossref API: `https://api.crossref.org/works/{doi}`
- DOI解析: `https://doi.org/{doi}` (Vision Agent使用)

---

### 🚨 常见错误防范

#### 错误1: 重复实现流程逻辑
```python
# ❌ 错误：Streamlit页面中直接写Scout→Vision→Judge
for doi in dois:
    scout = ScoutAgent().run(doi)
    vision = VisionAgent().process(...)
    judge = JudgeAgent().adjudicate(...)

# ✅ 正确：使用Orchestrator
from backend.orchestrator import Orchestrator
orch = Orchestrator()
results = orch.process_dois(dois)
```

#### 错误2: 忘记关闭数据库会话
```python
# ❌ 错误
db = get_db()
paper = db.query(Paper).first()
# 没有close()

# ✅ 正确
db = next(get_db())
try:
    paper = db.query(Paper).first()
finally:
    db.close()
```

#### 错误3: 不检查重复记录
```python
# ❌ 错误
author = PaperAuthor(...)
db.add(author)
db.commit()  # 可能重复

# ✅ 正确
existing = db.query(PaperAuthor).filter(
    PaperAuthor.paper_doi == doi,
    PaperAuthor.matched_faculty_id == fac_id
).first()
if not existing:
    db.add(author)
    db.commit()
```

#### 错误4: 在循环中重复初始化Agent
```python
# ❌ 错误：初始化开销大（尤其是Vision Agent的浏览器）
for doi in dois:
    orchestrator = Orchestrator()  # 每次初始化Scout/Vision/Judge
    results = orchestrator.process_dois([doi])

# ✅ 正确：单次初始化
orchestrator = Orchestrator()
results = orchestrator.process_dois(dois)
```

#### 错误5: 未设置正确的User-Agent
```python
# ❌ 错误
requests.get(url)  # 默认User-Agent会导致403

# ✅ 正确
from config import HEADERS
requests.get(url, headers=HEADERS)
```

---

### 📦 依赖严格清单

#### 核心依赖（必须）
```
streamlit          # 前端框架
sqlalchemy         # ORM
pandas             # 数据处理
openpyxl           # Excel读取
requests           # HTTP请求
```

#### 可选但推荐
```
playwright         # 浏览器自动化 (Vision Agent)
playwright-stealth # 反爬虫规避
pymupdf            # PDF解析（未来用）
pypinyin           # 中文→拼音转换（excel_parser用）
```

#### 未来集成
```
deepseek-api       # DeepSeek-VL LLM
```

---

### 🔄 版本控制&迭代约定

#### 当前版本: 1.0
- Scout Agent: v1.0 (Crossref API)
- Vision Agent: v1.0 (Playwright截图 + Mock VLM)
- Judge Agent: v1.0 (字符串匹配 + 标记检测)
- Database: v1.0 (三表结构)

#### 已知缺陷需在后续版本处理

1. **Vision Agent - VLM集成** (v1.1)
   - 当前: Mock返回
   - 需要: 接入DeepSeek-VL API或其他视觉模型
   - 时间线: TBD

2. **Judge Agent - 匹配算法改进** (v1.1)
   - 当前: 简单字符串匹配
   - 建议: 
     - 模糊匹配 (Levenshtein距离)
     - 拼音缩写识别
     - 机构名规范化
   - 优先级: 中

3. **性能优化** (v2.0)
   - Vision Agent: 支持并发浏览器 (当前串行)
   - Judge Agent: 批量数据库操作优化
   - 优先级: 低

4. **功能扩展** (v2.0+)
   - 支持PDF文本提取 (PyMuPDF/pdfplumber)
   - 支持HTML页面抓取和解析
   - 导出管理和报告生成
   - 优先级: 低

---

### 🎯 快速检查清单（代码审查用）

新增功能前，确保满足：

- [ ] **命名**: 遵循snake_case/PascalCase/UPPER_SNAKE_CASE约定
- [ ] **导入**: 使用正确的模块路径 (`from backend.agents import ...`)
- [ ] **会话**: 数据库操作包含try-finally-close
- [ ] **重复检查**: 数据库操作前检查存在性
- [ ] **状态值**: 使用定义的常数值（如"COMPLETED"而非"complete"）
- [ ] **异常处理**: 不让异常从Agent冒出，改为返回error字段
- [ ] **Agent初始化**: Orchestrator中单次初始化，不在循环中重复
- [ ] **依赖声明**: 新增第三方包需更新requirements.txt
- [ ] **测试**: 新增功能需有对应的测试脚本
- [ ] **文档**: 添加函数docstring和关键逻辑注释

---

## 附录：相关文件速查

| 文件 | 行数 | 说明 |
|------|-----|------|
| [config.py](config.py) | ~25 | 全局配置 |
| [database/models.py](database/models.py) | ~120 | 数据模型 |
| [database/connection.py](database/connection.py) | ~30 | DB连接 |
| [backend/orchestrator.py](backend/orchestrator.py) | ~60 | 编排器 |
| [backend/agents/scout_agent.py](backend/agents/scout_agent.py) | ~50 | Scout代理 |
| [backend/agents/vision_agent.py](backend/agents/vision_agent.py) | ~100 | Vision代理 |
| [backend/agents/judge_agent.py](backend/agents/judge_agent.py) | ~120 | Judge代理 |
| [backend/utils/pdf_loader.py](backend/utils/pdf_loader.py) | ~50 | PDF工具 |
| [backend/utils/excel_parser.py](backend/utils/excel_parser.py) | ~80 | Excel工具 |
| [pages/2_Smart_Extraction.py](pages/2_Smart_Extraction.py) | ~80 | 主UI页面 |
| [frontend/components.py](frontend/components.py) | ~20 | UI组件库 |

---

## 总结

本架构文档提供了MAC-ADG系统的**完整代码地图**和**实现约束清单**，涵盖：

✅ **7个信息层**: 配置→数据库→代理→编排→工具→前端  
✅ **3个端到端flow**: Scout→Vision→Judge  
✅ **详细的命名、签名、状态约定**  
✅ **已实现功能列表**（勿重复）  
✅ **常见错误防范**  

使用本文档作为**新功能开发**、**代码审查**、**问题排查**的参考标准。

---

*文档生成时间: 2026年3月10日*  
*维护者: MAC-ADG 技术团队*
