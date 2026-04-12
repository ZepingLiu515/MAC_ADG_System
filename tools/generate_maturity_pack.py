"""Generate evidence pack for midterm report maturity levels (4/5/6).

This script is designed for the MAC-ADG project.
It can:
- Read existing assets: doi_table.csv, staff_table.csv, SQLite DB (data/mac_adg.db)
- Optionally run the Orchestrator on a DOI list and record per-DOI runtime
- Export 3 groups of tables (CSV) + optional charts (PNG) + 3 markdown sections

Why this file:
- Maturity 4: "system runs through" evidence (run logs + stability summary)
- Maturity 5: at least 3 groups of data/tables + SI-style data acquisition description
- Maturity 6: software-generated charts + analysis/discussion derived from real data

Windows / PowerShell friendly.
Python 3.8+ compatible.

Examples:
  # 1) Generate pack from existing CSV+DB (no rerun)
  python tools/generate_maturity_pack.py --doi-csv doi_table.csv --staff-csv staff_table.csv --db data/mac_adg.db

  # 2) Run pipeline for all DOIs in doi_table.csv and record timings
  $env:PLAYWRIGHT_CAPTURE_AUTHOR_ROI='1'; $env:VISION_FORCE_AUTHOR_ROI='1'; $env:PLAYWRIGHT_DEVICE_SCALE_FACTOR='2'
  conda run -n doi python tools/generate_maturity_pack.py --run --force --doi-csv doi_table.csv --staff-csv staff_table.csv --db data/mac_adg.db

Notes:
- Charts require matplotlib. If missing, script still exports CSV + markdown.
"""

import argparse
import csv
import datetime as _dt
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# Allow running this script from within the `tools/` folder while still importing
# project packages like `backend.*` from the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _split_semicolon(s: str) -> List[str]:
    if not s:
        return []
    parts = [p.strip() for p in str(s).split(";")]
    return [p for p in parts if p]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _try_import_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except Exception:
        return None


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _build_doi_list_from_doi_table(doi_rows: List[Dict[str, str]]) -> List[str]:
    dois: List[str] = []
    for r in doi_rows:
        d = str(r.get("DOI") or "").strip()
        if d:
            dois.append(d)
    # keep order, de-dup
    seen = set()
    uniq: List[str] = []
    for d in dois:
        if d in seen:
            continue
        seen.add(d)
        uniq.append(d)
    return uniq


def _db_connect(db_path: Path):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _db_fetch_papers(conn) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT doi, title, journal, publish_date, pdf_path, status, created_at FROM papers",
            conn,
        )
    except Exception:
        return pd.DataFrame()


def _db_fetch_authors(conn) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            """
            SELECT
              id, paper_doi, rank, raw_name, raw_affiliation, raw_affiliations,
              is_corresponding, is_co_first,
              matched_faculty_id, confidence_score, matched_level, match_signals
            FROM paper_authors
            """,
            conn,
        )
    except Exception:
        return pd.DataFrame()


def _db_fetch_faculty(conn) -> pd.DataFrame:
    try:
        return pd.read_sql_query(
            "SELECT id, employee_id, name_zh, department, departments, name_en_list FROM faculty",
            conn,
        )
    except Exception:
        return pd.DataFrame()


def _count_affiliation_completeness(aff_series: pd.Series) -> Tuple[int, int]:
    # returns (non_unknown, total)
    total = int(len(aff_series))
    non_unknown = 0
    for v in aff_series.fillna("").astype(str).tolist():
        s = v.strip()
        if s and s.lower() != "unknown":
            non_unknown += 1
    return non_unknown, total


