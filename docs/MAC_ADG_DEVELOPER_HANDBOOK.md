# 📘 MAC-ADG 系统开发白皮书（Developer Handbook / Single Source of Truth）

**项目全称**：科技文献关键信息智能识别与提取 Agent 开发（MAC-ADG）  
**架构模式**：感知（Perception）- 决策（Decision）- 执行（Execution）的多智能体协同  
**本文定位**：本仓库的**唯一权威版**开发手册；当其他文档或注释与本文冲突时，以本文为准。

---

## 0. 读者与使用边界

- **目标读者**：需要二次开发/接入新数据源/修复抓取与匹配问题的开发者。
- **系统目标**：面向高校科研管理的智能治理系统，核心产出是可审核、可追溯的《科研成果统计报表》数据底座。
- **合规边界**：
  - 对 Web 访问的 403/风控拦截：本系统不提供“绕过/破解”方案；只能通过**合法合规**方式（例如：改用公开 API、使用授权网络出口、人工交互/白名单申请）提高成功率。

---

## 1. 项目愿景与核心业务（Project Scope）

### 1.1 系统定位

MAC-ADG 不是单纯的文献抓取工具，而是一个面向高校科研管理的智能治理系统：
- **解决 OCR 的结构性缺陷**：复杂版面（通讯作者角标、脚注邮箱、共同一作说明）无法可靠用纯 OCR 规则提取。
- **解决 API 的滞后与缺失**：Crossref 等元数据经常缺单位/缺权益标记/字段不一致，需要视觉与推理融合。

### 1.2 核心场景：批量科研绩效统计

- **输入**：
  1) 待查清单：包含 500+ DOI 的 Excel
  2) 基准名单：本校教师花名册（姓名、工号、学院/单位）

- **核心挑战**：
  - 多源异构：Crossref（API）与网页/首屏视觉信息的冲突与缺失
  - 模糊匹配：缩写、变体、拼写差异（例：Z.P. Liu vs 刘泽萍）
  - 权益认定：通讯作者、共同一作、署名单位

- **输出**：
  - 可写入数据库的结构化记录（Paper / PaperAuthor / Faculty 关联）
  - 可进一步导出为学院要求的统计报表（本仓库当前以数据库为主输出）

---

## 2. 系统技术架构（System Architecture）

### 2.1 P-D-E 三段式分工

- **Perception（感知）**：
  - `ScoutAgent`：从公开 API 拉取元数据与作者（Crossref；必要时 OpenAlex 补全）
  - `WebDriverAdapter`：页面导航与截图（Playwright）
  - `VisionAgent`：对截图做 OCR + 结构化解析（DeepSeek OCR + 文本模型解析）

- **Decision（决策）**：
  - `JudgeAgent`：身份匹配、冲突消解、权益融合与置信度评估；只把“与本校相关”的内容落库

- **Execution（执行）**：
  - `Orchestrator`：任务编排、异常隔离、状态机推进、写库

### 2.2 当前主流水线（与代码一致）

> **当前实现以 `Orchestrator.process_dois()` 为准**（见 `backend/orchestrator.py`）。

1) Scout：`ScoutAgent().run(doi)` → `title/journal/publish_date/authors/landing_page_url`
2) WebDriver：`WebDriverAdapter().get_webpage_screenshot(doi, landing_page_url=...)` → `data/visual_slices/<doi>.png` 或 `None`
3) Vision：`VisionAgent().analyze_screenshot(image_path)` → `{"text":..., "image_path":..., "authors": [...]}`
4) Judge：`JudgeAgent().adjudicate(scout_data, vision_data)` → 写入 `Paper` 与 `PaperAuthor`

---

## 3. 仓库目录结构规范（Repository Layout）

> 下面是**当前仓库真实结构**的规范化解释（不是理想化结构图）。

