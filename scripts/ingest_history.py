import pandas as pd
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, get_engine
from src.cleaning import clean_portfolio_data

def ingest_portfolio_history(file_path):
    engine = get_engine()
    print(f"Processing 50k Portfolio History from {file_path}...")
    
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {file_path}")
        return

    files_map = {"Historic_Dump": df}
    
    try:
        meta = {
            'urls': pd.read_sql("SELECT * FROM meta_urls", engine),
            'names': pd.read_sql("SELECT * FROM meta_name_changes", engine),
            'tags': pd.read_sql("SELECT * FROM meta_tech_tags", engine),
            'funds': pd.read_sql("SELECT * FROM meta_fund_names", engine), # For cleaning names
            'master_funds': pd.read_sql("SELECT * FROM isomer_funds", engine) # For Isomer Fund Lookup
        }
    except Exception as e:
        print(f"⚠️ Warning: Metadata load failed ({e}). Cleaning will be less effective.")
        meta = {
            'urls': pd.DataFrame(), 
            'names': pd.DataFrame(), 
            'tags': pd.DataFrame(), 
            'funds': pd.DataFrame(),
            'master_funds': pd.DataFrame()
        }

    print("Running cleaning logic (this may take a moment)...")
    clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
    # --- DB MAPPING ---
    db_map = {
        'LPA Num': 'lpa_num',
        'Company Name': 'company_name',
        'Isomer Fund': 'isomer_fund',
        'Fund Name': 'fund_name',
        'Reporting Quarter': 'reporting_quarter',
        'Invest Quarter': 'invest_quarter',
        'Invest Year': 'invest_year',
        'Initial Investment Date': 'initial_investment_date',
        'Data as of Date': 'data_as_of_date',
        'Status': 'status',
        'Country': 'country',
        'Technology Tag': 'technology_tag',
        'Business Model': 'business_model',
        'Description': 'description',
        'Long Description': 'long_description',
        'SDGs': 'sdgs',
        'Female Founders': 'female_founders',
        "Cost in Isomer's Share EUR": 'cost_eur',
        "Valuation of Isomer's Share EUR": 'value_eur',
        "Distributions EUR": 'distributions_eur',
        'Multiple': 'multiple',
        'URL': 'url'
    }
    
    final_df = clean_df.rename(columns=db_map)
    
    valid_cols = [
        'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 
        'reporting_quarter', 'invest_quarter', 'invest_year', 
        'initial_investment_date', 'data_as_of_date',
        'status', 'country', 'technology_tag', 'business_model', 
        'description', 'long_description', 'sdgs', 'female_founders', 
        'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
    ]
    
    cols_to_save = [c for c in valid_cols if c in final_df.columns]
    final_df = final_df[cols_to_save]

    final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
    print(f"✅ Successfully ingested {len(final_df)} historic portfolio rows.")

if __name__ == "__main__":
    init_db()
    ingest_portfolio_history("data/historic_data.csv")

# import pandas as pd
# import sys
# import os
# from sqlalchemy import text

# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# from src.database import init_db, get_engine
# from src.cleaning import clean_portfolio_data

# def ingest_portfolio_history(file_path):
#     engine = get_engine()
#     print(f"Processing 50k Portfolio History from {file_path}...")
    
#     try:
#         df = pd.read_csv(file_path)
#     except FileNotFoundError:
#         print(f"❌ Error: File not found at {file_path}")
#         return

#     files_map = {"Historic_Dump": df}
    
#     try:
#         # --- FIX IS HERE ---
#         # We load 'meta_fund_names' for the cleaning map (dirty -> clean)
#         # instead of 'isomer_funds' (which is the master commitment list)
#         meta = {
#             'urls': pd.read_sql("SELECT * FROM meta_urls", engine),
#             'names': pd.read_sql("SELECT * FROM meta_name_changes", engine),
#             'tags': pd.read_sql("SELECT * FROM meta_tech_tags", engine),
#             'funds': pd.read_sql("SELECT * FROM meta_fund_names", engine) 
#         }
#     except Exception as e:
#         print(f"⚠️ Warning: Metadata load failed ({e}). Cleaning will be less effective.")
#         meta = {
#             'urls': pd.DataFrame(), 
#             'names': pd.DataFrame(), 
#             'tags': pd.DataFrame(), 
#             'funds': pd.DataFrame(columns=['original_fund', 'cleaned_fund']) # Ensure columns exist to prevent KeyError
#         }

