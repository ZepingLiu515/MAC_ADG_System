from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Faculty, Paper, PaperAuthor
import json

class JudgeAgent:
    """
    [Judge Agent]
    Responsibilities:
    1. Cross-reference extracted authors with the local Faculty database.
    2. Persist the final Paper and Author records into SQLite.
    3. Determine 'Is this paper valid for our university?'
    """

    def __init__(self):
        pass

    def adjudicate(self, scout_data, vision_data):
        """
        Main entry point.
        Input: 
          - scout_data (dict): Metadata from Crossref/Unpaywall
          - vision_data (dict): Text extracted from PDF/HTML
        """
        doi = scout_data.get("doi")
        title = scout_data.get("title")
        journal = scout_data.get("journal")
        pub_date = scout_data.get("publish_date")
        
        print(f"[Judge] Adjudicating case: {doi}")

        # 1. Database Session
        db: Session = next(get_db())
        
        try:
            # 2. Check if Paper already exists (Avoid duplicates)
            existing_paper = db.query(Paper).filter(Paper.doi == doi).first()
            if existing_paper:
                print(f"[Judge] Paper already exists. Updating status.")
                # We reuse the existing paper record
                paper = existing_paper
            else:
                # Create new Paper record
                paper = Paper(
                    doi=doi,
                    title=title,
                    journal=journal,
                    publish_date=pub_date,
                    # Save local path if available
                    pdf_path=scout_data.get("pdf_path") or scout_data.get("html_path"), 
                    status="COMPLETED"
                )
                db.add(paper)
                db.flush() # Flush to get the ID ready

            # 3. Identity Matching Strategy (Enhanced L1+L2)
            full_text = vision_data.get("text", "").lower()
            all_faculty = db.query(Faculty).all()
            matched_count = 0

            # helper functions defined below
            def _quick_match(name, faculty_obj):
                from difflib import SequenceMatcher
                variants = []
                if faculty_obj.name_en_list:
                    try:
                        variants = json.loads(faculty_obj.name_en_list)
                    except:
                        variants = []
                candidates = []
                if faculty_obj.name_zh:
                    candidates.append(faculty_obj.name_zh)
                candidates.extend(variants)

                best = 0.0
                for variant in candidates:
                    if not variant:
                        continue
                    var = variant.lower()
                    nm = name.lower()
                    if var == nm:
                        return 1.0
                    if var in nm:
                        return 0.95
                    score = SequenceMatcher(None, var, nm).ratio()
                    if score > best:
                        best = score
                return best

            def _get_affiliation_synonyms(dept):
                # this could later load from a json file
                synonym_map = {
                    "四川大学物理学院": [
                        "school of physics, sichuan university",
                        "physics department, sichuan university",
                        "物理系"
                    ],
                    "四川大学华西医院": [
                        "huaxi hospital, sichuan university",
                        "west china hospital",
                        "west china medical school"
                    ]
                }
                return synonym_map.get(dept.lower(), [])

            def _affiliation_match(paper_aff, faculty_obj):
                if not paper_aff or not faculty_obj.department:
                    return 0.5
                paper_aff = paper_aff.lower()
                dept = faculty_obj.department.lower()
                if paper_aff == dept:
                    return 1.0
                if dept in paper_aff:
                    return 0.9
                for syn in _get_affiliation_synonyms(dept):
                    if syn in paper_aff:
                        return 0.85
                # keyword fallback
                kws = [w for w in dept.replace(',', ' ').split() if w]
                matched = sum(1 for kw in kws if kw in paper_aff)
                if matched > 0:
                    return 0.5 + 0.2 * min(matched / len(kws), 1.0)
                return 0.0

            def _calculate_confidence(name, aff, coauthors, faculty_obj, score_l1):
                # weights: name 0.5, aff 0.4, coauthor 0.1
                s_name = score_l1
                s_aff = _affiliation_match(aff, faculty_obj)
                s_co = 0.5
                if coauthors:
                    matchc = 0
                    for ca in coauthors:
                        if _quick_match(ca, faculty_obj) > 0.8:
                            matchc += 1
                    s_co = 0.5 + 0.5 * min(matchc / len(coauthors), 1.0)
                return min(1.0, 0.5 * s_name + 0.4 * s_aff + 0.1 * s_co), {
                    'name': s_name, 'aff': s_aff, 'coauthor': s_co
                }

            # parse author list from vision_data
            vision_authors = vision_data.get("authors", [])
            if not vision_authors:
                vision_authors = [{'name': 'Unknown', 'affiliation': '', 'position': 1}]

            for pa in vision_authors:
                pname = pa.get('name', '')
                paff = pa.get('affiliation', '')
                prank = pa.get('position', 999)
                coauthors = [x.get('name') for x in vision_authors if x.get('name') != pname]
                is_corr = pa.get('is_corresponding', False)
                is_cofst = pa.get('is_co_first', False)

                # L1 filtering
                candidates = []
                for faculty in all_faculty:
                    score1 = _quick_match(pname, faculty)
                    if score1 > 0.6:
                        candidates.append((faculty, score1))
                if not candidates:
                    continue

                # L2 scoring
                scored = []
                for faculty, s1 in candidates:
                    conf, signals = _calculate_confidence(pname, paff, coauthors, faculty, s1)
                    scored.append((faculty, conf, s1, signals))
                scored.sort(key=lambda t: t[1], reverse=True)

                best_faculty, best_conf, best_s1, best_signals = scored[0]
                level = 'L1' if best_conf >= 0.8 else 'L2'
                # in future we may add L3

                existing_link = db.query(PaperAuthor).filter(
                    PaperAuthor.paper_doi == doi,
                    PaperAuthor.matched_faculty_id == best_faculty.id
                ).first()

                if not existing_link:
                    author_record = PaperAuthor(
                        paper_doi=doi,
                        rank=prank,
                        raw_name=pname,
                        raw_affiliation=paff,
                        matched_faculty_id=best_faculty.id,
                        is_corresponding=is_corr,
                        is_co_first=is_cofst,
                        confidence_score=int(best_conf * 100),
                        matched_level=level,
                        match_signals=best_signals
                    )
                    db.add(author_record)
                    matched_count += 1

            db.commit()
            print(f"[Judge] Case Closed. Matched {matched_count} faculty members.")
            return True

        except Exception as e:
            db.rollback()
            print(f"[Judge] Error: {e}")
            return False
        finally:
            db.close()