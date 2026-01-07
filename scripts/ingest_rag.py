import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, get_engine, load_metadata
from src.cleaning import clean_portfolio_data

def ingest_rag_history(csv_path):
    print(f"Processing RAG Foundation History from {csv_path}...")
    
    # 1. Load Raw Data
    raw_rag = pd.read_csv(csv_path)
    
    # 2. Setup the 'Files Map' with the key 'RAG'
    # This triggers the filtering logic in src/cleaning.py
    files_map = {'RAG': raw_rag}
    
    # 3. Load Metadata
    meta = {
        'urls': load_metadata('meta_urls'),
        'names': load_metadata('meta_name_changes'),
        'tags': load_metadata('meta_tech_tags'),
        'funds': load_metadata('meta_fund_names')
    }
    
    # 4. Run Cleaning
    # This will automatically DROP 'Isomer II', 'Isomer III', 'Isomer Capital Secondaries'
    print("Cleaning and filtering overlaps...")
    clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
    # 5. Map Columns (Ensure these match your CSV headers)
    db_column_map = {
        'LPA Num': 'lpa_num',
        'Company Name': 'company_name',
        'Isomer Fund': 'isomer_fund',
        'Fund Name': 'fund_name',
        "Cost in Isomer's Share EUR": 'cost_eur',
        "Valuation of Isomer's Share EUR": 'value_eur',
        "Distributions EUR": 'distributions_eur',
        'Multiple': 'multiple',
        'Status': 'status',
        'Country': 'country',
        'Technology Tag': 'technology_tag',
        'Business Model': 'business_model',
        'URL': 'url',
        'Invest Year': 'invest_year',
        'Description': 'description',
        'Long Description': 'long_description',
        'SDGs': 'sdgs',
        'Female Founders': 'female_founders',
        # Map your date/quarter column
        'Invest Quarter': 'reporting_quarter' 
    }
    
    clean_df.rename(columns=db_column_map, inplace=True)
    
    # Filter for valid DB columns
    valid_cols = [c for c in clean_df.columns if c in db_column_map.values()]
    final_df = clean_df[valid_cols]
    
    # 6. Save to DB
    engine = get_engine()
    final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
    print(f"✅ Successfully ingested {len(final_df)} RAG rows (overlaps removed).")

if __name__ == "__main__":
    init_db()
    # Update path to your file
    ingest_rag_history("data/rag_historic_data.csv")