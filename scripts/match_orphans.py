import pandas as pd
from difflib import get_close_matches
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.database import get_engine

def find_matches():
    engine = get_engine()
    print("🕵️‍♂️  Hunting for Orphans...")

    # 1. Get the lists
    # Orphans = Funds in Portfolio History that DON'T exist in Isomer Funds
    portfolio_funds = pd.read_sql("SELECT DISTINCT clean_fund_name FROM portfolio_entries WHERE clean_fund_name IS NOT NULL", engine)
    master_funds = pd.read_sql("SELECT DISTINCT clean_fund_name FROM isomer_funds WHERE clean_fund_name IS NOT NULL", engine)
    
    # Set difference: What is in Portfolio but NOT in Master?
    p_set = set(portfolio_funds['clean_fund_name'])
    m_set = set(master_funds['clean_fund_name'])
    orphans = list(p_set - m_set)
    
    print(f"   Found {len(orphans)} unmatched funds.")

    # 2. Fuzzy Match
    results = []
    # Convert master set to list for indexing
    master_list = list(m_set)
    
    print("   ...Calculating similarity scores (this may take a moment)...")
    
    for orphan in orphans:
        # Find closest match (cutoff=0.4 means "at least 40% similar")
        matches = get_close_matches(orphan, master_list, n=1, cutoff=0.4)
        
        if matches:
            best_match = matches[0]
            results.append({
                'original_fund': orphan,
                'suggested_match': best_match,
                'notes': 'High Confidence' if orphan.lower() == best_match.lower() else 'Check Manually'
            })
        else:
            results.append({
                'original_fund': orphan,
                'suggested_match': None,
                'notes': 'No Match Found'
            })

    # 3. Save Report
    df_results = pd.DataFrame(results).sort_values('suggested_match')
    output_path = "data/suggested_fund_mappings.csv"
    df_results.to_csv(output_path, index=False)
    
    print(f"\n✅ Done! Check {output_path}")
    print("   -> Review this file.")
    print("   -> Copy the CORRECT matches into 'data/fund_name_changes_master.csv'")

if __name__ == "__main__":
    find_matches()