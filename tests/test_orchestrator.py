from backend.orchestrator import Orchestrator


def test_orchestrator():
    print("--- Testing Orchestrator Pipeline ---")
    orchestrator = Orchestrator()
    # use a known DOI that should be reachable
    sample = ["10.1038/s41586-020-2649-2"]
    results = orchestrator.process_dois(sample)
    print("Results:", results)
    if results and results[0].get("doi") == sample[0]:
        print("✅ Orchestrator returned expected record.")
    else:
        print("❌ Orchestrator test failed.")


if __name__ == "__main__":
    test_orchestrator()