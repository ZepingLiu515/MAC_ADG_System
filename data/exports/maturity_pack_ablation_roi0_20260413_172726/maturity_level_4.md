## 成熟度 4 级：使用必要研究方法记录一批数据（运行记录证明）

### 4.1 实验对象与数据规模
- 处理样本：5 篇论文 DOI（来源：doi_table.csv）
- 教师名录库：152 名四川大学教职工（来源：staff_table.csv）
- 数据库：SQLite（D:\university\research\competition\2025_2026Doi\MAC_ADG_System\data\mac_adg.db），记录 papers / paper_authors / faculty 三张核心表

### 4.2 研究方法（系统运行与稳定性）
本项目采用多智能体协同的有限状态机（FSM）流程：Scout（API 侦察）→ Perception（网页截图 + hover/ROI + OCR）→ Judge（异构证据仲裁与身份匹配）→ Evolution（入库与终态）。

- 批处理策略：Orchestrator 在批次开始阶段对 DOI 状态进行一次性批量查询（SQL IN），避免 N 次 DB round-trip。
- 去重策略：重复 DOI 按策略（SKIP / OVERWRITE / PROMPT）决策，确保实验可重复性。
- 证据审计：截图与 sidecar（OCR/hover 文本、作者结构化输出）保留在 data/visual_slices 便于复核。

### 4.3 运行结果（真实统计）
- 运行成功率（流程成功，无 ERROR）：5 / 5（100.0%）
- 平均耗时：69.237 s/篇；P90 耗时：78.532 s/篇（run_times 统计）
- DOI 中含四川大学作者的论文数：5 / 5（比例 100.0%）
- 名单命中数（识别到教师库匹配的论文数）：5 / 5
- 识别到的四川大学作者提及次数：18（去重作者数 14）
- 共一标记出现的论文数：2；通讯作者标记出现的论文数：5

（补充）结构化作者条目产出覆盖率：100.0% (5/5)（以每篇 DOI 是否存在 paper_authors 条目统计）。

### 4.4 可核验的运行证据（建议附录）
- 逐 DOI 耗时与成功状态：run_times.csv（若使用 --run）
- 页面截图与 hover sidecar：data/visual_slices/（如 *_page_author_data.json、*_author_roi.png）

### 4.5 日志留存（控制台数字化足迹）
成熟度 4 级要求保留一次“可见的智能体流转日志”。建议在批跑时保留一段终端输出，包含类似：
- [Scout] Fetching...
- [Vision] Capturing ROI...
- [Judge] Matching...

（可选）若本次使用脚本对 50 DOI 进行了完整重跑，则在 run_times.csv 中记录每篇论文的端到端耗时，并可据此报告平均耗时与离散程度。
