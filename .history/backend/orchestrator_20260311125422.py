import pandas as pd
from typing import List, Dict

from .agents.scout_agent import ScoutAgent
from .agents.vision_agent import VisionAgent
from .agents.judge_agent import JudgeAgent


class Orchestrator:
    """运行 Scout→Vision→Judge 流水线的中央协调器。

    该类设计得很简洁；这样可以让 Streamlit 页面和任何未来的 CLI 工具
    能够重用单一实现，而不必重复编写循环逻辑。
    """

    def __init__(self):
        self.scout = ScoutAgent()
        self.vision = VisionAgent()
        self.judge = JudgeAgent()

    # ------------------------------------------------------------------
    # 公开辅助函数
    # ------------------------------------------------------------------
    def process_dois(self, dois: List[str]) -> List[Dict]:
        """为一组 DOI 运行完整流水线。

        返回由 ScoutAgent 生成的原始字典列表，附加了一些便利的键。
        """
        results = []
        total = len(dois)
        for index, doi in enumerate(dois, start=1):
            doi = doi.strip()
            record: Dict = {"doi": doi}
            try:
                # 1. Scout 代理
                scout_data = self.scout.run(doi)
                record.update(scout_data)

                # 2. Vision 代理（直接传递 DOI 给新的 GUI 代理）
                vision_data = self.vision.process(doi)
                record["vision_text_length"] = len(vision_data.get("text", ""))

                # 3. Judge 代理（内部写入数据库）
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

