print("DEBUG: Script has started running...")  # Line 1 verification

import sys
import os

# Add current directory to path just in case
sys.path.append(os.getcwd())

try:
    from backend.agents.scout_agent import ScoutAgent
    import json
    print("DEBUG: Modules imported successfully.")
except ImportError as e:
    print(f"DEBUG: Import Error! {e}")
    sys.exit(1)

def test_scout():
    print("--- Testing Scout Agent ---")
    
    try:
        agent = ScoutAgent()
        print("DEBUG: Agent initialized.")
        
        # Test Case: A Nature paper (Open Access)
        test_doi = "10.1038/s41586-020-2649-2"
        
        print(f"DEBUG: Running agent for DOI: {test_doi}")
        result = agent.run(test_doi)
        
        print("\n--- Result ---")
        print(json.dumps(result, indent=4))
        
        # the agent now returns multiple status codes
        # success_pdf / success_html / metadata_only / error
        print(f"DEBUG: received status={result.get('status')}")
        if result['status'] in ('success_pdf', 'success_html', 'metadata_only'):
            print("\n✅ Scout Agent Test Passed (valid status)")
        else:
            print("\n❌ Scout Agent Test Failed (unexpected status)")
            
    except Exception as e:
        print(f"DEBUG: Runtime Error! {e}")

if __name__ == "__main__":
    print("DEBUG: Entering main block...")
    test_scout()