import pandas as pd
import sys
import os
from difflib import SequenceMatcher
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.database import get_engine

def get_similarity(a, b):
    """Calculates similarity ratio between 0 and 1."""
    return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

def diagnose():
    print("🔍 DIAGNOSTIC MODE: Analyzing Unmatched Funds...")
    engine = get_engine()
    
    # 1. Get Top Unmatched Funds (The culprits)
    query = """
    SELECT fund_name, COUNT(*) as count 
    FROM portfolio_entries 
    WHERE isomer_fund = 'Historic_Dump' 
    GROUP BY fund_name 
    ORDER BY count DESC 
    LIMIT 20
    """
    try:
        unmatched = pd.read_sql(query, engine)
    except Exception as e:
        print(f"❌ Error reading DB: {e}")
        return

    if unmatched.empty:
        print("✅ No 'Historic_Dump' entries found! You are done.")
        return

    # 2. Get Master List (The Brain)
    try:
        master = pd.read_sql("SELECT * FROM isomer_funds", engine)
    except:
        print("❌ Could not load master funds.")
        return

    print(f"\nAnalyzing Top {len(unmatched)} Unmatched Funds against {len(master)} Master Funds...")
    
    # Check if alt columns exist and have data
    has_alt1 = 'alt_name_1' in master.columns and master['alt_name_1'].notna().any()
    has_alt2 = 'alt_name_2' in master.columns and master['alt_name_2'].notna().any()
    
    print(f"   > Master Table Columns: {list(master.columns)}")
    print(f"   > Has 'alt_name_1' data? {'✅ YES' if has_alt1 else '❌ NO (Did you re-seed?)'}")
    print(f"   > Has 'alt_name_2' data? {'✅ YES' if has_alt2 else '❌ NO'}")
    
    print("\n" + "="*110)
    print(f"{'UNMATCHED RAW NAME':<35} | {'BEST MATCH IN DB':<35} | {'SCORE':<5} | {'FOUND IN COLUMN'}")
    print("="*110)

    # 3. Find best match for each unmatched fund
    for _, row in unmatched.iterrows():
        target = row['fund_name']
        best_match = "No Match"
        best_score = 0.0
        best_col = "-"
        
        # Columns to check
        cols_to_check = ['fund_name']
        if 'alt_name_1' in master.columns: cols_to_check.append('alt_name_1')
        if 'alt_name_2' in master.columns: cols_to_check.append('alt_name_2')

        for _, master_row in master.iterrows():
            for col in cols_to_check:
                candidate = master_row[col]
                if pd.notna(candidate):
                    score = get_similarity(target, candidate)
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                        best_col = col
        
        # Interpretation
        status = ""
        if best_score >= 0.92: status = "✅ (Should have matched!)"
        elif best_score >= 0.85: status = "⚠️ (Close - try 0.85)"
        else: status = "❌ (Too different)"
        
        print(f"{str(target)[:35]:<35} | {str(best_match)[:35]:<35} | {best_score:.3f} | {best_col} {status}")

    print("="*110)
    print("\n💡 DIAGNOSIS:")
    if not has_alt1:
        print("🔴 CRITICAL: Your 'alt_name_1' column is empty in the database.")
        print("   Run 'python scripts/seed_metadata.py' to reload your CSV.")
    else:
        print("1. If scores are 0.85-0.91: Lower your threshold in src/cleaning.py to 0.85.")
        print("2. If scores are < 0.80: You need to add these specific spellings to your 'isomer_funds.csv'.")

if __name__ == "__main__":
    diagnose()