#     print("Running cleaning logic (this may take a moment)...")
#     clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
#     # --- DB MAPPING ---
#     db_map = {
#         'LPA Num': 'lpa_num',
#         'Company Name': 'company_name',
#         'Isomer Fund': 'isomer_fund',
#         'Fund Name': 'fund_name',
#         'Reporting Quarter': 'reporting_quarter',
#         'Invest Quarter': 'invest_quarter',
#         'Invest Year': 'invest_year',
#         'Initial Investment Date': 'initial_investment_date',
#         'Data as of Date': 'data_as_of_date',
#         'Status': 'status',
#         'Country': 'country',
#         'Technology Tag': 'technology_tag',
#         'Business Model': 'business_model',
#         'Description': 'description',
#         'Long Description': 'long_description',
#         'SDGs': 'sdgs',
#         'Female Founders': 'female_founders',
#         "Cost in Isomer's Share EUR": 'cost_eur',
#         "Valuation of Isomer's Share EUR": 'value_eur',
#         "Distributions EUR": 'distributions_eur',
#         'Multiple': 'multiple',
#         'URL': 'url'
#     }
    
#     final_df = clean_df.rename(columns=db_map)
    
#     valid_cols = [
#         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 
#         'reporting_quarter', 'invest_quarter', 'invest_year', 
#         'initial_investment_date', 'data_as_of_date',
#         'status', 'country', 'technology_tag', 'business_model', 
#         'description', 'long_description', 'sdgs', 'female_founders', 
#         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
#     ]
    
#     cols_to_save = [c for c in valid_cols if c in final_df.columns]
#     final_df = final_df[cols_to_save]

#     final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
#     print(f"✅ Successfully ingested {len(final_df)} historic portfolio rows.")

# if __name__ == "__main__":
#     init_db()
#     ingest_portfolio_history("data/historic_data.csv")

# # import pandas as pd
# # import sys
# # import os
# # from sqlalchemy import text

# # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# # from src.database import init_db, get_engine
# # from src.cleaning import clean_portfolio_data

# # def ingest_portfolio_history(file_path):
# #     engine = get_engine()
# #     print(f"Processing 50k Portfolio History from {file_path}...")
    
# #     try:
# #         df = pd.read_csv(file_path)
# #     except FileNotFoundError:
# #         print(f"❌ Error: File not found at {file_path}")
# #         return

# #     files_map = {"Historic_Dump": df}
    
# #     try:
# #         meta = {
# #             'urls': pd.read_sql("SELECT * FROM meta_urls", engine),
# #             'names': pd.read_sql("SELECT * FROM meta_name_changes", engine),
# #             'tags': pd.read_sql("SELECT * FROM meta_tech_tags", engine),
# #             'funds': pd.read_sql("SELECT * FROM isomer_funds", engine)
# #         }
# #     except Exception as e:
# #         meta = {'urls': pd.DataFrame(), 'names': pd.DataFrame(), 'tags': pd.DataFrame(), 'funds': pd.DataFrame()}

# #     print("Running cleaning logic (this may take a moment)...")
# #     clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
# #     # --- DB MAPPING ---
# #     db_map = {
# #         'LPA Num': 'lpa_num',
# #         'Company Name': 'company_name',
# #         'Isomer Fund': 'isomer_fund',
# #         'Fund Name': 'fund_name',
# #         'Reporting Quarter': 'reporting_quarter',
# #         'Invest Quarter': 'invest_quarter',
# #         'Invest Year': 'invest_year',
# #         'Initial Investment Date': 'initial_investment_date', # <--- MAPPED
# #         'Data as of Date': 'data_as_of_date',
# #         'Status': 'status',
# #         'Country': 'country',
# #         'Technology Tag': 'technology_tag',
# #         'Business Model': 'business_model',
# #         'Description': 'description',
# #         'Long Description': 'long_description',
# #         'SDGs': 'sdgs',
# #         'Female Founders': 'female_founders',
# #         "Cost in Isomer's Share EUR": 'cost_eur',
# #         "Valuation of Isomer's Share EUR": 'value_eur',
# #         "Distributions EUR": 'distributions_eur',
# #         'Multiple': 'multiple',
# #         'URL': 'url'
# #     }
    
# #     final_df = clean_df.rename(columns=db_map)
    
# #     valid_cols = [
# #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 
# #         'reporting_quarter', 'invest_quarter', 'invest_year', 
# #         'initial_investment_date', 'data_as_of_date', # <--- VALIDATED
# #         'status', 'country', 'technology_tag', 'business_model', 
# #         'description', 'long_description', 'sdgs', 'female_founders', 
# #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# #     ]
    
# #     cols_to_save = [c for c in valid_cols if c in final_df.columns]
# #     final_df = final_df[cols_to_save]

# #     final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
# #     print(f"✅ Successfully ingested {len(final_df)} historic portfolio rows.")

# # if __name__ == "__main__":
# #     init_db()
# #     ingest_portfolio_history("data/historic_data.csv")

# # # import pandas as pd
# # # import sys
# # # import os