```
MAC_ADG_System/
├── .env                          # 可选：环境变量（密钥、Playwright参数），建议不入库
├── config.py                     # 全局配置（路径、HTTP headers、DeepSeek配置等）
├── requirements.txt              # Python 依赖
├── run_orchestrator.py           # ✅ Orchestrator-only 入口（推荐批处理/命令行运行）
├── main.py                       # Streamlit UI 入口（若使用 UI）
│
├── backend/
│   ├── orchestrator.py            # 指挥官：流水线编排、状态推进、异常隔离
│   ├── agents/
│   │   ├── scout_agent.py         # 侦察兵：Crossref + OpenAlex 元数据与作者
│   │   ├── vision_agent.py        # 视觉眼：OCR + LLM 解析（也保留 process(doi) 能力）
│   │   └── judge_agent.py         # 仲裁官：匹配/融合/写库
│   └── utils/
│       ├── excel_parser.py        # Excel 解析（教师名单、DOI 清单）
│       ├── pdf_loader.py          # 本地文件缓存工具（历史遗留/可扩展）
│       └── webdriver.py           # ✅ Playwright 截图工具（反爬参数、阻断页诊断）
│
├── database/
│   ├── connection.py              # DB Session 工厂、初始化
│   └── models.py                  # ORM：Faculty / Paper / PaperAuthor
│
├── data/
│   ├── mac_adg.db                 # SQLite 数据库
│   ├── visual_slices/             # 网页截图与阻断页截图（*_blocked.png）
│   ├── pdf_cache/                 # 预留/历史
│   └── html_cache/                # 预留/历史
│
├── docs/                          # ✅ 文档统一放在此目录
└── tests/                         # 测试脚本（以当前保留版本为准）
```

**关于你原文档中提到但当前仓库不存在的模块**：
- `backend/utils/image_processor.py`：当前未独立成模块（如果后续要做“自适应切片/去噪锐化”，建议再拆出来）。

---

## 4. 核心数据库设计（Database Schema）

> 数据库模型以 `database/models.py` 为准，这里给出“业务视角”解释。

### 4.1 Faculty（基准名单表）

用途：Judge 做身份核验的“标准答案”。
- `employee_id`（唯一）：工号
- `name_zh`：中文名
- `name_en_list`（JSON）：英文名变体列表
- `department`：主单位
- `departments`（JSON）：多个单位（可选）

### 4.2 Paper（文献主表）

用途：存储元数据与处理状态。
- `doi`（PK）
- `title` / `journal` / `publish_date`
- `pdf_path`：历史字段（当前截图流不强依赖该字段）
- `status`：
  - `PENDING`：未处理
  - `PROCESSING`：处理中
  - `COMPLETED`：完成
  - `SKIPPED`：被 Judge 判定与本校无关（例如：无学校相关单位）
  - `ERROR`：处理失败

### 4.3 PaperAuthor（作者权益表）

用途：记录作者排序、单位、权益标记与匹配结果。
- `paper_doi`（FK）
- `rank`：作者顺序
- `raw_name`
- `raw_affiliation` / `raw_affiliations`
- `is_corresponding` / `is_co_first`
- `matched_faculty_id`
- `confidence_score`：0-100
- `matched_level` / `match_signals`：调试/解释用

---

## 5. 智能体功能技术规范（Agent Specifications）

### 5.1 🕵️ ScoutAgent（极致轻量化元数据/路由器）

**职责**：只做元数据与路由，不做网页截图、不做 OCR。

- 数据源：
  - 首选 Crossref：`https://api.crossref.org/works/{doi}`
  - 兜底 OpenAlex：用于补全作者单位与落地页（当 Crossref 缺失/Unknown）

- 输出字段（核心）：
  - `doi/title/journal/publish_date/url/authors/landing_page_url`

### 5.2 🌐 WebDriverAdapter（执行层工具：截图获取）

**职责**：负责“像人一样打开网页并截图”。

- 输入：`doi` +（可选）`landing_page_url`
- 输出：截图路径或 `None`
- 关键特性（与代码一致）：
  - 支持 `PLAYWRIGHT_CHANNEL=chrome` 使用系统 Chrome
  - 支持代理：`PLAYWRIGHT_PROXY/USERNAME/PASSWORD`
  - 支持 headful 调试：`PLAYWRIGHT_HEADLESS=0`
  - 被拦截时保存 `*_blocked.png` 便于判断是 403 还是逻辑问题

### 5.3 👁️ VisionAgent（核心：OCR + 结构化解析）

**职责**：把截图变成结构化作者数据。

- 主入口（编排器使用）：`analyze_screenshot(image_path)`
- 兼容入口：`process(doi)`（Vision 自己也能执行截图+解析，但编排器默认使用 WebDriverAdapter 先截图）

- 输出结构（标准）：
```json
{
  "text": "...OCR text...",
  "image_path": "data/visual_slices/<doi>.png",
  "authors": [
    {
      "name": "Zeping Liu",
      "affiliation": "Sichuan University...",
      "position": 1,
      "is_corresponding": true,
      "is_co_first": false
    }
  ]
}
```

