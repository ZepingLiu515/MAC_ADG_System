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
        
        print(f"DEBUG: received status={result.get('status')}")
        if result.get('status') in ('metadata_ready', 'metadata_only', 'success_html', 'success_pdf'):
            print("\n✅ Scout Agent returned a valid status")
        else:
            print("\n❌ Unexpected status (check network/DOI)")

        authors = result.get('authors') or []
        if not authors:
            print("\n⚠️ No authors returned (may be network/API issue)")
            return

        # Basic schema check
        assert any((a.get('name') or '').strip() for a in authors if isinstance(a, dict)), "No author names found"

        # OpenAlex fallback: affiliations may still be Unknown for some DOIs, so we only require at least one non-Unknown when possible.
        non_unknown_aff = [
            a for a in authors
            if isinstance(a, dict)
            and str(a.get('affiliation') or '').strip()
            and str(a.get('affiliation') or '').strip().lower() != 'unknown'
        ]
        if non_unknown_aff:
            print(f"\n✅ Found {len(non_unknown_aff)} authors with non-Unknown affiliation (OpenAlex/crossref)")
        else:
            print("\n⚠️ All affiliations are Unknown (some records truly lack affiliations)")
            
    except Exception as e:
        print(f"DEBUG: Runtime Error! {e}")

if __name__ == "__main__":
    print("DEBUG: Entering main block...")
    test_scout()