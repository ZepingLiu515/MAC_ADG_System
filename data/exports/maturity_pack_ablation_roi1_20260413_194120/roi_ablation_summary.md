# ROI 消融（A/B）对比结论（tag: 20260413_194120）

对比对象（同一 5 DOI 子集 `data/doi_table_ablation_5.csv`）：
- ROI 关闭（对照组）：`data/exports/maturity_pack_ablation_roi0_20260413_194120/`
- ROI 开启（实验组）：`data/exports/maturity_pack_ablation_roi1_20260413_194120/`

## A/B 关键差异（Ground Truth 一致性评测 + 运行效率）

| 指标 | ROI关闭 | ROI开启 | Δ |
|---|---:|---:|---:|
| 论文级命中 Accuracy | 100.00% (5/5) | 80.00% (4/5) | -20.00pp |
| 作者级名单匹配 F1 | 97.30% | 84.85% | -12.45pp |
| 通讯作者标记 Recall | 80.00% (4/5) | 60.00% (3/5) | -20.00pp |
| 共一标记 Recall | 50.00% (1/2) | 100.00% (2/2) | +50.00pp |
| 平均耗时 | 22.32s/篇 | 40.99s/篇 | +18.67s (+83.7%) |

> 更详细的数值与差异表见：`roi_ablation_delta.csv`

## 代表性 error case（用于讨论与后续迭代）

- ROI开启导致论文级 FN：`10.1038/s41467-023-42720-6`（pred_has_scu=N），漏识别：Cheng Gu; Shengdong Wang
- ROI开启作者漏识别：`10.1038/s41392-022-01130-8` 漏识别：Jun Shao; Weimin Li
- 两组均漏通讯：`10.1038/s41467-024-47121-x`（gt_corresponding=Y，pred_corresponding=N）

## 结论（可直接写入成熟度6/中期报告）

- ROI 强制开启在该子集上带来“共一标记召回率”提升，但同时引入了作者漏识别与论文级漏报，并显著增加耗时。
- 更稳健的策略是“自适应 ROI”：仅在全页证据不足（base authors 弱/hover 不完整）时启用 ROI，并在 ROI 结果导致匹配下降时回退到全页结果。
