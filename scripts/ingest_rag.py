import pandas as pd
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, get_engine
from src.cleaning import clean_portfolio_data

def ingest_rag_history(file_path):
    engine = get_engine()
    print(f"Processing RAG Foundation History from {file_path}...")
    
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {file_path}")
        return

    # Check for overlapping funds
    print("Cleaning and filtering overlaps...")
    rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
    if 'Fund Name' in df.columns:
        df = df[~df['Fund Name'].isin(rag_exclusions)]

    files_map = {"RAG": df}
    
    try:
        meta = {
            'urls': pd.read_sql("SELECT * FROM meta_urls", engine),
            'names': pd.read_sql("SELECT * FROM meta_name_changes", engine),
            'tags': pd.read_sql("SELECT * FROM meta_tech_tags", engine),
            'funds': pd.read_sql("SELECT * FROM meta_fund_names", engine),
            # --- FIX: Add Master Funds here ---
            'master_funds': pd.read_sql("SELECT * FROM isomer_funds", engine)
        }
    except Exception as e:
        print(f"⚠️ Warning: Metadata load failed ({e}).")
        meta = {}

    clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
    # DB Mapping
    db_map = {
        'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
        'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
        'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
        'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
        'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
        "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
        "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url'
    }
    
    clean_df.rename(columns=db_map, inplace=True)
    valid_cols = [c for c in clean_df.columns if c in db_map.values()]
    final_df = clean_df[valid_cols]

    final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
    print(f"✅ Successfully ingested {len(final_df)} RAG rows (overlaps removed).")

if __name__ == "__main__":
    # Note: We don't run init_db() here to avoid wiping the table if running sequentially
    ingest_rag_history("data/rag_historic_data.csv")

# import pandas as pd
# import sys
# import os

# # Add project root to path
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# from src.database import init_db, get_engine, load_metadata
# from src.cleaning import clean_portfolio_data

# def ingest_rag_history(csv_path):
#     print(f"Processing RAG Foundation History from {csv_path}...")
    
#     # 1. Load Raw Data
#     raw_rag = pd.read_csv(csv_path)
    
#     # 2. Setup the 'Files Map' with the key 'RAG'
#     # This triggers the filtering logic in src/cleaning.py
#     files_map = {'RAG': raw_rag}
    
#     # 3. Load Metadata
#     meta = {
#         'urls': load_metadata('meta_urls'),
#         'names': load_metadata('meta_name_changes'),
#         'tags': load_metadata('meta_tech_tags'),
#         'funds': load_metadata('meta_fund_names')
#     }
    
#     # 4. Run Cleaning
#     # This will automatically DROP 'Isomer II', 'Isomer III', 'Isomer Capital Secondaries'
#     print("Cleaning and filtering overlaps...")
#     clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
#     # 5. Map Columns (Ensure these match your CSV headers)
#     db_column_map = {
#         'LPA Num': 'lpa_num',
#         'Company Name': 'company_name',
#         'Isomer Fund': 'isomer_fund',
#         'Fund Name': 'fund_name',
#         "Cost in Isomer's Share EUR": 'cost_eur',
#         "Valuation of Isomer's Share EUR": 'value_eur',
#         "Distributions EUR": 'distributions_eur',
#         'Multiple': 'multiple',
#         'Status': 'status',
#         'Country': 'country',
#         'Technology Tag': 'technology_tag',
#         'Business Model': 'business_model',
#         'URL': 'url',
#         'Invest Year': 'invest_year',
#         'Description': 'description',
#         'Long Description': 'long_description',
#         'SDGs': 'sdgs',
#         'Female Founders': 'female_founders',
#         # Map your date/quarter column
#         'Invest Quarter': 'reporting_quarter' 
#     }
    
#     clean_df.rename(columns=db_column_map, inplace=True)
    
#     # Filter for valid DB columns
#     valid_cols = [c for c in clean_df.columns if c in db_column_map.values()]
#     final_df = clean_df[valid_cols]
    
#     # 6. Save to DB
#     engine = get_engine()
#     final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
#     print(f"✅ Successfully ingested {len(final_df)} RAG rows (overlaps removed).")

# if __name__ == "__main__":
#     init_db()
#     # Update path to your file
#     ingest_rag_history("data/rag_historic_data.csv")