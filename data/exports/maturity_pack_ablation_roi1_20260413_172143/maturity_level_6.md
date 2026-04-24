## 成熟度 6 级：软件生成图表、数据分析与讨论（讨论部分）

### 6.1 结果总览与规律发现
基于 5 篇 DOI 的运行结果，系统已能够稳定输出：论文终态（COMPLETED/NEEDS_REVIEW/SKIPPED）、作者结构化信息（单位/权益标记）、以及与四川大学教师库的身份匹配结果。

本次统计摘要（由系统自动汇总）：
- 论文终态 Top1：NEEDS_REVIEW（4 篇）
- 平均每篇论文作者数：9.6；平均匹配到教师库作者数：0.8

- 图 6-1（status_distribution.png）：论文终态分布，反映 FSM 在异构网页环境下的鲁棒性。
- 图 6-2（matched_authors_hist.png）：每篇论文匹配到教师库的作者条目数分布，用于评估学术贡献覆盖度。

![图 6-1 论文终态分布](status_distribution.png)

![图 6-2 匹配作者条目数分布](matched_authors_hist.png)

### 6.2 纵向对比：ROI 增强对微小角标识别的影响
本系统在 Perception 阶段引入作者块 ROI 截取与高 DPI 渲染，其核心目标是提升微小角标（例如 *、†、数字上标）的可见性，从而提高通讯/共一标记与单位映射的可恢复性。

- 若在同一 DOI 子集上进行 A/B（关闭 ROI vs 开启 ROI）消融实验，可将“通讯/共一标记识别率”与“作者级匹配 F1”作为主指标，统计提升幅度（%）。

建议的消融实验协议（可复现）：
- 对照组（ROI 关闭）：设置 `PLAYWRIGHT_CAPTURE_AUTHOR_ROI=0`、`VISION_FORCE_AUTHOR_ROI=0`，运行同一批 DOI 并导出证据包与 ground_truth_eval_*.csv。
- 实验组（ROI 开启）：设置 `PLAYWRIGHT_CAPTURE_AUTHOR_ROI=1`、`VISION_FORCE_AUTHOR_ROI=1`，并保持 `PLAYWRIGHT_DEVICE_SCALE_FACTOR=2`，重复运行与评测。

本证据包基线（若已生成 ground_truth_eval_summary.csv）：
- 作者级匹配：F1=36.36%（Precision=100.00% Recall=22.22%）
- 通讯作者标记：Recall=60.00%（TP=3 FN=2）
- 共一标记：Recall=0.00%（TP=0 FN=2）

### 6.3 横向对标：复杂版式下的优势
相较于传统仅依赖 PDF 文本层或单一 API 元数据的解析工具，MAC-ADG 通过网页 hover/click + OCR + 规则仲裁实现“结构化证据链”。在多栏版面、动态作者面板（如 Nature 系）等场景下，系统具备：
- 更强的证据覆盖：hover/click 可直接获取作者-单位映射；OCR 作为兜底补全。
- 更强的可解释性：sidecar 与 match_signals 使每条作者结论可追溯。
- 更可控的误报：身份确认必须满足“姓名+单位双一致”；姓名匹配但单位冲突/缺失进入 NEEDS_REVIEW，降低误判风险。

（建议在报告中附上 2-3 个代表性 DOI 的证据包截图与 author 表格片段，作为讨论部分的定性支撑。）
