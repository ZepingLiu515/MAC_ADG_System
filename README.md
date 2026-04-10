# 🎓 MAC-ADG 项目 - 最终概览

> **标题**: 科技文献关键信息智能识别与提取 Agent 开发  
> **日期**: 2026-03-10  
> **完成度**: 69% (25/36 功能) → 目标 95% (再需 3-4 小时)

---

## 🚀 快速导航

| 需求 | 文档 | 时长 |
|-----|------|------|
| 📚 文档总入口 | [docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md) | 3-5 分钟 |
| 📋 查看完整功能清单 | [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | 10 分钟 |
| 🧪 学习测试方法 | [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) | 15 分钟 |
| 🚀 快速开始验证 | [QUICKSTART.md](QUICKSTART.md) | 10 分钟 |
| 📘 最新版开发手册 | [docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md) | 20-30 分钟 |

---

## 📋 核心信息速查表

### 系统架构
```
用户界面 (Streamlit)
    ↓
Orchestrator (流程编排)
  ├→ Scout Agent (元数据 + 作者/落地页补全)
  ├→ WebDriver (网页导航 + 截图)
  ├→ Vision Agent (截图 OCR + 结构化作者解析)
    └→ Judge Agent (身份匹配 + 数据库保存)
    ↓
SQLite 数据库
```

### 已完成的模块
| 模块 | 完成度 | 关键功能 |
|-----|--------|---------|
| 🗄️ 数据库 | 100% | Faculty / Papers / PaperAuthors |
| 🕵️ Scout | 83% | Crossref API + OpenAlex 补全（作者单位/落地页） |
| 👁️ Vision | 67% | 网页截图 OCR + 作者结构化解析（依赖 DeepSeek 配置） |
| ⚖️ Judge | 57% | 字符串匹配 + 标记识别 (缺 LLM + 模糊) |
| 🔄 Orchestrator | 67% | Scout→Vision→Judge 流水线 |
| 🎨 前端 | 57% | 3 个 Streamlit 页面 (缺预览和审核) |

### 下一步优先级

**🔴 P0** (必须, 3-4 小时内完成)
- Vision Agent: DeepSeek-VL 集成
- Judge Agent: LLM 模糊匹配

**🟡 P1** (重要, 下周完成)
- 前端 PDF 预览
- 手动审核面板
- Levenshtein 模糊匹配

**🟢 P2** (优化, 可选)
- 异步处理
- 断点续传
- 性能监控

---

## ✅ 立即可做的事 (无需额外配置)

### 1️⃣ 验证环境 (5 分钟)
```bash
python quick_verify.py
```
**检查内容**: Python 版本、依赖、文件、数据库

### 2️⃣ 运行测试 (15 分钟)
```bash
python tests/test_scout.py              # Scout Agent
python tests/test_vision.py             # Vision Agent
python tests/test_orchestrator.py       # Orchestrator
python tests/test_complete_pipeline.py  # 端到端
```
**预期**: 所有测试通过，系统可正常工作

### 3️⃣ 启动 UI (2 分钟)
```bash
streamlit run main.py
```
**可以做**: 
- 上传教师名单
- 批量提取 DOI
- 查看统计报表

### 4️⃣ 阅读指南 (30 分钟)
根据需求选择：
- [QUICKSTART.md](QUICKSTART.md) - 快速上手
- [docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md) - 最新版开发手册（权威）

---

## 🎯 三个使用场景

### 场景 1: 快速演示
**目标**: 向导师展示系统可用性  
**时间**: 30 分钟

1. 运行 `quick_verify.py` (5 分钟)
2. 运行 `test_complete_pipeline.py` (10 分钟)
3. 启动 `streamlit run main.py` (2 分钟)
4. 演示 UI (10 分钟)

### 场景 2: 完成开发
**目标**: 将系统完成度从 69% 提升到 95%  
**时间**: 3-4 小时

1. 阅读 [docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md)
2. 按优先级实现 9 个功能（可与 AI 协作）
3. 运行所有测试验证（见 [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)）

### 场景 3: 日常使用
**目标**: 处理实际的 DOI 列表  
**时间**: 持续

1. 准备教师名单 Excel
2. 准备 DOI 列表
3. 在 UI 中上传并运行
4. 导出报表

---

## 📊 功能完成度详表

### Phase 1-2 (100% 完成) ✅
```
基础设施搭建 4/4
└─ 初始化项目
└─ 数据库设计
└─ PDF 加载器
└─ 工具函数库
```

### Phase 3 (69% 完成, 6/9 功能) ✅
```
核心智能体开发 (6/9)
├─ ✅ Scout Agent (5/6)
│  ├─ ✅ Crossref API
│  ├─ ✅ Unpaywall 获取
│  ├─ ✅ PDF 下载
│  ├─ ✅ HTML 备用
│  ├─ ✅ 缓存机制
│  └─ ⏳ 异常处理完善
├─ ⏳ Vision Agent (4/6)
│  ├─ ✅ PDF→图转换
│  ├─ ✅ 文本提取
│  ├─ ✅ HTML 支持
│  ├─ ✅ 图片保存
│  ├─ ⏳ 自适应切片
│  └─ ⏳ DeepSeek-VL
└─ ⏳ Judge Agent (4/7)
   ├─ ✅ 字符串匹配
   ├─ ✅ 名字变体生成
   ├─ ✅ 标记识别
   ├─ ✅ 数据库写入
   ├─ ⏳ Levenshtein
   ├─ ⏳ LLM 匹配
   └─ ⏳ 贝叶斯推理
```

### Phase 4-5 (57% 完成, 8/14 功能) ✅
```
系统集成与 UI 开发 (8/14)
├─ ✅ Orchestrator (4/6)
│  ├─ ✅ 流水线编排
│  ├─ ✅ 批量处理
│  ├─ ✅ 错误隔离
│  ├─ ✅ 进度跟踪
│  ├─ ⏳ 异步处理
│  └─ ⏳ 断点续传
└─ ✅ 前端 UI (4/7)
   ├─ ✅ 主页
   ├─ ✅ 教师名单管理
   ├─ ✅ DOI 批量提取
   ├─ ✅ 统计报表
   ├─ ⏳ PDF 预览
   ├─ ⏳ 手动审核
   └─ ⏳ 仪表板
```

---

## 💾 关键数据库设计

### Faculty (教师表)
```sql
CREATE TABLE faculty (
    id INTEGER PRIMARY KEY,
    employee_id STRING UNIQUE,       -- 工号
    name_zh STRING,                  -- 中文名
    name_en_list JSON,              -- 英文名变体
    department STRING               -- 学院
);
```

### Papers (论文表)
```sql
CREATE TABLE papers (
    doi STRING PRIMARY KEY,          -- DOI
    title TEXT,                      -- 论文标题
    journal STRING,                  -- 期刊名
    publish_date STRING,             -- 发表日期
    pdf_path STRING,                 -- PDF 本地路径
    html_path STRING,                -- HTML 本地路径
    status STRING,                   -- 处理状态
    created_at DATETIME              -- 创建时间
);
```

### PaperAuthors (作者权益表)
```sql
CREATE TABLE paper_authors (
    id INTEGER PRIMARY KEY,
    paper_doi STRING FK,             -- 关联论文
    rank INTEGER,                    -- 作者排位
    raw_name STRING,                 -- 原始署名
    raw_affiliation TEXT,            -- 原始单位
    is_corresponding BOOLEAN,        -- 通讯作者 (*)
    is_co_first BOOLEAN,             -- 共同一作 (#)
    matched_faculty_id INTEGER FK,   -- 匹配的教师 ID
    confidence FLOAT,                -- 匹配置信度
    is_reviewed BOOLEAN              -- 是否已审核
);
```

---

## 🔧 关键代码位置

| 功能 | 文件 | 主要函数 |
|-----|------|---------|
| 元数据获取 | `backend/agents/scout_agent.py` | `run()`, `fetch_metadata()` |
| PDF 处理 | `backend/agents/vision_agent.py` | `process()`, `_process_pdf()` |
| 身份匹配 | `backend/agents/judge_agent.py` | `adjudicate()` |
| 流程编排 | `backend/orchestrator.py` | `process_dois()` |
| 前端 - 主页 | `pages/1_Data_Management.py` | - |
| 前端 - 提取 | `pages/2_Smart_Extraction.py` | - |
| 前端 - 报表 | `pages/3_Analytics_Reports.py` | - |

---

## 🔑 关键函数签名

```python
# Scout Agent
scout.run(doi: str) -> Dict  # 返回 metadata + pdf_path

# Vision Agent
vision.process(file_path: str) -> Dict  # 返回 text + image_path

# Judge Agent
judge.adjudicate(scout_data: Dict, vision_data: Dict) -> bool

# Orchestrator
orchestrator.process_dois(dois: List[str]) -> List[Dict]
orchestrator.process_excel(file) -> List[Dict]

# Streamlit 页面
streamlit_run_main.py  # 启动主应用
```

---

## 📈 性能指标

### 当前性能
- ✅ 相应时间: ~5-10 秒/DOI (串行)
- ✅ 成功率: ~95% (成功获取元数据)
- ✅ 匹配准确度: ~70% (简单字符串匹配)
- ✅ 数据库性能: 支持 500+ 论文

### 目标性能 (完成后)
- 🎯 相应时间: ~3-5 秒/DOI (优化后)
- 🎯 成功率: ~98% (改进异常处理)
- 🎯 匹配准确度: ~90%+ (LLM 集成)
- 🎯 并发处理: 支持异步 20+ 并发

---

## 🚨 已知限制

| 限制 | 影响 | 解决方案 |
|-----|------|---------|
| 无 DeepSeek-VL | 无法识别图片中的作者 | 集成 Vision API |
| 无 LLM 匹配 | 模糊名字无法匹配 | 集成 Judge LLM |
| 串行处理 | 500+ DOI 需要 50+ 秒 | 实现异步处理 |
| 无中断恢复 | 中途出错要重新开始 | 实现断点续传 |
| 无手动审核 | 错误无法修正 | 添加审核面板 |

---

## 📞 技术支持快速指南

### 问题: "代码报错"
1. 查看 [TROUBLESHOOTING.md](#) (若有)
2. 运行 `python quick_verify.py` 诊断
3. 查看错误堆栈，搜索文件名

### 问题: "测试失败"
1. 清除缓存（PowerShell）: `Remove-Item -Recurse -Force data\pdf_cache\* , data\visual_slices\* -ErrorAction SilentlyContinue`
2. 重新初始化: `python force_init_db.py`
3. 重新运行测试

### 问题: "不知道如何继续"
1. 阅读 [docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md)
2. 按手册里的“扩展点/状态机/运行参数”推进

### 问题: "想要快速演示"
```bash
python quick_verify.py      # 验证环境 (5 分钟)
python tests/test_complete_pipeline.py  # 运行完整流程 (10 分钟)
streamlit run main.py       # 启动 UI (立即启动)
```

---

## 📚 推荐阅读（以最新版为准）

- 权威手册（首选）：[docs/MAC_ADG_DEVELOPER_HANDBOOK.md](docs/MAC_ADG_DEVELOPER_HANDBOOK.md)
- 文档导航入口：[docs/DOCUMENTATION_INDEX.md](docs/DOCUMENTATION_INDEX.md)
- 快速开始：[QUICKSTART.md](QUICKSTART.md)
- 测试指南：[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)
