import pandas as pd
import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, get_engine

def seed_metadata():
    engine = get_engine()
    print("🌱 Seeding Metadata Tables...")

    # 1. URLs (Has Header: LPA Num, Organization URL)
    try:
        urls_df = pd.read_csv("data/company_urls_master.csv")
        # Rename to match DB columns
        urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
        urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(urls_df)} URLs.")
    except FileNotFoundError:
        print("❌ Warning: 'company_urls_master.csv' not found.")

    # 2. Name Changes (No Header, Col 0 = original, Col 1 = new)
    try:
        names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
        names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(names_df)} Name Mappings.")
    except FileNotFoundError:
        print("❌ Warning: 'name_change_master.csv' not found.")

    # 3. Tech Tags (No Header)
    try:
        tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
        tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(tags_df)} Tech Tags.")
    except FileNotFoundError:
        print("❌ Warning: 'tech_tags_master.csv' not found.")

    # 4. Fund Names (No Header)
    try:
        funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
        funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(funds_df)} Fund Name Mappings.")
    except FileNotFoundError:
        print("❌ Warning: 'fund_name_changes_master.csv' not found.")

if __name__ == "__main__":
    init_db()
    seed_metadata()