def _export_charts(out_dir: Path, tables: Dict[str, pd.DataFrame]) -> List[str]:
    """Export basic charts if matplotlib is available."""
    plt = _try_import_matplotlib()
    if plt is None:
        return ["matplotlib_not_installed"]

    notes: List[str] = []

    # 1) Status distribution
    if "status_summary" in tables and not tables["status_summary"].empty:
        df = tables["status_summary"]
        fig = plt.figure(figsize=(6, 4))
        ax = fig.add_subplot(111)
        ax.bar(df["status"].astype(str).tolist(), df["count"].astype(int).tolist())
        ax.set_title("Paper Status Distribution")
        ax.set_ylabel("count")
        fig.tight_layout()
        fig.savefig(str(out_dir / "status_distribution.png"), dpi=200)
        plt.close(fig)

    # 2) Matched authors per paper
    if "per_paper" in tables and not tables["per_paper"].empty:
        df = tables["per_paper"].copy()
        fig = plt.figure(figsize=(6, 4))
        ax = fig.add_subplot(111)
        ax.hist(df["matched_authors"].astype(int).tolist(), bins=10)
        ax.set_title("Matched Authors per Paper")
        ax.set_xlabel("matched_authors")
        ax.set_ylabel("papers")
        fig.tight_layout()
        fig.savefig(str(out_dir / "matched_authors_hist.png"), dpi=200)
        plt.close(fig)

    # 3) Capability increment bars
    if "capability_increment" in tables and not tables["capability_increment"].empty:
        df = tables["capability_increment"]
        # Expect columns: metric, scout_only, vision_fused
        if set(["metric", "scout_only", "vision_fused"]).issubset(set(df.columns)):
            # This table is often a template containing non-numeric placeholders.
            scout = pd.to_numeric(df["scout_only"], errors="coerce")
            vision = pd.to_numeric(df["vision_fused"], errors="coerce")
            if scout.notna().any() and vision.notna().any():
                fig = plt.figure(figsize=(7, 4))
                ax = fig.add_subplot(111)
                x = list(range(len(df)))
                ax.bar([i - 0.2 for i in x], scout.fillna(0.0).astype(float).tolist(), width=0.4, label="Scout")
                ax.bar([i + 0.2 for i in x], vision.fillna(0.0).astype(float).tolist(), width=0.4, label="Vision+Hover")
                ax.set_xticks(x)
                ax.set_xticklabels(df["metric"].astype(str).tolist(), rotation=20, ha="right")
                ax.set_title("Capability Increment")
                ax.legend()
                fig.tight_layout()
                fig.savefig(str(out_dir / "capability_increment.png"), dpi=200)
                plt.close(fig)
            else:
                notes.append("capability_increment_non_numeric_skipped")

    return notes


def _render_markdown_m4(stats: Dict[str, Any]) -> str:
    return f"""## 成熟度 4 级：使用必要研究方法记录一批数据（运行记录证明）

### 4.1 实验对象与数据规模
- 处理样本：{stats.get('n_dois', 'N/A')} 篇论文 DOI（来源：doi_table.csv）
- 教师名录库：{stats.get('n_staff', 'N/A')} 名四川大学教职工（来源：staff_table.csv）
- 数据库：SQLite（{stats.get('db_path', 'data/mac_adg.db')}），记录 papers / paper_authors / faculty 三张核心表

### 4.2 研究方法（系统运行与稳定性）
本项目采用多智能体协同的有限状态机（FSM）流程：Scout（API 侦察）→ Perception（网页截图 + hover/ROI + OCR）→ Judge（异构证据仲裁与身份匹配）→ Evolution（入库与终态）。

- 批处理策略：Orchestrator 在批次开始阶段对 DOI 状态进行一次性批量查询（SQL IN），避免 N 次 DB round-trip。
- 去重策略：重复 DOI 按策略（SKIP / OVERWRITE / PROMPT）决策，确保实验可重复性。
- 证据审计：截图与 sidecar（OCR/hover 文本、作者结构化输出）保留在 data/visual_slices 便于复核。

### 4.3 运行结果（真实统计）
- DOI 中含四川大学作者的论文数：{stats.get('has_scu', 'N/A')} / {stats.get('n_dois', 'N/A')}（比例 {stats.get('has_scu_ratio', 'N/A')}）
- 识别到的四川大学作者提及次数：{stats.get('scu_author_mentions', 'N/A')}（去重作者数 {stats.get('scu_author_unique', 'N/A')}）
- 共一标记出现的论文数：{stats.get('co_first_rows', 'N/A')}；通讯作者标记出现的论文数：{stats.get('corresponding_rows', 'N/A')}

### 4.4 可核验的运行证据（建议附录）
- 逐 DOI 耗时与成功状态：run_times.csv（若使用 --run）
- 页面截图与 hover sidecar：data/visual_slices/（如 *_page_author_data.json、*_author_roi.png）

（可选）若本次使用脚本对 50 DOI 进行了完整重跑，则在 run_times.csv 中记录每篇论文的端到端耗时，并可据此报告平均耗时与离散程度。
"""


