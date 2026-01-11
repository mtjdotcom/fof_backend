import pandas as pd
from src.database import get_engine

def check_join_quality():
    engine = get_engine()
    
    # 1. Load the two tables
    portfolio = pd.read_sql("SELECT clean_fund_name, cost_eur FROM portfolio_entries", engine)
    funds_master = pd.read_sql("SELECT clean_fund_name, isomer_fund FROM isomer_funds", engine)
    
    # 2. Perform the Join
    merged = pd.merge(portfolio, funds_master, on='clean_fund_name', how='left', indicator=True)
    
    # 3. Calculate Stats
    total_rows = len(merged)
    matched_rows = len(merged[merged['_merge'] == 'both'])
    match_rate = (matched_rows / total_rows) * 100
    
    print(f"--- 🔗 JOIN QUALITY REPORT ---")
    print(f"Total Portfolio Entries: {total_rows}")
    print(f"Successfully Matched:    {matched_rows} ({match_rate:.1f}%)")
    
    # 4. Show the "Orphans" (Funds that didn't match)
    if match_rate < 100:
        orphans = merged[merged['_merge'] == 'left_only']['clean_fund_name'].unique()
        print(f"\n⚠️  These {len(orphans)} funds found NO match in the Master List:")
        print(orphans[:10]) # Show first 10
    else:
        print("\n✅ PERFECT MATCH! Every entry links to a Master Fund.")

if __name__ == "__main__":
    check_join_quality()