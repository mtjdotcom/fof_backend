import pandas as pd
import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import get_engine, load_metadata

def harvest_missing_funds(history_file):
    print(f"🚜 Harvesting missing funds from {history_file}...")
    engine = get_engine()
    
    # 1. Load Historic Data
    try:
        df = pd.read_csv(history_file)
        # Assuming 'Fund Name' is the column header. Change if it's 'fund_name' etc.
        unique_raw_funds = df['Fund Name'].unique()
        print(f"   Found {len(unique_raw_funds)} unique funds in history file.")
    except Exception as e:
        print(f"❌ Error reading history file: {e}")
        return

    # 2. Load Existing DB Funds
    existing_funds_df = load_metadata('isomer_funds')
    
    existing_set = set()
    if not existing_funds_df.empty:
        existing_set = set(existing_funds_df['fund_name'].unique())

    # 3. Find Missing
    new_funds = []
    for fund in unique_raw_funds:
        if pd.notna(fund) and fund not in existing_set:
            new_funds.append(fund)
            
    if not new_funds:
        print("✅ No new funds found. Your DB is up to date!")
        return

    print(f"   Found {len(new_funds)} NEW funds not in DB.")

    # 4. Prepare DataFrame to Insert
    # We default 'Isomer Fund' to 'Review Me' so you can spot them easily in Tab 4
    new_rows = pd.DataFrame({
        'fund_name': new_funds,
        'isomer_fund': 'Review Me', # Placeholder
        'vintage_year': 2015,       # Placeholder
        'isomer_commitment_eur': 0,
        'isomer_ic_date': None,
        'lpac_seat': False
    })
    
    # 5. Append to DB
    new_rows.to_sql('isomer_funds', engine, if_exists='append', index=False)
    print(f"✅ Added {len(new_rows)} funds to 'isomer_funds' table.")
    print("👉 Next Step: Go to Page 2 -> Tab 4 and assign the correct 'Isomer Fund' for these new rows.")

if __name__ == "__main__":
    harvest_missing_funds("data/historic_data.csv")