def _render_markdown_m5(stats: Dict[str, Any]) -> str:
    return f"""## 成熟度 5 级：规范实验与 SI 证明（至少 3 组数据/表格 + 采集说明）

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

- DPI/缩放：Playwright 端采用 deviceScaleFactor={stats.get('device_scale_factor', 'N/A')}（可通过环境变量 PLAYWRIGHT_DEVICE_SCALE_FACTOR 配置），以提升微小角标与上标符号的渲染清晰度。
- ROI 动态锚定：在网页截图基础上额外截取作者块 ROI（PLAYWRIGHT_CAPTURE_AUTHOR_ROI=1 时启用），将“作者行/角标区域”作为高分辨率补充证据。
- 坐标仿射映射：ROI 截取与全图共享同一页面坐标系，ROI→全图通过（x,y,w,h）偏移完成映射，保证 OCR token 可回溯到原始截图位置，实现 sidecar 可审计。
- 异构证据仲裁：Judge 以 Crossref/hover/Vision 三类证据对作者权益（通讯/共一）与单位信息进行融合，并将 match_signals 写入数据库，便于抽样复核。

### 5.5 图表（与表格对应的可视化证据）
若已安装 matplotlib，则本脚本会自动生成并保存如下图表文件（与表 A1/A2 对应）：

![论文终态分布（A1）](status_distribution.png)

![每篇论文匹配到教师库的作者条目数分布（A2）](matched_authors_hist.png)

（若图片未生成：请在 doi 环境安装 matplotlib 后重新运行脚本：`conda run -n doi python -m pip install matplotlib`）
"""


