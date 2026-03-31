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

            # 3. Identity Matching Strategy (Simple String Match for MVP)
            # Strategy: "Reverse Search" - Iterate DB Faculty -> Search in Extracted Text
            
            full_text = vision_data.get("text", "").lower()
            all_faculty = db.query(Faculty).all()
            
            matched_count = 0
            
            for faculty in all_faculty:
                # 3.1 Check Name (Chinese Pinyin or English variants)
                variants = []
                if faculty.name_en_list:
                    try:
                        variants = json.loads(faculty.name_en_list)
                    except:
                        variants = []
                
                # combine chinese + english variants for scanning
                names_to_check = []
                if faculty.name_zh:
                    names_to_check.append(faculty.name_zh)
                names_to_check.extend(variants)

                found_name = None
                for name in names_to_check:
                    if name and name.lower() in full_text:
                        found_name = name
                        break

                if not found_name:
                    continue

                # simple marker detection in original full_text
                # search around first occurrence of found_name
                idx = full_text.find(found_name.lower())
                snippet = full_text[max(0, idx-5): idx+len(found_name)+5]
                is_corr = "*" in snippet
                is_cofst = "#" in snippet

                print(f"[Judge] MATCH FOUND: Faculty {faculty.name_zh} -> snippet='{snippet}'")

                existing_link = db.query(PaperAuthor).filter(
                    PaperAuthor.paper_doi == doi,
                    PaperAuthor.matched_faculty_id == faculty.id
                ).first()

                if not existing_link:
                    author_record = PaperAuthor(
                        paper_doi=doi,
                        rank=1, # Placeholder rank, future work: parse exact rank
                        raw_name=found_name,
                        matched_faculty_id=faculty.id,
                        is_corresponding=is_corr,
                        is_co_first=is_cofst
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