import pandas as pd
import sys
import os
from sqlalchemy import text

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.database import get_engine

def force_apply_mappings():
    engine = get_engine()
    print("🔧 STARTING FORCE REPAIR...")

    # 1. Get the Rules (The 17 overrides you loaded)
    try:
        map_df = pd.read_sql("SELECT original_fund, cleaned_fund FROM meta_fund_names", engine)
        if map_df.empty:
            print("❌ No mappings found in 'meta_fund_names'. Did you run seed_metadata.py?")
            return
        
        # Convert to dictionary: {'Atlantic Labs 2': 'Atlantic Labs II'}
        # We strip whitespace just in case
        map_df['original_fund'] = map_df['original_fund'].str.strip()
        map_df['cleaned_fund'] = map_df['cleaned_fund'].str.strip()
        name_map = dict(zip(map_df['original_fund'], map_df['cleaned_fund']))
        
        print(f"✅ Loaded {len(name_map)} mapping rules from database.")
    except Exception as e:
        print(f"❌ Error reading mappings: {e}")
        return

    # 2. Get the Portfolio Data
    try:
        df = pd.read_sql("SELECT * FROM portfolio_entries", engine)
        print(f"📉 Loaded {len(df)} portfolio rows.")
    except Exception as e:
        print(f"❌ Error reading portfolio: {e}")
        return

    # 3. Apply the Fix
    # Only verify changes on rows that actually exist in our map
    mask = df['clean_fund_name'].isin(name_map.keys())
    affected_rows = df[mask]
    
    if affected_rows.empty:
        print("⚠️  No rows matched your rules! Check if 'clean_fund_name' matches your CSV 'original_fund'.")
        # Debug: Show samples
        print("\nSample Portfolio Names:")
        print(df['clean_fund_name'].dropna().unique()[:5])
        print("\nSample Rules:")
        print(list(name_map.keys())[:5])
    else:
        # Apply the replace
        df.loc[mask, 'clean_fund_name'] = df.loc[mask, 'clean_fund_name'].replace(name_map)
        print(f"🔥 FIXED {len(affected_rows)} rows using manual overrides.")
        
        # 4. Save Back to DB
        # We replace the table to ensure the fix sticks
        df.to_sql('portfolio_entries', engine, if_exists='replace', index=False)
        print("💾 Database updated successfully.")

if __name__ == "__main__":
    force_apply_mappings()