def _render_markdown_m6(stats: Dict[str, Any]) -> str:
    return f"""## 成熟度 6 级：软件生成图表、数据分析与讨论（讨论部分）

### 6.1 结果总览与规律发现
基于 {stats.get('n_dois', 'N/A')} 篇 DOI 的运行结果，系统已能够稳定输出：论文终态（COMPLETED/NEEDS_REVIEW/SKIPPED）、作者结构化信息（单位/权益标记）、以及与四川大学教师库的身份匹配结果。

本次统计摘要（由系统自动汇总）：
- 论文终态 Top1：{stats.get('top_status', 'N/A')}（{stats.get('top_status_count', 'N/A')} 篇）
- 平均每篇论文作者数：{stats.get('mean_total_authors', 'N/A')}；平均匹配到教师库作者数：{stats.get('mean_matched_authors', 'N/A')}

- 图 6-1（status_distribution.png）：论文终态分布，反映 FSM 在异构网页环境下的鲁棒性。
- 图 6-2（matched_authors_hist.png）：每篇论文匹配到教师库的作者条目数分布，用于评估学术贡献覆盖度。

![图 6-1 论文终态分布](status_distribution.png)

![图 6-2 匹配作者条目数分布](matched_authors_hist.png)

### 6.2 纵向对比：ROI 增强对微小角标识别的影响
本系统在 Perception 阶段引入作者块 ROI 截取与高 DPI 渲染，其核心目标是提升微小角标（例如 *、†、数字上标）的可见性，从而提高通讯/共一标记与单位映射的可恢复性。

- 若在同一 DOI 子集上进行 A/B（关闭 ROI vs 开启 ROI）消融实验，可将“通讯/共一标记识别率”与“单位完整率”作为主指标，统计提升幅度（%）。

### 6.3 横向对标：复杂版式下的优势
相较于传统仅依赖 PDF 文本层或单一 API 元数据的解析工具，MAC-ADG 通过网页 hover/click + OCR + 规则仲裁实现“结构化证据链”。在多栏版面、动态作者面板（如 Nature 系）等场景下，系统具备：
- 更强的证据覆盖：hover/click 可直接获取作者-单位映射；OCR 作为兜底补全。
- 更强的可解释性：sidecar 与 match_signals 使每条作者结论可追溯。
- 更可控的误报：身份确认必须满足“姓名+单位双一致”；姓名匹配但单位冲突/缺失进入 NEEDS_REVIEW，降低误判风险。

（建议在报告中附上 2-3 个代表性 DOI 的证据包截图与 author 表格片段，作为讨论部分的定性支撑。）
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate maturity evidence pack (4/5/6) for MAC-ADG")
    parser.add_argument("--doi-csv", type=str, default="doi_table.csv")
    parser.add_argument("--staff-csv", type=str, default="staff_table.csv")
    parser.add_argument("--db", type=str, default="data/mac_adg.db")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: data/exports/maturity_pack_TIMESTAMP)")
    parser.add_argument("--run", action="store_true", help="Run orchestrator for all DOIs (records per-DOI runtime)")
    parser.add_argument("--force", action="store_true", help="Force reprocess when running orchestrator")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of DOIs to run/analyze (0 = all)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    doi_csv = (root / args.doi_csv).resolve() if not os.path.isabs(args.doi_csv) else Path(args.doi_csv)
    staff_csv = (root / args.staff_csv).resolve() if not os.path.isabs(args.staff_csv) else Path(args.staff_csv)
    db_path = (root / args.db).resolve() if not os.path.isabs(args.db) else Path(args.db)
    if not db_path.exists():
        fallback_db = (root / "data" / "mac_adg.db").resolve()
        if fallback_db.exists():
            print(f"[WARN] db not found: {db_path}; falling back to: {fallback_db}", flush=True)
            db_path = fallback_db
        else:
            print(f"[WARN] db not found: {db_path}; DB-derived tables will be skipped.", flush=True)

    if args.out:
        out_dir = (root / args.out).resolve() if not os.path.isabs(args.out) else Path(args.out)
    else:
        out_dir = (root / "data" / "exports" / f"maturity_pack_{_now_tag()}").resolve()

    _ensure_dir(out_dir)

    print("[INFO] MAC-ADG maturity pack generator")
    print(f"[INFO] out_dir = {out_dir}")
    print(f"[INFO] doi_csv = {doi_csv}")
    print(f"[INFO] staff_csv = {staff_csv}")
    print(f"[INFO] db = {db_path}")
    print(f"[INFO] run_orchestrator = {bool(args.run)}; force = {bool(args.force)}; limit = {int(args.limit or 0)}")
    sys.stdout.flush()

    doi_rows = _read_csv_rows(doi_csv)
    staff_rows = _read_csv_rows(staff_csv)
    all_dois = _build_doi_list_from_doi_table(doi_rows)
    dois = list(all_dois)
    if args.limit and args.limit > 0:
        dois = dois[: int(args.limit)]

    doi_set = set(dois)
    doi_rows_considered = [
        r
        for r in doi_rows
        if str(r.get("DOI") or "").strip() and str(r.get("DOI") or "").strip() in doi_set
    ]

    # Basic stats from doi_table.csv
    n_dois = len(dois)
    has_scu = sum(1 for x in doi_rows_considered if str(x.get("是否有川大作者", "")).strip().upper() == "Y")
    co_first_rows = sum(1 for x in doi_rows_considered if str(x.get("是否共一", "")).strip().upper() == "Y")
    corresponding_rows = sum(1 for x in doi_rows_considered if str(x.get("是否通讯作者", "")).strip().upper() == "Y")
    names = [
        p.strip()
        for x in doi_rows_considered
        if str(x.get("是否有川大作者", "")).strip().upper() == "Y"
        for p in str(x.get("川大作者姓名", "") or "").split(";")
        if p.strip()
    ]

    # Env parameters (recorded as SI evidence)
    device_scale_factor = os.getenv("PLAYWRIGHT_DEVICE_SCALE_FACTOR", "")

    stats: Dict[str, Any] = {
        "n_dois": n_dois,
        "n_staff": len(staff_rows),
        "has_scu": has_scu,
        "has_scu_ratio": (f"{(has_scu / n_dois * 100.0):.1f}%" if n_dois else "N/A"),
        "co_first_rows": co_first_rows,
        "corresponding_rows": corresponding_rows,
        "scu_author_mentions": len(names),
        "scu_author_unique": len(set(names)),
        "device_scale_factor": device_scale_factor or "(unset)",
        "db_path": str(db_path),
    }

    # Export DOI list
    (out_dir / "dois.txt").write_text("\n".join(dois) + "\n", encoding="utf-8")
    print(f"[INFO] loaded_dois = {len(dois)} (written to dois.txt)", flush=True)

    # Optional: run orchestrator and record timing
    run_times: List[Dict[str, Any]] = []
    if args.run:
        print("[INFO] Running Orchestrator for DOIs... (this may take a while; progress will print per DOI)", flush=True)
        from backend.orchestrator import Orchestrator
        from backend.utils.schemas import DuplicateStrategy
        from database.connection import get_db
        from database.settings import get_duplicate_strategy, set_duplicate_strategy

        prev_strategy = None
        if args.force:
            db = next(get_db())
            try:
                prev_strategy = get_duplicate_strategy(db)
                set_duplicate_strategy(db, DuplicateStrategy.OVERWRITE)
            finally:
                db.close()

        orch = Orchestrator()
        try:
            for i, doi in enumerate(dois, 1):
                print(f"[RUN] {i}/{len(dois)} {doi}", flush=True)
                t0 = time.perf_counter()
                ok = True
                err = ""
                status = ""
                try:
                    recs = orch.process_dois([doi])
                    if isinstance(recs, list) and recs:
                        r0 = recs[0]
                        if isinstance(r0, dict):
                            status = str(r0.get("status") or "")
                except Exception as exc:
                    ok = False
                    err = str(exc)
                t1 = time.perf_counter()
                run_times.append(
                    {
                        "idx": i,
                        "doi": doi,
                        "success": ok,
                        "status": status,
                        "elapsed_sec": round(float(t1 - t0), 3),
                        "error": err,
                    }
                )

                # Write incremental progress so the output folder isn't empty during long runs.
                pd.DataFrame(run_times).to_csv(out_dir / "run_times.csv", index=False, encoding="utf-8-sig")
                print(
                    f"[DONE] {i}/{len(dois)} success={ok} status={status!s} elapsed_sec={run_times[-1]['elapsed_sec']}",
                    flush=True,
                )
        finally:
            if prev_strategy is not None:
                db = next(get_db())
                try:
                    set_duplicate_strategy(db, prev_strategy)
                finally:
                    db.close()

        if run_times:
            elapsed = [x["elapsed_sec"] for x in run_times if x.get("success")]
            if elapsed:
                stats["mean_elapsed_sec"] = round(sum(elapsed) / len(elapsed), 3)
                stats["p90_elapsed_sec"] = round(sorted(elapsed)[int(0.9 * (len(elapsed) - 1))], 3)

    # DB-derived tables
    tables: Dict[str, pd.DataFrame] = {}
    if db_path.exists():
        conn = _db_connect(db_path)
        try:
            papers = _db_fetch_papers(conn)
            authors = _db_fetch_authors(conn)
            faculty = _db_fetch_faculty(conn)
        finally:
            conn.close()

        if not papers.empty:
            status_summary = papers.groupby("status").size().reset_index(name="count").sort_values("count", ascending=False)
            tables["status_summary"] = status_summary
            status_summary.to_csv(out_dir / "status_summary.csv", index=False, encoding="utf-8-sig")

            try:
                if not status_summary.empty:
                    stats["top_status"] = str(status_summary.iloc[0]["status"])
                    stats["top_status_count"] = int(status_summary.iloc[0]["count"])
            except Exception:
                pass

        if not authors.empty:
            # per paper
            per_paper = authors.groupby("paper_doi").agg(
                total_authors=("id", "count"),
                matched_authors=("matched_faculty_id", lambda s: int(pd.notna(s).sum())),
                needs_review_authors=("match_signals", lambda s: int(sum(1 for x in s.fillna("").astype(str).tolist() if 'name_only_candidate' in x or 'school_affiliation_hit' in x))),
            ).reset_index().rename(columns={"paper_doi": "doi"})
            tables["per_paper"] = per_paper
            per_paper.to_csv(out_dir / "per_paper_summary.csv", index=False, encoding="utf-8-sig")

            try:
                stats["mean_total_authors"] = round(float(per_paper["total_authors"].astype(float).mean()), 2)
                stats["mean_matched_authors"] = round(float(per_paper["matched_authors"].astype(float).mean()), 2)
            except Exception:
                pass

            # affiliation completeness
            non_unknown, total_aff = _count_affiliation_completeness(authors.get("raw_affiliation", pd.Series(dtype=str)))
            stats["aff_non_unknown"] = non_unknown
            stats["aff_total"] = total_aff
            stats["aff_non_unknown_ratio"] = f"{(non_unknown / total_aff * 100.0):.1f}%" if total_aff else "N/A"

            # identity audit: suspicious affiliations and needs_review
            susp_terms = ["锦城", "Jincheng", "职业", "Vocational", "中学", "High School"]
            def _is_susp(v: str) -> bool:
                t = str(v or "")
                return any(k.lower() in t.lower() for k in susp_terms)

            audit_rows: List[Dict[str, Any]] = []
            for _, row in authors.head(5000).iterrows():
                aff = str(row.get("raw_affiliation") or "")
                ms = str(row.get("match_signals") or "")
                if _is_susp(aff) or ("name_only_candidate" in ms):
                    audit_rows.append(
                        {
                            "doi": row.get("paper_doi"),
                            "rank": row.get("rank"),
                            "raw_name": row.get("raw_name"),
                            "raw_affiliation": aff,
                            "matched_faculty_id": row.get("matched_faculty_id"),
                            "confidence_score": row.get("confidence_score"),
                            "match_signals": ms[:600],
                        }
                    )
            identity_audit = pd.DataFrame(audit_rows)
            tables["identity_audit"] = identity_audit
            identity_audit.to_csv(out_dir / "identity_audit.csv", index=False, encoding="utf-8-sig")

        if not faculty.empty:
            faculty.to_csv(out_dir / "faculty_dump.csv", index=False, encoding="utf-8-sig")

    # Capability increment: produce a template table (real increment requires running scout+vision separately)
    inc = pd.DataFrame(
        [
            {"metric": "affiliation_non_unknown_ratio", "scout_only": "(需要运行采样)", "vision_fused": stats.get("aff_non_unknown_ratio", "N/A")},
            {"metric": "corresponding_flag_rows", "scout_only": "(需要运行采样)", "vision_fused": corresponding_rows},
            {"metric": "co_first_flag_rows", "scout_only": "(需要运行采样)", "vision_fused": co_first_rows},
        ]
    )
    tables["capability_increment"] = inc
    inc.to_csv(out_dir / "capability_increment.csv", index=False, encoding="utf-8-sig")

    # Precision validation: export a 10-DOI annotation template
    sample = dois[:10]
    precision_template = pd.DataFrame(
        [
            {
                "doi": d,
                "gt_has_scu_author(Y/N)": "",
                "gt_corresponding_present(Y/N)": "",
                "gt_co_first_present(Y/N)": "",
                "notes": "",
            }
            for d in sample
        ]
    )
    precision_template.to_csv(out_dir / "precision_gt_template_10.csv", index=False, encoding="utf-8-sig")

    # Export charts
    chart_notes = _export_charts(out_dir, tables)

    # Write report sections
    _write_text(out_dir / "maturity_level_4.md", _render_markdown_m4(stats))
    _write_text(out_dir / "maturity_level_5.md", _render_markdown_m5(stats))
    _write_text(out_dir / "maturity_level_6.md", _render_markdown_m6(stats))

    # Write run config
    _write_json(
        out_dir / "run_config.json",
        {
            "inputs": {
                "doi_csv": str(doi_csv),
                "staff_csv": str(staff_csv),
                "db": str(db_path),
            },
            "args": {
                "run": bool(args.run),
                "force": bool(args.force),
                "limit": int(args.limit or 0),
            },
            "env": {
                "PLAYWRIGHT_DEVICE_SCALE_FACTOR": os.getenv("PLAYWRIGHT_DEVICE_SCALE_FACTOR"),
                "PLAYWRIGHT_CAPTURE_AUTHOR_ROI": os.getenv("PLAYWRIGHT_CAPTURE_AUTHOR_ROI"),
                "VISION_FORCE_AUTHOR_ROI": os.getenv("VISION_FORCE_AUTHOR_ROI"),
                "VISION_SKIP_OCR_IF_HOVER_COMPLETE": os.getenv("VISION_SKIP_OCR_IF_HOVER_COMPLETE"),
            },
            "chart_notes": chart_notes,
            "stats": stats,
        },
    )

    print(f"[OK] Maturity pack generated: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
