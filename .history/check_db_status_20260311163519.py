"""检查数据库状态"""
from database.connection import SessionLocal
from database.models import Faculty, Paper, PaperAuthor
import json

db = SessionLocal()

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

papers = db.query(Paper).all()
for p in papers:
    title_preview = p.title[:80] if p.title else "N/A"
    print(f'DOI: {p.doi}')
    print(f'  标题: {title_preview}...')
    print(f'  期刊: {p.journal}')
    
print('\n' + '=' * 70)
print('[数据库检查] PaperAuthor 记录')
print('=' * 70)

authors = db.query(PaperAuthor).all()
if not authors:
    print('[无记录]')
else:
    for a in authors:
        print(f'作者: {a.raw_name} | DOI: {a.paper_doi} | 匹配教师ID: {a.matched_faculty_id} | 置信度: {a.confidence_score}% | 通讯作者: {a.is_corresponding} | 共同一作: {a.is_co_first}')

db.close()
