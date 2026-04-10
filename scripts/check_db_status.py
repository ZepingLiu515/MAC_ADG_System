"""检查数据库状态"""

# 允许从任意工作目录运行该脚本（例如在 scripts/ 目录直接运行）
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import argparse

from database.connection import SessionLocal
from database.models import Faculty, Paper, PaperAuthor

db = SessionLocal()

parser = argparse.ArgumentParser(description="Check MAC-ADG SQLite database status")
parser.add_argument("--doi", type=str, default="", help="Optional: only show records for a specific DOI")
args = parser.parse_args()

doi_filter = (args.doi or "").strip()

print('=' * 70)
print('[数据库检查] Faculty 记录')
print('=' * 70)

faculties = db.query(Faculty).all()
for f in faculties:
    en_list = json.loads(f.name_en_list) if isinstance(f.name_en_list, str) else f.name_en_list
    print(f'ID: {f.id} | 中文: {f.name_zh} | 英文: {en_list} | 部门: {f.department}')

print('\n' + '=' * 70)
print('[数据库检查] Paper 记录')
print('=' * 70)

papers_q = db.query(Paper)
if doi_filter:
    papers_q = papers_q.filter(Paper.doi == doi_filter)
papers = papers_q.all()
for p in papers:
    title_preview = p.title[:80] if p.title else "N/A"
    print(f'DOI: {p.doi}')
    print(f'  标题: {title_preview}...')
    print(f'  期刊: {p.journal}')
    print(f'  状态: {p.status}')
    
print('\n' + '=' * 70)
print('[数据库检查] PaperAuthor 记录')
print('=' * 70)

authors_q = db.query(PaperAuthor)
if doi_filter:
    authors_q = authors_q.filter(PaperAuthor.paper_doi == doi_filter)
authors = authors_q.order_by(PaperAuthor.paper_doi, PaperAuthor.rank).all()
if not authors:
    print('[无记录]')
else:
    for a in authors:
        affs = None
        try:
            affs = json.loads(a.raw_affiliations) if isinstance(a.raw_affiliations, str) else a.raw_affiliations
        except Exception:
            affs = a.raw_affiliations

        print(
            f'作者: {a.raw_name} | DOI: {a.paper_doi} | 匹配教师ID: {a.matched_faculty_id} '
            f'| 置信度: {a.confidence_score}% | 通讯: {a.is_corresponding} | 共一: {a.is_co_first}'
        )
        if affs:
            print(f'  多单位: {affs}')
        else:
            print(f'  单位: {a.raw_affiliation}')

db.close()
