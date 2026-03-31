import pandas as pd
from typing import List, Dict

from .agents.scout_agent import ScoutAgent
from .agents.vision_agent import VisionAgent
from .agents.judge_agent import JudgeAgent


class Orchestrator:
    """Central coordinator that runs the Scout→Vision→Judge pipeline.

    The class is intentionally simple; it exists so that the Streamlit pages and
    any future CLI tools can reuse a single implementation rather than
    duplicating the loop logic.
    """

    def __init__(self):
        self.scout = ScoutAgent()
        self.vision = VisionAgent()
        self.judge = JudgeAgent()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def process_dois(self, dois: List[str]) -> List[Dict]:
        """Run the full pipeline for a list of DOIs.

        Returns a list of the raw dictionaries produced by the ScoutAgent with
        a few additional keys for convenience.
        """
        results = []
        total = len(dois)
        for index, doi in enumerate(dois, start=1):
            doi = doi.strip()
            record: Dict = {"doi": doi}
            try:
                # 1. Scout
                scout_data = self.scout.run(doi)
                record.update(scout_data)

                # 2. Vision (pass DOI directly to new GUI agent)
                vision_data = self.vision.process(doi)
                record["vision_text_length"] = len(vision_data.get("text", ""))

                # 3. Judge (writes to database internally)
                self.judge.adjudicate(scout_data, vision_data)

            except Exception as exc:
                record["error"] = str(exc)
            results.append(record)
        return results

    def process_excel(self, excel_file) -> List[Dict]:
        """Convenience wrapper that accepts a Streamlit-uploaded Excel
        object or a file path and extracts the DOI column automatically.
        """
        df = pd.read_excel(excel_file)
        doi_col = next((c for c in df.columns if str(c).lower() == "doi"), None)
        if doi_col is None:
            raise ValueError("Excel file must contain a 'DOI' column")
        dois = df[doi_col].astype(str).tolist()
        return self.process_dois(dois)

