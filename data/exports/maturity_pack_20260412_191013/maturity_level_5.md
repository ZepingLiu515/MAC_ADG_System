## 成熟度 5 级：规范实验与 SI 证明（至少 3 组数据/表格 + 采集说明）

本阶段强调实验的可复现性与可审计性。我们将证据分为三组数据包（每组均可导出 CSV，并由系统生成图表/截图 sidecar 作为审计材料）。

### 5.1 数据组 A：样本与元数据一致性（doi_table + DB）
- 表 A1（status_summary.csv）：论文终态分布（COMPLETED / NEEDS_REVIEW / SKIPPED / ERROR）。
- 表 A2（per_paper_summary.csv）：每篇论文的作者条目数、匹配到教师库的条目数、待复核条目数等。

### 5.2 数据组 B：能力增量验证（Scout vs Vision/hover 增强）
- 表 B1（capability_increment.csv）：对比 Scout 仅 API 元数据与 Vision/hover 增强后的结构化作者信息，量化以下指标的增量：
  - 单位完整率（non-Unknown affiliation ratio）
  - 通讯作者/共一标记可用性
  - 作者-单位映射的可解释证据（sidecar 与 match_signals）

### 5.3 数据组 C：身份审计与排除流程（staff_table + Judge 仲裁信号）
- 表 C1（identity_audit.csv）：展示疑似“挂名单位/同名异校”的作者条目，系统如何通过“姓名+单位双阈值一致”确认，或将“姓名像但单位 Unknown/不一致”的情况进入 NEEDS_REVIEW。

### 5.4 数据采集说明（SI：参数、ROI 锚定与坐标映射）
本系统的数据采集采用“网页证据优先、OCR 兜底”的策略，并引入 ROI 动态锚定以提高角标/小字号信息的可见性。

- DPI/缩放：Playwright 端采用 deviceScaleFactor=2（可通过环境变量 PLAYWRIGHT_DEVICE_SCALE_FACTOR 配置），以提升微小角标与上标符号的渲染清晰度。
- ROI 动态锚定：在网页截图基础上额外截取作者块 ROI（PLAYWRIGHT_CAPTURE_AUTHOR_ROI=1 时启用），将“作者行/角标区域”作为高分辨率补充证据。
- 坐标仿射映射：ROI 截取与全图共享同一页面坐标系，ROI→全图通过（x,y,w,h）偏移完成映射，保证 OCR token 可回溯到原始截图位置，实现 sidecar 可审计。
- 异构证据仲裁：Judge 以 Crossref/hover/Vision 三类证据对作者权益（通讯/共一）与单位信息进行融合，并将 match_signals 写入数据库，便于抽样复核。
