# Maturity 4/5/6 Evidence Pack Guide

This project includes a one-shot script to generate midterm-report evidence for maturity levels 4/5/6.

## What it generates
Output folder: `data/exports/maturity_pack_YYYYMMDD_HHMMSS/`

- `maturity_level_4.md` / `maturity_level_5.md` / `maturity_level_6.md`
- Tables (CSV):
  - `status_summary.csv`
  - `per_paper_summary.csv`
  - `capability_increment.csv`
  - `identity_audit.csv`
  - `faculty_dump.csv` (if DB has faculty table)
  - `run_times.csv` (only when `--run`)
- Charts (PNG, optional):
  - `status_distribution.png`
  - `matched_authors_hist.png`
  - `capability_increment.png`
  - If matplotlib is missing, CSV+MD are still generated.
- Annotation template (for maturity-5 precision validation):
  - `precision_gt_template_10.csv`

## Minimal usage
### A) Generate pack from existing CSV + DB (no rerun)
```powershell
conda run -n doi python -m tools.generate_maturity_pack --doi-csv doi_table.csv --staff-csv staff_table.csv --db data/mac_adg.db
```

### B) Re-run all 50 DOIs (force overwrite) + record per-DOI timing
```powershell
$env:PLAYWRIGHT_CAPTURE_AUTHOR_ROI='1'
$env:VISION_FORCE_AUTHOR_ROI='1'
$env:PLAYWRIGHT_DEVICE_SCALE_FACTOR='2'
conda run -n doi python -m tools.generate_maturity_pack --run --force --doi-csv doi_table.csv --staff-csv staff_table.csv --db data/mac_adg.db
```

## Notes
- With `--run`, the first DOI can take a while (Playwright + OCR). The script prints per-DOI progress and writes `run_times.csv` incrementally.
- If you want charts, install matplotlib:
```powershell
conda run -n doi python -m pip install matplotlib
```
- The script never fabricates numeric results; all numbers in markdown are computed from your CSV/DB.
- The maturity-5 “precision” table is generated as a **ground-truth template**; fill it manually for 10 samples, then keep it as SI attachment.
