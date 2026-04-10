from backend.agents.judge_agent import JudgeAgent


def test_merge_preserves_openalex_corresponding():
    judge = JudgeAgent()

    crossref_authors = [
        {
            "name": "Charles R. Harris",
            "affiliation": "Independent researcher",
            "order": 1,
            "is_corresponding": True,  # from OpenAlex enrichment
            "is_co_first": False,
        },
        {
            "name": "K. Jarrod Millman",
            "affiliation": "University of California, Berkeley",
            "order": 2,
            "is_corresponding": False,
            "is_co_first": False,
        },
    ]

    # Vision/hover data sometimes has different name formatting and may omit corresponding
    vision_authors = [
        {"name": "Charles Harris", "position": 1, "is_corresponding": False, "is_co_first": False},
        {"name": "K Jarrod Millman", "position": 2, "is_corresponding": True, "is_co_first": False},
    ]

    merged = judge._merge_authors(crossref_authors, vision_authors)

    assert merged[0]["is_corresponding"] is True, "Should preserve existing True corresponding flag"
    assert merged[1]["is_corresponding"] is True, "Should merge corresponding by order when name differs"


if __name__ == "__main__":
    test_merge_preserves_openalex_corresponding()
    print("OK")