### 5.4 ⚖️ JudgeAgent（身份匹配 + 冲突消解 + 落库）

**职责**：解决“信谁”和“是不是同一个人”。

- 决策要点（与当前实现一致）：
  1) 先用 Crossref 作者单位做“是否与本校相关”的快速筛选
  2) 若无学校相关单位 → `status=skipped`（不浪费后续资源）
  3) 若有相关单位 → 融合 Vision 的权益标记（*/#）
  4) 对合并后的作者逐个匹配 Faculty，并写入 PaperAuthor

---

## 6. Orchestrator 状态机与错误隔离

### 6.1 处理状态（Paper.status 与结果 record.status）

- `PROCESSING`：进入完整流程时设置（防并发重复）
- `COMPLETED`：Judge 成功落库
- `SKIPPED`：Judge 判定与本校无关/无作者数据
- `ERROR`：任意阶段异常（单 DOI 失败不影响其他 DOI）

### 6.2 截图失败的可诊断输出

当 WebDriver 无法截图时：
- 结果中会出现：
  - `screenshot_status = BLOCKED_OR_FAILED`
  - 可能有 `data/visual_slices/<doi>_blocked.png`

这用于区分：
- 代码逻辑错误 vs 站点风控/403/需要交互验证

---

## 7. 403/反爬与可行的工程策略（不提供绕过）

现实情况：doi.org 与出版社站点可能返回 403/风控页，这通常是**IP 信誉、频率、自动化特征**导致。

推荐策略（合规）：
- **优先走公开 API**：Crossref/OpenAlex 能拿到作者与部分单位时，可在截图失败时继续完成“与本校相关”的匹配（但权益标记可能缺失）。
- **换合法网络出口**：使用单位出口、允许的代理或白名单 IP（通过 `PLAYWRIGHT_PROXY` 配置）。
- **人工 headful 模式辅助**：`PLAYWRIGHT_HEADLESS=0`，用于处理一次性的人机验证/Cookie 同意等。
- **降级策略**：截图失败时允许系统产出 `SKIPPED/NEEDS_REVIEW`（由业务决定是否引入 NEEDS_REVIEW 状态）。

---

## 8. 运行方式（推荐 Orchestrator-only）

### 8.1 命令行批处理（推荐）

- 单 DOI：
```bash
python run_orchestrator.py --doi 10.1038/s41586-020-2649-2
```

- 多 DOI（重复参数）：
```bash
python run_orchestrator.py --doi 10.1038/s41586-020-2649-2 --doi 10.1161/CIRCULATIONAHA.119.045033
```

### 8.2 Playwright 运行参数（环境变量）

- 使用系统 Chrome：
```bash
set PLAYWRIGHT_CHANNEL=chrome
```

- 开启 headful：
```bash
set PLAYWRIGHT_HEADLESS=0
```

- 代理：
```bash
set PLAYWRIGHT_PROXY=http://host:port
set PLAYWRIGHT_PROXY_USERNAME=xxx
set PLAYWRIGHT_PROXY_PASSWORD=yyy
```

---

## 9. 开发实施路线图（与现状对齐版）

> 你的原路线图是正确的，但本仓库当前已经演进为“截图+OCR”主路线；下面是按当前代码现实修订后的版本。

- Phase 1：基础设施 ✅
  - 数据库模型与初始化 ✅（`database/models.py`, `database/connection.py`）
  - Excel 解析 ✅（`backend/utils/excel_parser.py`）

- Phase 2：核心智能体 ✅/⏳
  - Scout：Crossref + OpenAlex 补全 ✅（不再负责 PDF 下载）
  - Vision：截图 OCR + LLM 解析 ✅（DeepSeek 依赖需配置）
  - Judge：身份匹配与落库 ✅（快速筛选 + 融合权益标记；后续可继续增强）

- Phase 3：业务流程串联 ✅
  - Orchestrator：批量循环、异常隔离、去重 ✅

- Phase 4：UI 与交付（可选）
  - Streamlit 页面存在，但如果你的目标是“只跑 orchestrator”，可不投入 UI 改造。

---

## 10. 贡献与扩展点

- 新数据源（替代/补充 Crossref）：在 `ScoutAgent` 内新增 fetch/enrich 函数，输出字段保持不变。
- 新权益提取策略（更强视觉切片）：建议新增 `backend/utils/image_processor.py`，由 Vision 调用。
- 输出报表：建议在 `data/exports/` 建立统一导出入口（当前以数据库为底座）。