# # # # Add the project root to python path so we can import src
# # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# # # from src.database import init_db, get_engine, load_metadata
# # # from src.cleaning import clean_portfolio_data

# # # def ingest_isomer_funds(csv_path):
# # #     """
# # #     Job A: Load the Master Fund Commitments table.
# # #     """
# # #     print(f"Loading Isomer Funds from {csv_path}...")
# # #     df = pd.read_csv(csv_path)
    
# # #     # Normalize Column Names to match DB Schema
# # #     # CSV Header: ['fund_name', 'vintage_year', 'ccy', 'size_ccy', 'isomer_commitment_ccy', 'Isomer Commitment EUR', 'share_of_partnership', 'isomer_fund', 'organisation', 'HQ', 'Stage of Investment', 'Allocation type', 'LPAC Seat', 'Isomer IC Date']
# # #     rename_map = {
# # #         'Isomer Commitment EUR': 'isomer_commitment_eur',
# # #         'HQ': 'hq',
# # #         'Stage of Investment': 'stage_of_investment',
# # #         'Allocation type': 'allocation_type',
# # #         'LPAC Seat': 'lpac_seat',
# # #         'Isomer IC Date': 'isomer_ic_date'
# # #     }
# # #     df.rename(columns=rename_map, inplace=True)
    
# # #     # Handle Date Conversion (European format dd/mm/yyyy)
# # #     df['isomer_ic_date'] = pd.to_datetime(df['isomer_ic_date'], dayfirst=True)
    
# # #     # Save to DB
# # #     engine = get_engine()
# # #     try:
# # #         df.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # #         print(f"✅ Successfully loaded {len(df)} fund commitments.")
# # #     except Exception as e:
# # #         print(f"❌ Error loading funds: {e}")

# # # def ingest_portfolio_history(csv_path):
# # #     """
# # #     Job B: Clean and Load the 50k row historic dump.
# # #     """
# # #     print(f"Processing 50k Portfolio History from {csv_path}...")
    
# # #     # 1. Load Raw Data
# # #     raw_history = pd.read_csv(csv_path)
    
# # #     # 2. Simulate 'Files Map' for the cleaner
# # #     files_map = {'Historic_Dump': raw_history}
    
# # #     # 3. Load Metadata for Cleaning
# # #     meta = {
# # #         'urls': load_metadata('meta_urls'),
# # #         'names': load_metadata('meta_name_changes'),
# # #         'tags': load_metadata('meta_tech_tags'),
# # #         'funds': load_metadata('meta_fund_names')
# # #     }
    
# # #     # 4. Run Cleaning (Granular Mode)
# # #     print("Running cleaning logic (this may take a moment)...")
# # #     clean_df = clean_portfolio_data(files_map, meta, mode='duplicates')
    
# # #     # 5. Map Columns to DB Schema
# # #     # Note: Ensure your raw CSV has a column we can map to 'reporting_quarter' 
# # #     # (e.g., 'Data as of Date' or 'Quarter')
    
# # #     db_column_map = {
# # #         'LPA Num': 'lpa_num',
# # #         'Company Name': 'company_name',
# # #         'Isomer Fund': 'isomer_fund', # From the 'Historic_Dump' key or file column
# # #         'Fund Name': 'fund_name',
# # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # #         "Distributions EUR": 'distributions_eur',
# # #         'Multiple': 'multiple',
# # #         'Status': 'status',
# # #         'Country': 'country',
# # #         'Technology Tag': 'technology_tag',
# # #         'Business Model': 'business_model',
# # #         'URL': 'url',
# # #         'Invest Year': 'invest_year',
# # #         'Description': 'description',
# # #         'Long Description': 'long_description',
# # #         'SDGs': 'sdgs',
# # #         'Female Founders': 'female_founders',
# # #         # Crucial: Map your historic date column to 'reporting_quarter'
# # #         'Invest Quarter': 'invest_quarter' 
# # #     }
    
# # #     # Apply mapping
# # #     clean_df.rename(columns=db_column_map, inplace=True)
    
# # #     # Keep only valid columns
# # #     valid_cols = [c for c in clean_df.columns if c in db_column_map.values()]
# # #     final_df = clean_df[valid_cols]
    
# # #     # 6. Save
# # #     engine = get_engine()
# # #     final_df.to_sql('portfolio_entries', engine, if_exists='append', index=False)
# # #     print(f"✅ Successfully ingested {len(final_df)} historic portfolio rows.")

# # # if __name__ == "__main__":
# # #     # Initialize DB tables first
# # #     init_db()
    
# # #     # Run Ingestion (Update paths to where your CSVs are)
# # #     ingest_isomer_funds("data/isomer_funds.csv")
    
# # #     ingest_portfolio_history("data/historic_data.csv") 