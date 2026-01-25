import os
import re
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# Database Path
DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
os.makedirs(DB_FOLDER, exist_ok=True)
DB_URL = f"sqlite:///{DB_FILE}"

def get_engine():
    return create_engine(DB_URL)

# --- 🛠️ CLEANING FUNCTION ---
def clean_fund_name(name):
    if not isinstance(name, str) or pd.isna(name) or name.strip() == "":
        return None
    name = " ".join(name.split())
    suffixes = [
        r'Gmbh\s*&\s*Co\.?\s*KG', r'Gmbh\s*&\s*Co\.?', r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', 
        r'Co[oö]peratief\s*U\.?A\.?', r'Guernsey\s*L\.?P\.?', r'Conopus\s*A\.?B\.?', 
        r'-\s*Units\s*A', r'Gmbh', r'L\.?\s*P\.?', r'L\.?\s*L\.?\s*P\.?', r'S\.?L\.?P\.?', 
        r'F\.?C\.?R\.?E\.?', r'F\.?C\.?R\.?', r'F\.?P\.?C\.?I\.?', r'S\.?C\.?Sp\.?', 
        r'S\.?C\.?S\.?', r'S\.?A\.?', r'S\.?C\.?A\.?', r'C\.?\s*V\.?', r'K\s*/\s*S', 
        r'K\.?y\.?', r'A\.?B\.?', r'B\.?V\.?', r'N\.?V\.?', r'Ltd\.?', r'Limited', 
        r'L\.?L\.?C\.?', r'Inc\.?', r'Co\.?', r'Corp\.?'
    ]
    pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    return clean.strip(' ,.-')

def load_metadata(table_name):
    """Load metadata table, returning empty DataFrame with correct columns if table doesn't exist."""
    # Define expected columns for each metadata table
    table_columns = {
        'meta_name_changes': ['original_name', 'new_name'],
        'meta_urls': ['lpa_num', 'url'],
        'meta_tech_tags': ['original_tag', 'cleaned_tag'],
        'meta_fund_names': ['original_fund', 'cleaned_fund'],
        'isomer_funds': ['fund_name', 'clean_fund_name', 'isomer_fund', 'organisation',
                         'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date',
                         'lpac_seat', 'alt_name_1', 'alt_name_2', 'default_deal_type'],
    }

    engine = get_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception as e:
        print(f"Error loading {table_name}: {e}")
        # Return empty DataFrame with correct columns if known
        if table_name in table_columns:
            return pd.DataFrame(columns=table_columns[table_name])
        return pd.DataFrame()

def init_db():
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))

        conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS isomer_funds (
                fund_name TEXT PRIMARY KEY,
                clean_fund_name TEXT,
                isomer_fund TEXT,
                organisation TEXT,
                vintage_year INTEGER,
                isomer_commitment_eur REAL,
                isomer_ic_date DATE,
                lpac_seat BOOLEAN,
                alt_name_1 TEXT,
                alt_name_2 TEXT,
                default_deal_type TEXT
            )
        """))

        # Fix isomer_funds table if fund_name column is missing
        result = conn.execute(text("PRAGMA table_info(isomer_funds)"))
        columns = [row[1] for row in result.fetchall()]
        if 'fund_name' not in columns:
            # Table exists but missing fund_name - recreate it
            conn.execute(text("DROP TABLE isomer_funds"))
            conn.execute(text("""
                CREATE TABLE isomer_funds (
                    fund_name TEXT PRIMARY KEY,
                    clean_fund_name TEXT,
                    isomer_fund TEXT,
                    organisation TEXT,
                    vintage_year INTEGER,
                    isomer_commitment_eur REAL,
                    isomer_ic_date DATE,
                    lpac_seat BOOLEAN,
                    alt_name_1 TEXT,
                    alt_name_2 TEXT,
                    default_deal_type TEXT
                )
            """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lpa_num INTEGER,
                company_name TEXT,
                isomer_fund TEXT,
                fund_name TEXT,
                clean_fund_name TEXT, 
                
                reporting_quarter TEXT,
                invest_quarter TEXT,
                invest_year INTEGER,
                initial_investment_date DATE,
                data_as_of_date DATE,
                
                status TEXT,
                country TEXT,
                technology_tag TEXT,
                business_model TEXT,
                description TEXT,
                long_description TEXT,
                sdgs TEXT,
                female_founders TEXT,
                cost_eur REAL,
                value_eur REAL,
                distributions_eur REAL,
                multiple REAL,
                
                deal_type TEXT,
                is_secondary BOOLEAN,
                is_coinvest BOOLEAN,
                
                url TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))
        conn.commit()


def save_raw_data(df, source_label):
    engine = get_engine()
    column_map = {
        'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
        'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
        'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
        'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
        'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
        'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
        'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
        'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
        'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
        'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
        'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
        'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
        'Long Description': 'long_description'
    }
    df_to_save = df.rename(columns=column_map)
    df_to_save['source_file'] = source_label
    valid_cols = list(column_map.values()) + ['source_file']
    final_cols = [c for c in valid_cols if c in df_to_save.columns]
    df_to_save = df_to_save[final_cols].astype(str)
    df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

def save_quarterly_data(df):
    engine = get_engine()
    col_map = {
        'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
        'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
        'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
        'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
        'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
        "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
        "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
        'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
    }
    
    # 1. Rename columns
    df = df.rename(columns=col_map)
    
    # 2. CREATE CLEAN FUND NAME (Before filtering!)
    if 'fund_name' in df.columns:
        df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
        
        # A. Regex Clean
        df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
        df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])

        # B. DICTIONARY OVERRIDE (I restored this block!)
        try:
            mapping_df = pd.read_sql("SELECT original_fund, cleaned_fund FROM meta_fund_names", engine)
            if not mapping_df.empty:
                # Create map: {'Atlantic Labs 2': 'Atlantic Labs II'}
                name_map = dict(zip(mapping_df['original_fund'], mapping_df['cleaned_fund']))
                
                # Apply map
                df['clean_fund_name'] = df['clean_fund_name'].replace(name_map)
                print(f"   🔄 Applied manual overrides from {len(name_map)} rules.")
        except Exception as e:
            print(f"   ⚠️ Could not apply mappings: {e}")

    # 3. Select columns
    valid_cols = [v for v in col_map.values() if v in df.columns]
    if 'clean_fund_name' in df.columns:
        valid_cols.append('clean_fund_name')
    df = df[valid_cols].copy() 

    # 4. Clean Dates
    date_cols = ['initial_investment_date', 'data_as_of_date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            df[col] = df[col].replace({pd.NaT: None, np.nan: None})

    df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# import os
# import re
# import pandas as pd
# import numpy as np
# from sqlalchemy import create_engine, text

# # Database Path
# DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# os.makedirs(DB_FOLDER, exist_ok=True)
# DB_URL = f"sqlite:///{DB_FILE}"

# def get_engine():
#     return create_engine(DB_URL)

# # --- 🛠️ CLEANING FUNCTION ---
# def clean_fund_name(name):
#     """
#     Standardizes fund names by stripping legal suffixes.
#     Returns the original name if no suffix is found.
#     """
#     if not isinstance(name, str) or pd.isna(name) or name.strip() == "":
#         return None
    
#     # 1. Normalize spaces
#     name = " ".join(name.split())
    
#     # 2. Comprehensive Suffix List
#     suffixes = [
#         # Complex / Compound
#         r'Gmbh\s*&\s*Co\.?\s*KG',          # GmbH & Co KG
#         r'Gmbh\s*&\s*Co\.?',               # GmbH & Co
#         r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', # SICAV-SIF, SCS
#         r'Co[oö]peratief\s*U\.?A\.?',      # Cooperatief U.A.
#         r'Guernsey\s*L\.?P\.?',            # Guernsey LP
#         r'Conopus\s*A\.?B\.?',             # Conopus AB
#         r'-\s*Units\s*A',                  # - Units A

#         # Standard Acronyms
#         r'Gmbh', 
#         r'L\.?\s*P\.?',                    # LP, L.P.
#         r'L\.?\s*L\.?\s*P\.?',             # LLP
#         r'S\.?L\.?P\.?',                   # SLP
#         r'F\.?C\.?R\.?E\.?',               # FCRE
#         r'F\.?C\.?R\.?',                   # FCR
#         r'F\.?P\.?C\.?I\.?',               # FPCI
#         r'S\.?C\.?Sp\.?',                  # SCSp
#         r'S\.?C\.?S\.?',                   # SCS
#         r'S\.?A\.?',                       # SA
#         r'S\.?C\.?A\.?',                   # SCA
#         r'C\.?\s*V\.?',                    # CV
#         r'K\s*/\s*S',                      # K/S
#         r'K\.?y\.?',                       # Ky
#         r'A\.?B\.?',                       # AB
#         r'B\.?V\.?',                       # BV
#         r'N\.?V\.?',                       # NV
        
#         # Corporate Generic
#         r'Ltd\.?', r'Limited', r'L\.?L\.?C\.?', r'Inc\.?', r'Co\.?', r'Corp\.?'
#     ]
    
#     # Build Regex
#     pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    
#     # Execute Strip (Case Insensitive)
#     clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
#     # Final cleanup
#     return clean.strip(' ,.-')

# def load_metadata(table_name):
#     engine = get_engine()
#     try:
#         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
#     except Exception as e:
#         print(f"Error loading {table_name}: {e}")
#         return pd.DataFrame()

# def init_db():
#     engine = get_engine()
#     with engine.connect() as conn:
        
#         # 1. Metadata Tables
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
#         # 2. Dimensions
#         conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

#         # 3. External Funds
#         conn.execute(text("""
#             CREATE TABLE IF NOT EXISTS isomer_funds (
#                 fund_name TEXT PRIMARY KEY,
#                 clean_fund_name TEXT,  
#                 isomer_fund TEXT,
#                 organisation TEXT,
#                 vintage_year INTEGER,
#                 isomer_commitment_eur REAL,
#                 isomer_ic_date DATE,
#                 lpac_seat BOOLEAN,
#                 alt_name_1 TEXT,
#                 alt_name_2 TEXT,
#                 default_deal_type TEXT 
#             )
#         """))

#         # 4. Cleaned Portfolio Data
#         conn.execute(text("""
#             CREATE TABLE IF NOT EXISTS portfolio_entries (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 lpa_num INTEGER,
#                 company_name TEXT,
#                 isomer_fund TEXT,
#                 fund_name TEXT,
#                 clean_fund_name TEXT, 
                
#                 reporting_quarter TEXT,
#                 invest_quarter TEXT,
#                 invest_year INTEGER,
#                 initial_investment_date DATE,
#                 data_as_of_date DATE,
                
#                 status TEXT,
#                 country TEXT,
#                 technology_tag TEXT,
#                 business_model TEXT,
#                 description TEXT,
#                 long_description TEXT,
#                 sdgs TEXT,
#                 female_founders TEXT,
#                 cost_eur REAL,
#                 value_eur REAL,
#                 distributions_eur REAL,
#                 multiple REAL,
                
#                 deal_type TEXT,
#                 is_secondary BOOLEAN,
#                 is_coinvest BOOLEAN,
                
#                 url TEXT,
#                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#             )
#         """))
        
#         # 5. Raw Data Vault
#         conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))

# def save_raw_data(df, source_label):
#     engine = get_engine()
#     column_map = {
#         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
#         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
#         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
#         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
#         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
#         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
#         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
#         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
#         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
#         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
#         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
#         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
#         'Long Description': 'long_description'
#     }
#     df_to_save = df.rename(columns=column_map)
#     df_to_save['source_file'] = source_label
#     valid_cols = list(column_map.values()) + ['source_file']
#     final_cols = [c for c in valid_cols if c in df_to_save.columns]
#     df_to_save = df_to_save[final_cols].astype(str)
#     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# def save_quarterly_data(df):
#     engine = get_engine()
#     col_map = {
#         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
#         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
#         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
#         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
#         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
#         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
#         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
#         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
#     }
    
#     # 1. Rename columns
#     df = df.rename(columns=col_map)
    
#     # 2. CREATE clean_fund_name FIRST (before filtering!)
#     if 'fund_name' in df.columns:
#         df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
#         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
#         df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])
        
#         print("   🧹 Cleaning Validation (First 3 rows):")
#         sample = df[['fund_name', 'clean_fund_name']].dropna().head(3)
#         for _, row in sample.iterrows():
#             print(f"      '{row['fund_name']}' -> '{row['clean_fund_name']}'")
    
#     # 3. Build valid_cols list INCLUDING clean_fund_name
#     valid_cols = [v for v in col_map.values() if v in df.columns]
#     if 'clean_fund_name' in df.columns:
#         valid_cols.append('clean_fund_name')
    
#     # 4. NOW filter
#     df = df[valid_cols].copy()

#     # 5. Clean Dates
#     date_cols = ['initial_investment_date', 'data_as_of_date']
#     for col in date_cols:
#         if col in df.columns:
#             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
#             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

#     # 6. Save
#     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # def save_quarterly_data(df):
# #     engine = get_engine()
# #     col_map = {
# #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# #     }
    
# #     # 1. Rename columns
# #     df = df.rename(columns=col_map)
    
# #     # 2. CREATE CLEAN FUND NAME (Before filtering!)
# #     if 'fund_name' in df.columns:
# #         # Force string type
# #         df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
# #         # Apply cleaner
# #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
# #         # Fallback to original
# #         df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])
        
# #         print("   🧹 Cleaning Validation (First 3 rows):")
# #         print(df[['fund_name', 'clean_fund_name']].head(3))

# #     # 3. SELECT COLUMNS TO KEEP
# #     # Start with mapped columns
# #     valid_cols = [v for v in col_map.values() if v in df.columns]
    
# #     # Explicitly ADD our new column to the list
# #     if 'clean_fund_name' in df.columns:
# #         valid_cols.append('clean_fund_name')
        
# #     # 4. FILTER (Now it's safe)
# #     df = df[valid_cols].copy() 

# #     # 5. Clean Dates
# #     date_cols = ['initial_investment_date', 'data_as_of_date']
# #     for col in date_cols:
# #         if col in df.columns:
# #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # import os
# # import re
# # import pandas as pd
# # import numpy as np
# # from sqlalchemy import create_engine, text

# # # Database Path
# # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # os.makedirs(DB_FOLDER, exist_ok=True)
# # DB_URL = f"sqlite:///{DB_FILE}"

# # def get_engine():
# #     return create_engine(DB_URL)

# # # --- 🛠️ CLEANING FUNCTION ---
# # def clean_fund_name(name):
# #     """
# #     Standardizes fund names by stripping legal suffixes.
# #     Returns the original name if no suffix is found.
# #     """
# #     if not isinstance(name, str) or pd.isna(name) or name.strip() == "":
# #         return None
    
# #     # 1. Normalize spaces
# #     name = " ".join(name.split())
    
# #     # 2. Comprehensive Suffix List
# #     suffixes = [
# #         # Complex / Compound
# #         r'Gmbh\s*&\s*Co\.?\s*KG',          # GmbH & Co KG
# #         r'Gmbh\s*&\s*Co\.?',               # GmbH & Co
# #         r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', # SICAV-SIF, SCS
# #         r'Co[oö]peratief\s*U\.?A\.?',      # Cooperatief U.A.
# #         r'Guernsey\s*L\.?P\.?',            # Guernsey LP
# #         r'Conopus\s*A\.?B\.?',             # Conopus AB
# #         r'-\s*Units\s*A',                  # - Units A

# #         # Standard Acronyms
# #         r'Gmbh', 
# #         r'L\.?\s*P\.?',                    # LP, L.P.
# #         r'L\.?\s*L\.?\s*P\.?',             # LLP
# #         r'S\.?L\.?P\.?',                   # SLP
# #         r'F\.?C\.?R\.?E\.?',               # FCRE
# #         r'F\.?C\.?R\.?',                   # FCR
# #         r'F\.?P\.?C\.?I\.?',               # FPCI
# #         r'S\.?C\.?Sp\.?',                  # SCSp
# #         r'S\.?C\.?S\.?',                   # SCS
# #         r'S\.?A\.?',                       # SA
# #         r'S\.?C\.?A\.?',                   # SCA
# #         r'C\.?\s*V\.?',                    # CV
# #         r'K\s*/\s*S',                      # K/S
# #         r'K\.?y\.?',                       # Ky
# #         r'A\.?B\.?',                       # AB
# #         r'B\.?V\.?',                       # BV
# #         r'N\.?V\.?',                       # NV
        
# #         # Corporate Generic
# #         r'Ltd\.?', r'Limited', r'L\.?L\.?C\.?', r'Inc\.?', r'Co\.?', r'Corp\.?'
# #     ]
    
# #     # Build Regex
# #     pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    
# #     # Execute Strip (Case Insensitive)
# #     clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
# #     # Final cleanup
# #     return clean.strip(' ,.-')

# # def load_metadata(table_name):
# #     engine = get_engine()
# #     try:
# #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# #     except Exception as e:
# #         print(f"Error loading {table_name}: {e}")
# #         return pd.DataFrame()

# # def init_db():
# #     engine = get_engine()
# #     with engine.connect() as conn:
        
# #         # 1. Metadata Tables
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# #         # 2. Dimensions
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

# #         # 3. External Funds
# #         conn.execute(text("""
# #             CREATE TABLE IF NOT EXISTS isomer_funds (
# #                 fund_name TEXT PRIMARY KEY,
# #                 clean_fund_name TEXT,  
# #                 isomer_fund TEXT,
# #                 organisation TEXT,
# #                 vintage_year INTEGER,
# #                 isomer_commitment_eur REAL,
# #                 isomer_ic_date DATE,
# #                 lpac_seat BOOLEAN,
# #                 alt_name_1 TEXT,
# #                 alt_name_2 TEXT,
# #                 default_deal_type TEXT 
# #             )
# #         """))

# #         # 4. Cleaned Portfolio Data
# #         conn.execute(text("""
# #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# #                 lpa_num INTEGER,
# #                 company_name TEXT,
# #                 isomer_fund TEXT,
# #                 fund_name TEXT,
# #                 clean_fund_name TEXT, 
                
# #                 reporting_quarter TEXT,
# #                 invest_quarter TEXT,
# #                 invest_year INTEGER,
# #                 initial_investment_date DATE,
# #                 data_as_of_date DATE,
                
# #                 status TEXT,
# #                 country TEXT,
# #                 technology_tag TEXT,
# #                 business_model TEXT,
# #                 description TEXT,
# #                 long_description TEXT,
# #                 sdgs TEXT,
# #                 female_founders TEXT,
# #                 cost_eur REAL,
# #                 value_eur REAL,
# #                 distributions_eur REAL,
# #                 multiple REAL,
                
# #                 deal_type TEXT,
# #                 is_secondary BOOLEAN,
# #                 is_coinvest BOOLEAN,
                
# #                 url TEXT,
# #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# #             )
# #         """))
        
# #         # 5. Raw Data Vault
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))

# # def save_raw_data(df, source_label):
# #     engine = get_engine()
# #     column_map = {
# #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# #         'Long Description': 'long_description'
# #     }
# #     df_to_save = df.rename(columns=column_map)
# #     df_to_save['source_file'] = source_label
# #     valid_cols = list(column_map.values()) + ['source_file']
# #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# #     df_to_save = df_to_save[final_cols].astype(str)
# #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # def save_quarterly_data(df):
# #     engine = get_engine()
# #     col_map = {
# #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# #     }
    
# #     # 1. RENAME COLUMNS (So 'fund_name' exists for the calculation)
# #     df = df.rename(columns=col_map)
    
# #     # 2. CREATE CLEAN FUND NAME (Before Filtering!)
# #     if 'fund_name' in df.columns:
# #         # Force string
# #         df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
# #         # Apply clean
# #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
# #         # Fallback
# #         df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])
        
# #         print("   🧹 Cleaning Validation (First 3 rows):")
# #         print(df[['fund_name', 'clean_fund_name']].head(3))

# #     # 3. SELECT COLUMNS TO KEEP
# #     # Start with mapped columns
# #     valid_cols = [v for v in col_map.values() if v in df.columns]
    
# #     # Explicitly ADD our new column to the list
# #     if 'clean_fund_name' in df.columns:
# #         valid_cols.append('clean_fund_name')
        
# #     # 4. FILTER (Now it's safe)
# #     df = df[valid_cols].copy() 

# #     # 5. Clean Dates
# #     date_cols = ['initial_investment_date', 'data_as_of_date']
# #     for col in date_cols:
# #         if col in df.columns:
# #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # import os
# # # import re
# # # import pandas as pd
# # # import numpy as np
# # # from sqlalchemy import create_engine, text

# # # # Database Path
# # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # DB_URL = f"sqlite:///{DB_FILE}"

# # # def get_engine():
# # #     return create_engine(DB_URL)

# # # # --- 🛠️ CLEANING FUNCTION ---
# # # def clean_fund_name(name):
# # #     """
# # #     Standardizes fund names by stripping legal suffixes.
# # #     Returns the original name if no suffix is found.
# # #     """
# # #     if not isinstance(name, str) or pd.isna(name) or name.strip() == "":
# # #         return None
    
# # #     # 1. Normalize spaces
# # #     name = " ".join(name.split())
    
# # #     # 2. Comprehensive Suffix List
# # #     suffixes = [
# # #         # Complex / Compound
# # #         r'Gmbh\s*&\s*Co\.?\s*KG',          # GmbH & Co KG
# # #         r'Gmbh\s*&\s*Co\.?',               # GmbH & Co
# # #         r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', # SICAV-SIF, SCS
# # #         r'Co[oö]peratief\s*U\.?A\.?',      # Cooperatief U.A.
# # #         r'Guernsey\s*L\.?P\.?',            # Guernsey LP
# # #         r'Conopus\s*A\.?B\.?',             # Conopus AB
# # #         r'-\s*Units\s*A',                  # - Units A

# # #         # Standard Acronyms
# # #         r'Gmbh', 
# # #         r'L\.?\s*P\.?',                    # LP, L.P.
# # #         r'L\.?\s*L\.?\s*P\.?',             # LLP
# # #         r'S\.?L\.?P\.?',                   # SLP
# # #         r'F\.?C\.?R\.?E\.?',               # FCRE
# # #         r'F\.?C\.?R\.?',                   # FCR
# # #         r'F\.?P\.?C\.?I\.?',               # FPCI
# # #         r'S\.?C\.?Sp\.?',                  # SCSp
# # #         r'S\.?C\.?S\.?',                   # SCS
# # #         r'S\.?A\.?',                       # SA
# # #         r'S\.?C\.?A\.?',                   # SCA
# # #         r'C\.?\s*V\.?',                    # CV
# # #         r'K\s*/\s*S',                      # K/S
# # #         r'K\.?y\.?',                       # Ky
# # #         r'A\.?B\.?',                       # AB
# # #         r'B\.?V\.?',                       # BV
# # #         r'N\.?V\.?',                       # NV
        
# # #         # Corporate Generic
# # #         r'Ltd\.?', r'Limited', r'L\.?L\.?C\.?', r'Inc\.?', r'Co\.?', r'Corp\.?'
# # #     ]
    
# # #     # Build Regex
# # #     pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    
# # #     # Execute Strip (Case Insensitive)
# # #     clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
# # #     # Final cleanup
# # #     return clean.strip(' ,.-')

# # # def load_metadata(table_name):
# # #     engine = get_engine()
# # #     try:
# # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # #     except Exception as e:
# # #         print(f"Error loading {table_name}: {e}")
# # #         return pd.DataFrame()

# # # def init_db():
# # #     engine = get_engine()
# # #     with engine.connect() as conn:
        
# # #         # 1. Metadata Tables
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # #         # 2. Dimensions
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

# # #         # 3. External Funds
# # #         conn.execute(text("""
# # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # #                 fund_name TEXT PRIMARY KEY,
# # #                 clean_fund_name TEXT,  
# # #                 isomer_fund TEXT,
# # #                 organisation TEXT,
# # #                 vintage_year INTEGER,
# # #                 isomer_commitment_eur REAL,
# # #                 isomer_ic_date DATE,
# # #                 lpac_seat BOOLEAN,
# # #                 alt_name_1 TEXT,
# # #                 alt_name_2 TEXT,
# # #                 default_deal_type TEXT 
# # #             )
# # #         """))

# # #         # 4. Cleaned Portfolio Data
# # #         conn.execute(text("""
# # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # #                 lpa_num INTEGER,
# # #                 company_name TEXT,
# # #                 isomer_fund TEXT,
# # #                 fund_name TEXT,
# # #                 clean_fund_name TEXT, 
                
# # #                 reporting_quarter TEXT,
# # #                 invest_quarter TEXT,
# # #                 invest_year INTEGER,
# # #                 initial_investment_date DATE,
# # #                 data_as_of_date DATE,
                
# # #                 status TEXT,
# # #                 country TEXT,
# # #                 technology_tag TEXT,
# # #                 business_model TEXT,
# # #                 description TEXT,
# # #                 long_description TEXT,
# # #                 sdgs TEXT,
# # #                 female_founders TEXT,
# # #                 cost_eur REAL,
# # #                 value_eur REAL,
# # #                 distributions_eur REAL,
# # #                 multiple REAL,
                
# # #                 deal_type TEXT,
# # #                 is_secondary BOOLEAN,
# # #                 is_coinvest BOOLEAN,
                
# # #                 url TEXT,
# # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # #             )
# # #         """))
        
# # #         # 5. Raw Data Vault
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))

# # # def save_raw_data(df, source_label):
# # #     engine = get_engine()
# # #     column_map = {
# # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # #         'Long Description': 'long_description'
# # #     }
# # #     df_to_save = df.rename(columns=column_map)
# # #     df_to_save['source_file'] = source_label
# # #     valid_cols = list(column_map.values()) + ['source_file']
# # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # #     df_to_save = df_to_save[final_cols].astype(str)
# # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # def save_quarterly_data(df):
# # #     engine = get_engine()
# # #     col_map = {
# # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # #     }
    
# # #     # 1. Rename columns
# # #     df = df.rename(columns=col_map)
    
# # #     # 2. GENERATE CLEAN FUND NAME (Before filtering!)
# # #     #    This ensures we have the source data ('fund_name') available.
# # #     if 'fund_name' in df.columns:
# # #         # Force string type to prevent object/float errors
# # #         df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
        
# # #         # Apply cleaner
# # #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
        
# # #         # Fallback: If cleaner returns empty/null, use original name
# # #         df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])
        
# # #         # Debug: Print first few to verify
# # #         print("   🧹 Cleaning Validation (First 3 rows):")
# # #         print(df[['fund_name', 'clean_fund_name']].head(3))

# # #     # 3. Filter Columns
# # #     #    We get the list from col_map, AND explicitly add our new 'clean_fund_name'
# # #     valid_cols = [v for v in col_map.values() if v in df.columns]
    
# # #     if 'clean_fund_name' in df.columns:
# # #         valid_cols.append('clean_fund_name')
        
# # #     df = df[valid_cols].copy() 

# # #     # 4. Clean Dates
# # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # #     for col in date_cols:
# # #         if col in df.columns:
# # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # import os
# # # # import re
# # # # import pandas as pd
# # # # import numpy as np
# # # # from sqlalchemy import create_engine, text

# # # # # Database Path
# # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # def get_engine():
# # # #     return create_engine(DB_URL)

# # # # # --- 🛠️ CLEANING FUNCTION ---
# # # # def clean_fund_name(name):
# # # #     """
# # # #     Standardizes fund names by stripping legal suffixes.
# # # #     Returns the original name if no suffix is found.
# # # #     """
# # # #     if not isinstance(name, str) or pd.isna(name) or name.strip() == "":
# # # #         return None
    
# # # #     # 1. Normalize spaces
# # # #     name = " ".join(name.split())
    
# # # #     # 2. Comprehensive Suffix List
# # # #     suffixes = [
# # # #         # Complex / Compound
# # # #         r'Gmbh\s*&\s*Co\.?\s*KG',          # GmbH & Co KG
# # # #         r'Gmbh\s*&\s*Co\.?',               # GmbH & Co
# # # #         r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', # SICAV-SIF, SCS
# # # #         r'Co[oö]peratief\s*U\.?A\.?',      # Cooperatief U.A.
# # # #         r'Guernsey\s*L\.?P\.?',            # Guernsey LP
# # # #         r'Conopus\s*A\.?B\.?',             # Conopus AB
# # # #         r'-\s*Units\s*A',                  # - Units A

# # # #         # Standard Acronyms
# # # #         r'Gmbh', 
# # # #         r'L\.?\s*P\.?',                    # LP, L.P.
# # # #         r'L\.?\s*L\.?\s*P\.?',             # LLP
# # # #         r'S\.?L\.?P\.?',                   # SLP
# # # #         r'F\.?C\.?R\.?E\.?',               # FCRE
# # # #         r'F\.?C\.?R\.?',                   # FCR
# # # #         r'F\.?P\.?C\.?I\.?',               # FPCI
# # # #         r'S\.?C\.?Sp\.?',                  # SCSp
# # # #         r'S\.?C\.?S\.?',                   # SCS
# # # #         r'S\.?A\.?',                       # SA
# # # #         r'S\.?C\.?A\.?',                   # SCA
# # # #         r'C\.?\s*V\.?',                    # CV
# # # #         r'K\s*/\s*S',                      # K/S
# # # #         r'K\.?y\.?',                       # Ky
# # # #         r'A\.?B\.?',                       # AB
# # # #         r'B\.?V\.?',                       # BV
# # # #         r'N\.?V\.?',                       # NV
        
# # # #         # Corporate Generic
# # # #         r'Ltd\.?', r'Limited', r'L\.?L\.?C\.?', r'Inc\.?', r'Co\.?', r'Corp\.?'
# # # #     ]
    
# # # #     # Build Regex
# # # #     pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    
# # # #     # Execute Strip (Case Insensitive)
# # # #     clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
# # # #     # Final cleanup
# # # #     return clean.strip(' ,.-')

# # # # # --- RESTORED HELPER FUNCTION ---
# # # # def load_metadata(table_name):
# # # #     engine = get_engine()
# # # #     try:
# # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # #     except Exception as e:
# # # #         print(f"Error loading {table_name}: {e}")
# # # #         return pd.DataFrame()

# # # # def init_db():
# # # #     engine = get_engine()
# # # #     with engine.connect() as conn:
        
# # # #         # 1. Metadata Tables
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # #         # 2. Dimensions
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

# # # #         # 3. External Funds
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # #                 fund_name TEXT PRIMARY KEY,
# # # #                 clean_fund_name TEXT,  
# # # #                 isomer_fund TEXT,
# # # #                 organisation TEXT,
# # # #                 vintage_year INTEGER,
# # # #                 isomer_commitment_eur REAL,
# # # #                 isomer_ic_date DATE,
# # # #                 lpac_seat BOOLEAN,
# # # #                 alt_name_1 TEXT,
# # # #                 alt_name_2 TEXT,
# # # #                 default_deal_type TEXT 
# # # #             )
# # # #         """))

# # # #         # 4. Cleaned Portfolio Data
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # #                 lpa_num INTEGER,
# # # #                 company_name TEXT,
# # # #                 isomer_fund TEXT,
# # # #                 fund_name TEXT,
# # # #                 clean_fund_name TEXT, 
                
# # # #                 reporting_quarter TEXT,
# # # #                 invest_quarter TEXT,
# # # #                 invest_year INTEGER,
# # # #                 initial_investment_date DATE,
# # # #                 data_as_of_date DATE,
                
# # # #                 status TEXT,
# # # #                 country TEXT,
# # # #                 technology_tag TEXT,
# # # #                 business_model TEXT,
# # # #                 description TEXT,
# # # #                 long_description TEXT,
# # # #                 sdgs TEXT,
# # # #                 female_founders TEXT,
# # # #                 cost_eur REAL,
# # # #                 value_eur REAL,
# # # #                 distributions_eur REAL,
# # # #                 multiple REAL,
                
# # # #                 deal_type TEXT,
# # # #                 is_secondary BOOLEAN,
# # # #                 is_coinvest BOOLEAN,
                
# # # #                 url TEXT,
# # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # #             )
# # # #         """))
        
# # # #         # 5. Raw Data Vault
# # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))

# # # # def save_raw_data(df, source_label):
# # # #     engine = get_engine()
# # # #     column_map = {
# # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # #         'Long Description': 'long_description'
# # # #     }
# # # #     df_to_save = df.rename(columns=column_map)
# # # #     df_to_save['source_file'] = source_label
# # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # def save_quarterly_data(df):
# # # #     engine = get_engine()
# # # #     col_map = {
# # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # #     }
    
# # # #     df = df.rename(columns=col_map)
# # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # #     df = df[valid_cols].copy() 

# # # #     # Clean Dates
# # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # #     for col in date_cols:
# # # #         if col in df.columns:
# # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # #     # --- APPLY CLEAN FUND NAME (ROBUST) ---
# # # #     if 'fund_name' in df.columns:
# # # #         # 1. Force to string to prevent object errors
# # # #         df['fund_name'] = df['fund_name'].astype(str).replace('nan', np.nan)
        
# # # #         # 2. Apply cleaning
# # # #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)
        
# # # #         # 3. FALLBACK: If cleaning returned None/Empty, use the original name
# # # #         df['clean_fund_name'] = df['clean_fund_name'].fillna(df['fund_name'])
        
# # # #         # 4. DEBUG: Print samples to verify it's working
# # # #         print("   🧹 Cleaning Validation (First 3 rows):")
# # # #         sample = df[['fund_name', 'clean_fund_name']].dropna().head(3)
# # # #         for _, row in sample.iterrows():
# # # #             print(f"      '{row['fund_name']}' -> '{row['clean_fund_name']}'")

# # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # import os
# # # # # import re
# # # # # import pandas as pd
# # # # # import numpy as np
# # # # # from sqlalchemy import create_engine, text

# # # # # # Database Path
# # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # def get_engine():
# # # # #     return create_engine(DB_URL)

# # # # # # --- 🛠️ SUPERCHARGED CLEANING FUNCTION ---
# # # # # def clean_fund_name(name):
# # # # #     """
# # # # #     Standardizes fund names by stripping a massive list of legal suffixes.
# # # # #     Handles: "GmbH & Co KG", "Cooperatief U.A.", "SICAV-SIF", "- Units A", etc.
# # # # #     """
# # # # #     if not isinstance(name, str):
# # # # #         return None
    
# # # # #     # 1. Normalize spaces (collapse multiple spaces, convert non-breaking)
# # # # #     name = " ".join(name.split())
    
# # # # #     # 2. Comprehensive Suffix List (Regex)
# # # # #     # ORDER MATTERS: Longest/Specific matches must come before generic ones.
# # # # #     # e.g., "Guernsey LP" must be caught before "LP"
# # # # #     suffixes = [
# # # # #         # Complex / Compound
# # # # #         r'Gmbh\s*&\s*Co\.?\s*KG',          # GmbH & Co KG
# # # # #         r'Gmbh\s*&\s*Co\.?',               # GmbH & Co
# # # # #         r'SICAV[- ]SIF[,\s]*S\.?C\.?S\.?', # SICAV-SIF, SCS (Luxembourg)
# # # # #         r'Co[oö]peratief\s*U\.?A\.?',      # Cooperatief U.A. (Dutch, handles ö)
# # # # #         r'Guernsey\s*L\.?P\.?',            # Guernsey LP
# # # # #         r'Conopus\s*A\.?B\.?',             # Conopus AB (Specific case)
# # # # #         r'-\s*Units\s*A',                  # - Units A (Specific case)

# # # # #         # Standard Acronyms
# # # # #         r'Gmbh', 
# # # # #         r'L\.?\s*P\.?',                    # LP, L.P.
# # # # #         r'L\.?\s*L\.?\s*P\.?',             # LLP
# # # # #         r'S\.?L\.?P\.?',                   # SLP
# # # # #         r'F\.?C\.?R\.?E\.?',               # FCRE
# # # # #         r'F\.?C\.?R\.?',                   # FCR
# # # # #         r'F\.?P\.?C\.?I\.?',               # FPCI (French)
# # # # #         r'S\.?C\.?Sp\.?',                  # SCSp (Luxembourg)
# # # # #         r'S\.?C\.?S\.?',                   # SCS
# # # # #         r'S\.?A\.?',                       # SA
# # # # #         r'S\.?C\.?A\.?',                   # SCA
# # # # #         r'C\.?\s*V\.?',                    # CV
# # # # #         r'K\s*/\s*S',                      # K/S (Nordic)
# # # # #         r'K\.?y\.?',                       # Ky (Finnish)
# # # # #         r'A\.?B\.?',                       # AB (Swedish)
# # # # #         r'B\.?V\.?',                       # BV
# # # # #         r'N\.?V\.?',                       # NV
        
# # # # #         # Corporate Generic
# # # # #         r'Ltd\.?', 
# # # # #         r'Limited', 
# # # # #         r'L\.?L\.?C\.?', 
# # # # #         r'Inc\.?', 
# # # # #         r'Co\.?', 
# # # # #         r'Corp\.?'
# # # # #     ]
    
# # # # #     # Build Regex Pattern
# # # # #     # (?:[,.\s-]+) matches separators: Comma, Dot, Space, OR Hyphen (for " - Units A")
# # # # #     # (?: ... )+$  matches one or more suffixes at the very end
# # # # #     pattern = r'(?:[,.\s-]+)(?:' + '|'.join(suffixes) + r')+$'
    
# # # # #     # Execute Strip (Case Insensitive)
# # # # #     clean = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
# # # # #     # Final cleanup of trailing separators that might remain
# # # # #     # e.g. "Fund I," -> "Fund I"
# # # # #     return clean.strip(' ,.-')

# # # # # # --- RESTORED HELPER FUNCTION ---
# # # # # def load_metadata(table_name):
# # # # #     engine = get_engine()
# # # # #     try:
# # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # #     except Exception as e:
# # # # #         print(f"Error loading {table_name}: {e}")
# # # # #         return pd.DataFrame()

# # # # # def init_db():
# # # # #     engine = get_engine()
# # # # #     with engine.connect() as conn:
        
# # # # #         # 1. Metadata Tables
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # #         # 2. Dimensions
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS managers (organisation TEXT PRIMARY KEY, headquarters TEXT, secondary_offices TEXT, url TEXT)"))
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS isomer_internal_funds (isomer_fund TEXT PRIMARY KEY, currency TEXT, fund_size REAL, vintage_year INTEGER)"))

# # # # #         # 3. External Funds (The Brain)
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # #                 fund_name TEXT PRIMARY KEY,
# # # # #                 clean_fund_name TEXT,  
# # # # #                 isomer_fund TEXT,
# # # # #                 organisation TEXT,
# # # # #                 vintage_year INTEGER,
# # # # #                 isomer_commitment_eur REAL,
# # # # #                 isomer_ic_date DATE,
# # # # #                 lpac_seat BOOLEAN,
# # # # #                 alt_name_1 TEXT,
# # # # #                 alt_name_2 TEXT,
# # # # #                 default_deal_type TEXT 
# # # # #             )
# # # # #         """))

# # # # #         # 4. Cleaned Portfolio Data
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # #                 lpa_num INTEGER,
# # # # #                 company_name TEXT,
# # # # #                 isomer_fund TEXT,
# # # # #                 fund_name TEXT,
# # # # #                 clean_fund_name TEXT, 
                
# # # # #                 reporting_quarter TEXT,
# # # # #                 invest_quarter TEXT,
# # # # #                 invest_year INTEGER,
# # # # #                 initial_investment_date DATE,
# # # # #                 data_as_of_date DATE,
                
# # # # #                 status TEXT,
# # # # #                 country TEXT,
# # # # #                 technology_tag TEXT,
# # # # #                 business_model TEXT,
# # # # #                 description TEXT,
# # # # #                 long_description TEXT,
# # # # #                 sdgs TEXT,
# # # # #                 female_founders TEXT,
# # # # #                 cost_eur REAL,
# # # # #                 value_eur REAL,
# # # # #                 distributions_eur REAL,
# # # # #                 multiple REAL,
                
# # # # #                 deal_type TEXT,
# # # # #                 is_secondary BOOLEAN,
# # # # #                 is_coinvest BOOLEAN,
                
# # # # #                 url TEXT,
# # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # #             )
# # # # #         """))
        
# # # # #         # 5. Raw Data Vault
# # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS raw_portfolio_entries (raw_id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT, upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, lpa_num TEXT, data_as_of_date TEXT, company_name_legal TEXT, company_short_name TEXT, fund_name TEXT, initial_investment_date TEXT, fund_currency TEXT, total_cost_fund_ccy TEXT, current_cost_fund_ccy TEXT, current_value_fund_ccy TEXT, realized_value_fund_ccy TEXT, total_value_fund_ccy TEXT, multiple_fund_ccy TEXT, total_cost_base_ccy TEXT, current_cost_base_ccy TEXT, current_value_base_ccy TEXT, realized_value_base_ccy TEXT, total_value_base_ccy TEXT, multiple_base_ccy TEXT, status TEXT, country TEXT, region_group TEXT, sector TEXT, industry_group TEXT, industry TEXT, industry_detailed TEXT, technology_tag TEXT, business_model TEXT, description TEXT, sdgs TEXT, female_founders TEXT, long_description TEXT)"))

# # # # # def save_raw_data(df, source_label):
# # # # #     engine = get_engine()
# # # # #     column_map = {
# # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # #         'Long Description': 'long_description'
# # # # #     }
# # # # #     df_to_save = df.rename(columns=column_map)
# # # # #     df_to_save['source_file'] = source_label
# # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # def save_quarterly_data(df):
# # # # #     engine = get_engine()
# # # # #     col_map = {
# # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # #     }
    
# # # # #     df = df.rename(columns=col_map)
# # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # #     df = df[valid_cols].copy() 

# # # # #     # Clean Dates
# # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # #     for col in date_cols:
# # # # #         if col in df.columns:
# # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # #     # --- APPLY CLEAN FUND NAME ---
# # # # #     if 'fund_name' in df.columns:
# # # # #         print("   🧹 Cleaning Fund Names (Sample)...")
# # # # #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)

# # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # import os
# # # # # # import re
# # # # # # import pandas as pd
# # # # # # import numpy as np
# # # # # # from sqlalchemy import create_engine, text

# # # # # # # Database Path
# # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # def get_engine():
# # # # # #     return create_engine(DB_URL)

# # # # # # # --- NEW: Name Cleaning Function ---
# # # # # # def clean_fund_name(name):
# # # # # #     """
# # # # # #     Standardizes fund names by stripping legal suffixes.
# # # # # #     Example: "Hoxton Ventures Fund I, L.P." -> "Hoxton Ventures Fund I"
# # # # # #     """
# # # # # #     if not isinstance(name, str):
# # # # # #         return None
    
# # # # # #     # Normalize spaces (remove double spaces)
# # # # # #     name = " ".join(name.split())
    
# # # # # #     # List of legal suffixes to remove
# # # # # #     # (Order matters: longer matches like "Gmbh & Co KG" must be before "KG")
# # # # # #     suffixes = [
# # # # # #         r'Gmbh\s*&\s*Co\.?\s*KG', r'Gmbh\s*&\s*Co\.?', r'Gmbh', 
# # # # # #         r'L\.?P\.?', r'S\.?L\.?P\.?', r'F\.?C\.?R\.?', 
# # # # # #         r'S\.?A\.?', r'S\.?C\.?A\.?', r'C\.?V\.?', 
# # # # # #         r'Ltd\.?', r'Limited', r'L\.?L\.?C\.?', r'Inc\.?', 
# # # # # #         r'Co\.?', r'Corp\.?', r'B\.?V\.?', r'K\.?S\.?', 
# # # # # #         r'S\.?C\.?Sp\.?' # SCSp is common in Lux
# # # # # #     ]
    
# # # # # #     # Regex Pattern:
# # # # # #     # 1. Start with a separator: comma, dot, or space
# # # # # #     # 2. Match one of the suffixes
# # # # # #     # 3. Ensure end of string ($)
# # # # # #     # 4. Repeat (+) to handle cases like "Ltd. Co."
# # # # # #     pattern = r'[,.\s]+(' + '|'.join(suffixes) + r')+$'
    
# # # # # #     # Substitute with empty string and strip trailing punctuation
# # # # # #     clean = re.sub(pattern, '', name, flags=re.IGNORECASE).strip(' ,.')
    
# # # # # #     return clean

# # # # # # # --- RESTORED HELPER FUNCTION ---
# # # # # # def load_metadata(table_name):
# # # # # #     """
# # # # # #     Simple helper to load a table into a Pandas DataFrame.
# # # # # #     Used by Streamlit pages to display/edit metadata.
# # # # # #     """
# # # # # #     engine = get_engine()
# # # # # #     try:
# # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # #     except Exception as e:
# # # # # #         print(f"Error loading {table_name}: {e}")
# # # # # #         return pd.DataFrame()

# # # # # # def init_db():
# # # # # #     engine = get_engine()
# # # # # #     with engine.connect() as conn:
        
# # # # # #         # 1. Metadata Tables
# # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # #         # 2. Dimensions
# # # # # #         conn.execute(text("""
# # # # # #             CREATE TABLE IF NOT EXISTS managers (
# # # # # #                 organisation TEXT PRIMARY KEY,
# # # # # #                 headquarters TEXT,
# # # # # #                 secondary_offices TEXT,
# # # # # #                 url TEXT
# # # # # #             )
# # # # # #         """))

# # # # # #         conn.execute(text("""
# # # # # #             CREATE TABLE IF NOT EXISTS isomer_internal_funds (
# # # # # #                 isomer_fund TEXT PRIMARY KEY,
# # # # # #                 currency TEXT,
# # # # # #                 fund_size REAL,
# # # # # #                 vintage_year INTEGER
# # # # # #             )
# # # # # #         """))

# # # # # #         # 3. External Funds (The Brain)
# # # # # #         # Added 'clean_fund_name'
# # # # # #         conn.execute(text("""
# # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # #                 clean_fund_name TEXT,  -- <--- NEW COLUMN
# # # # # #                 isomer_fund TEXT,
# # # # # #                 organisation TEXT,
# # # # # #                 vintage_year INTEGER,
# # # # # #                 isomer_commitment_eur REAL,
# # # # # #                 isomer_ic_date DATE,
# # # # # #                 lpac_seat BOOLEAN,
# # # # # #                 alt_name_1 TEXT,
# # # # # #                 alt_name_2 TEXT,
# # # # # #                 default_deal_type TEXT 
# # # # # #             )
# # # # # #         """))

# # # # # #         # 4. Cleaned Portfolio Data
# # # # # #         # Added 'clean_fund_name'
# # # # # #         conn.execute(text("""
# # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # #                 lpa_num INTEGER,
# # # # # #                 company_name TEXT,
# # # # # #                 isomer_fund TEXT,
# # # # # #                 fund_name TEXT,
# # # # # #                 clean_fund_name TEXT,  -- <--- NEW COLUMN
                
# # # # # #                 reporting_quarter TEXT,
# # # # # #                 invest_quarter TEXT,
# # # # # #                 invest_year INTEGER,
# # # # # #                 initial_investment_date DATE,
# # # # # #                 data_as_of_date DATE,
                
# # # # # #                 status TEXT,
# # # # # #                 country TEXT,
# # # # # #                 technology_tag TEXT,
# # # # # #                 business_model TEXT,
# # # # # #                 description TEXT,
# # # # # #                 long_description TEXT,
# # # # # #                 sdgs TEXT,
# # # # # #                 female_founders TEXT,
# # # # # #                 cost_eur REAL,
# # # # # #                 value_eur REAL,
# # # # # #                 distributions_eur REAL,
# # # # # #                 multiple REAL,
                
# # # # # #                 deal_type TEXT,
# # # # # #                 is_secondary BOOLEAN,
# # # # # #                 is_coinvest BOOLEAN,
                
# # # # # #                 url TEXT,
# # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # #             )
# # # # # #         """))
        
# # # # # #         # 5. Raw Data Vault
# # # # # #         conn.execute(text("""
# # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # #                 source_file TEXT,
# # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # #                 lpa_num TEXT,
# # # # # #                 data_as_of_date TEXT,
# # # # # #                 company_name_legal TEXT,
# # # # # #                 company_short_name TEXT,
# # # # # #                 fund_name TEXT,
# # # # # #                 initial_investment_date TEXT,
# # # # # #                 fund_currency TEXT,
# # # # # #                 total_cost_fund_ccy TEXT,
# # # # # #                 current_cost_fund_ccy TEXT,
# # # # # #                 current_value_fund_ccy TEXT,
# # # # # #                 realized_value_fund_ccy TEXT,
# # # # # #                 total_value_fund_ccy TEXT,
# # # # # #                 multiple_fund_ccy TEXT,
# # # # # #                 total_cost_base_ccy TEXT,
# # # # # #                 current_cost_base_ccy TEXT,
# # # # # #                 current_value_base_ccy TEXT,
# # # # # #                 realized_value_base_ccy TEXT,
# # # # # #                 total_value_base_ccy TEXT,
# # # # # #                 multiple_base_ccy TEXT,
# # # # # #                 status TEXT,
# # # # # #                 country TEXT,
# # # # # #                 region_group TEXT,
# # # # # #                 sector TEXT,
# # # # # #                 industry_group TEXT,
# # # # # #                 industry TEXT,
# # # # # #                 industry_detailed TEXT,
# # # # # #                 technology_tag TEXT,
# # # # # #                 business_model TEXT,
# # # # # #                 description TEXT,
# # # # # #                 sdgs TEXT,
# # # # # #                 female_founders TEXT,
# # # # # #                 long_description TEXT
# # # # # #             )
# # # # # #         """))

# # # # # # def save_raw_data(df, source_label):
# # # # # #     engine = get_engine()
# # # # # #     column_map = {
# # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # #         'Long Description': 'long_description'
# # # # # #     }
# # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # #     df_to_save['source_file'] = source_label
# # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # def save_quarterly_data(df):
# # # # # #     engine = get_engine()
# # # # # #     col_map = {
# # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # #     }
    
# # # # # #     df = df.rename(columns=col_map)
# # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # #     df = df[valid_cols].copy() 

# # # # # #     # Clean Dates
# # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # #     for col in date_cols:
# # # # # #         if col in df.columns:
# # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # #     # --- APPLY CLEAN FUND NAME ---
# # # # # #     # Automatically strips "LP", "Gmbh & Co KG", etc.
# # # # # #     if 'fund_name' in df.columns:
# # # # # #         df['clean_fund_name'] = df['fund_name'].apply(clean_fund_name)

# # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # import os
# # # # # # # import pandas as pd
# # # # # # # import numpy as np
# # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # Database Path
# # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # def get_engine():
# # # # # # #     return create_engine(DB_URL)

# # # # # # # # --- RESTORED HELPER FUNCTION ---
# # # # # # # def load_metadata(table_name):
# # # # # # #     """
# # # # # # #     Simple helper to load a table into a Pandas DataFrame.
# # # # # # #     Used by Streamlit pages to display/edit metadata.
# # # # # # #     """
# # # # # # #     engine = get_engine()
# # # # # # #     try:
# # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # #     except Exception as e:
# # # # # # #         print(f"Error loading {table_name}: {e}")
# # # # # # #         return pd.DataFrame()

# # # # # # # def init_db():
# # # # # # #     engine = get_engine()
# # # # # # #     with engine.connect() as conn:
        
# # # # # # #         # 1. Metadata Tables
# # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # #         # 2. Dimensions (Managers & Internal Funds)
# # # # # # #         conn.execute(text("""
# # # # # # #             CREATE TABLE IF NOT EXISTS managers (
# # # # # # #                 organisation TEXT PRIMARY KEY,
# # # # # # #                 headquarters TEXT,
# # # # # # #                 secondary_offices TEXT,
# # # # # # #                 url TEXT
# # # # # # #             )
# # # # # # #         """))

# # # # # # #         conn.execute(text("""
# # # # # # #             CREATE TABLE IF NOT EXISTS isomer_internal_funds (
# # # # # # #                 isomer_fund TEXT PRIMARY KEY,
# # # # # # #                 currency TEXT,
# # # # # # #                 fund_size REAL,
# # # # # # #                 vintage_year INTEGER
# # # # # # #             )
# # # # # # #         """))

# # # # # # #         # 3. External Funds (The Brain)
# # # # # # #         conn.execute(text("""
# # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # #                 isomer_fund TEXT,
# # # # # # #                 organisation TEXT,
# # # # # # #                 vintage_year INTEGER,
# # # # # # #                 isomer_commitment_eur REAL,
# # # # # # #                 isomer_ic_date DATE,
# # # # # # #                 lpac_seat BOOLEAN,
# # # # # # #                 alt_name_1 TEXT,
# # # # # # #                 alt_name_2 TEXT,
# # # # # # #                 default_deal_type TEXT 
# # # # # # #             )
# # # # # # #         """))

# # # # # # #         # 4. Cleaned Portfolio Data
# # # # # # #         conn.execute(text("""
# # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # #                 lpa_num INTEGER,
# # # # # # #                 company_name TEXT,
# # # # # # #                 isomer_fund TEXT,
# # # # # # #                 fund_name TEXT,
                
# # # # # # #                 reporting_quarter TEXT,
# # # # # # #                 invest_quarter TEXT,
# # # # # # #                 invest_year INTEGER,
# # # # # # #                 initial_investment_date DATE,
# # # # # # #                 data_as_of_date DATE,
                
# # # # # # #                 status TEXT,
# # # # # # #                 country TEXT,
# # # # # # #                 technology_tag TEXT,
# # # # # # #                 business_model TEXT,
# # # # # # #                 description TEXT,
# # # # # # #                 long_description TEXT,
# # # # # # #                 sdgs TEXT,
# # # # # # #                 female_founders TEXT,
# # # # # # #                 cost_eur REAL,
# # # # # # #                 value_eur REAL,
# # # # # # #                 distributions_eur REAL,
# # # # # # #                 multiple REAL,
                
# # # # # # #                 deal_type TEXT,
# # # # # # #                 is_secondary BOOLEAN,
# # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # #                 url TEXT,
# # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # #             )
# # # # # # #         """))
        
# # # # # # #         # 5. Raw Data Vault
# # # # # # #         conn.execute(text("""
# # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # #                 source_file TEXT,
# # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # #                 lpa_num TEXT,
# # # # # # #                 data_as_of_date TEXT,
# # # # # # #                 company_name_legal TEXT,
# # # # # # #                 company_short_name TEXT,
# # # # # # #                 fund_name TEXT,
# # # # # # #                 initial_investment_date TEXT,
# # # # # # #                 fund_currency TEXT,
# # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # #                 current_value_base_ccy TEXT,
# # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # #                 total_value_base_ccy TEXT,
# # # # # # #                 multiple_base_ccy TEXT,
# # # # # # #                 status TEXT,
# # # # # # #                 country TEXT,
# # # # # # #                 region_group TEXT,
# # # # # # #                 sector TEXT,
# # # # # # #                 industry_group TEXT,
# # # # # # #                 industry TEXT,
# # # # # # #                 industry_detailed TEXT,
# # # # # # #                 technology_tag TEXT,
# # # # # # #                 business_model TEXT,
# # # # # # #                 description TEXT,
# # # # # # #                 sdgs TEXT,
# # # # # # #                 female_founders TEXT,
# # # # # # #                 long_description TEXT
# # # # # # #             )
# # # # # # #         """))

# # # # # # # def save_raw_data(df, source_label):
# # # # # # #     engine = get_engine()
# # # # # # #     column_map = {
# # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # #         'Long Description': 'long_description'
# # # # # # #     }
# # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # #     df_to_save['source_file'] = source_label
# # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # def save_quarterly_data(df):
# # # # # # #     engine = get_engine()
# # # # # # #     col_map = {
# # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # #     }
    
# # # # # # #     df = df.rename(columns=col_map)
# # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # #     df = df[valid_cols].copy() 

# # # # # # #     # Clean Dates (Strip time, keep as DATE object)
# # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # #     for col in date_cols:
# # # # # # #         if col in df.columns:
# # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # import os
# # # # # # # # import pandas as pd
# # # # # # # # import numpy as np
# # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # Database Path
# # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # def get_engine():
# # # # # # # #     return create_engine(DB_URL)

# # # # # # # # def init_db():
# # # # # # # #     engine = get_engine()
# # # # # # # #     with engine.connect() as conn:
        
# # # # # # # #         # 1. Metadata Tables (Standard)
# # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # #         # --- NEW: Manager Dimension ---
# # # # # # # #         conn.execute(text("""
# # # # # # # #             CREATE TABLE IF NOT EXISTS managers (
# # # # # # # #                 organisation TEXT PRIMARY KEY,
# # # # # # # #                 headquarters TEXT,
# # # # # # # #                 secondary_offices TEXT,
# # # # # # # #                 url TEXT
# # # # # # # #             )
# # # # # # # #         """))

# # # # # # # #         # --- Internal Funds Dimension ---
# # # # # # # #         conn.execute(text("""
# # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_internal_funds (
# # # # # # # #                 isomer_fund TEXT PRIMARY KEY,
# # # # # # # #                 currency TEXT,
# # # # # # # #                 fund_size REAL,
# # # # # # # #                 vintage_year INTEGER
# # # # # # # #             )
# # # # # # # #         """))

# # # # # # # #         # --- UPDATED: External Funds (The Brain) ---
# # # # # # # #         # Added 'organisation' so we can join to the managers table
# # # # # # # #         conn.execute(text("""
# # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # #                 isomer_fund TEXT,
# # # # # # # #                 organisation TEXT,  -- <--- NEW LINKING COLUMN
# # # # # # # #                 vintage_year INTEGER,
# # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # #                 isomer_ic_date DATE,
# # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # #                 alt_name_1 TEXT,
# # # # # # # #                 alt_name_2 TEXT,
# # # # # # # #                 default_deal_type TEXT 
# # # # # # # #             )
# # # # # # # #         """))

# # # # # # # #         # 2. Portfolio Data (Fact Table)
# # # # # # # #         conn.execute(text("""
# # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # #                 lpa_num INTEGER,
# # # # # # # #                 company_name TEXT,
# # # # # # # #                 isomer_fund TEXT,
# # # # # # # #                 fund_name TEXT,
                
# # # # # # # #                 reporting_quarter TEXT,
# # # # # # # #                 invest_quarter TEXT,
# # # # # # # #                 invest_year INTEGER,
# # # # # # # #                 initial_investment_date DATE,
# # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # #                 status TEXT,
# # # # # # # #                 country TEXT,
# # # # # # # #                 technology_tag TEXT,
# # # # # # # #                 business_model TEXT,
# # # # # # # #                 description TEXT,
# # # # # # # #                 long_description TEXT,
# # # # # # # #                 sdgs TEXT,
# # # # # # # #                 female_founders TEXT,
# # # # # # # #                 cost_eur REAL,
# # # # # # # #                 value_eur REAL,
# # # # # # # #                 distributions_eur REAL,
# # # # # # # #                 multiple REAL,
                
# # # # # # # #                 deal_type TEXT,
# # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # #                 url TEXT,
# # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # #             )
# # # # # # # #         """))
        
# # # # # # # #         # 3. Raw Data Vault
# # # # # # # #         conn.execute(text("""
# # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # #                 source_file TEXT,
# # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # #                 lpa_num TEXT,
# # # # # # # #                 data_as_of_date TEXT,
# # # # # # # #                 company_name_legal TEXT,
# # # # # # # #                 company_short_name TEXT,
# # # # # # # #                 fund_name TEXT,
# # # # # # # #                 initial_investment_date TEXT,
# # # # # # # #                 fund_currency TEXT,
# # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # #                 status TEXT,
# # # # # # # #                 country TEXT,
# # # # # # # #                 region_group TEXT,
# # # # # # # #                 sector TEXT,
# # # # # # # #                 industry_group TEXT,
# # # # # # # #                 industry TEXT,
# # # # # # # #                 industry_detailed TEXT,
# # # # # # # #                 technology_tag TEXT,
# # # # # # # #                 business_model TEXT,
# # # # # # # #                 description TEXT,
# # # # # # # #                 sdgs TEXT,
# # # # # # # #                 female_founders TEXT,
# # # # # # # #                 long_description TEXT
# # # # # # # #             )
# # # # # # # #         """))

# # # # # # # # def save_raw_data(df, source_label):
# # # # # # # #     engine = get_engine()
# # # # # # # #     column_map = {
# # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # #         'Long Description': 'long_description'
# # # # # # # #     }
# # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # def save_quarterly_data(df):
# # # # # # # #     engine = get_engine()
# # # # # # # #     col_map = {
# # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # #     }
    
# # # # # # # #     df = df.rename(columns=col_map)
# # # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # # #     df = df[valid_cols].copy() 

# # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # #     for col in date_cols:
# # # # # # # #         if col in df.columns:
# # # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # import os
# # # # # # # # # import pandas as pd
# # # # # # # # # import numpy as np
# # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # Database Path
# # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # def get_engine():
# # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # def init_db():
# # # # # # # # #     engine = get_engine()
# # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # #         # 1. Metadata Tables
# # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # #         # --- NEW TABLE: Isomer Internal Funds ---
# # # # # # # # #         conn.execute(text("""
# # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_internal_funds (
# # # # # # # # #                 isomer_fund TEXT PRIMARY KEY,
# # # # # # # # #                 currency TEXT,
# # # # # # # # #                 fund_size REAL,
# # # # # # # # #                 vintage_year INTEGER
# # # # # # # # #             )
# # # # # # # # #         """))
# # # # # # # # #         # ----------------------------------------

# # # # # # # # #         # TABLE: isomer_funds (The Brain - Portfolio Assets)
# # # # # # # # #         conn.execute(text("""
# # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # #             )
# # # # # # # # #         """))

# # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # #         conn.execute(text("""
# # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # #                 company_name TEXT,
# # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # #                 invest_year INTEGER,
# # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # #                 status TEXT,
# # # # # # # # #                 country TEXT,
# # # # # # # # #                 technology_tag TEXT,
# # # # # # # # #                 business_model TEXT,
# # # # # # # # #                 description TEXT,
# # # # # # # # #                 long_description TEXT,
# # # # # # # # #                 sdgs TEXT,
# # # # # # # # #                 female_founders TEXT,
# # # # # # # # #                 cost_eur REAL,
# # # # # # # # #                 value_eur REAL,
# # # # # # # # #                 distributions_eur REAL,
# # # # # # # # #                 multiple REAL,
                
# # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # #                 deal_type TEXT,
# # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # #                 url TEXT,
# # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # #             )
# # # # # # # # #         """))
        
# # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # #         conn.execute(text("""
# # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # #                 source_file TEXT,
# # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # #                 lpa_num TEXT,
# # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # #                 company_short_name TEXT,
# # # # # # # # #                 fund_name TEXT,
# # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # #                 fund_currency TEXT,
# # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # #                 status TEXT,
# # # # # # # # #                 country TEXT,
# # # # # # # # #                 region_group TEXT,
# # # # # # # # #                 sector TEXT,
# # # # # # # # #                 industry_group TEXT,
# # # # # # # # #                 industry TEXT,
# # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # #                 technology_tag TEXT,
# # # # # # # # #                 business_model TEXT,
# # # # # # # # #                 description TEXT,
# # # # # # # # #                 sdgs TEXT,
# # # # # # # # #                 female_founders TEXT,
# # # # # # # # #                 long_description TEXT
# # # # # # # # #             )
# # # # # # # # #         """))

# # # # # # # # # # ... (Rest of the file helper functions remain exactly the same) ...
# # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # #     engine = get_engine()
# # # # # # # # #     # (Existing mapping logic...)
# # # # # # # # #     column_map = {
# # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # #     }
# # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # def _clean_year(val):
# # # # # # # # #     if pd.isna(val) or str(val).lower() == 'nan':
# # # # # # # # #         return None
# # # # # # # # #     return str(val).split('.')[0].strip()

# # # # # # # # # def _make_qy(row):
# # # # # # # # #     quarter = row.get('invest_quarter')
# # # # # # # # #     year = row.get('_clean_year')
# # # # # # # # #     if pd.isna(quarter) or pd.isna(year):
# # # # # # # # #         return None
# # # # # # # # #     return f"{quarter} {year}"

# # # # # # # # # def save_quarterly_data(df):
# # # # # # # # #     engine = get_engine()
# # # # # # # # #     col_map = {
# # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # #     }
    
# # # # # # # # #     df = df.rename(columns=col_map)
# # # # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # # # #     df = df[valid_cols].copy() 

# # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # #     for col in date_cols:
# # # # # # # # #         if col in df.columns:
# # # # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # #     # Save
# # # # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # import os
# # # # # # # # # # import pandas as pd
# # # # # # # # # # import numpy as np
# # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # Database Path
# # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # def get_engine():
# # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # def init_db():
# # # # # # # # # #     engine = get_engine()
# # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # #         conn.execute(text("""
# # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # #             )
# # # # # # # # # #         """))

# # # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # # #         # REVERTED: Removed 'initial_investment_date_qy'
# # # # # # # # # #         conn.execute(text("""
# # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # #                 company_name TEXT,
# # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # #                 status TEXT,
# # # # # # # # # #                 country TEXT,
# # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # #                 business_model TEXT,
# # # # # # # # # #                 description TEXT,
# # # # # # # # # #                 long_description TEXT,
# # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # #                 value_eur REAL,
# # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # #                 url TEXT,
# # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # #             )
# # # # # # # # # #         """))
        
# # # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # # #         conn.execute(text("""
# # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # #                 source_file TEXT,
# # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # #                 status TEXT,
# # # # # # # # # #                 country TEXT,
# # # # # # # # # #                 region_group TEXT,
# # # # # # # # # #                 sector TEXT,
# # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # #                 industry TEXT,
# # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # #                 business_model TEXT,
# # # # # # # # # #                 description TEXT,
# # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # #                 long_description TEXT
# # # # # # # # # #             )
# # # # # # # # # #         """))

# # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # #     engine = get_engine()
# # # # # # # # # #     column_map = {
# # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # #     }
# # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # #     engine = get_engine()
# # # # # # # # # #     col_map = {
# # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # #     }
    
# # # # # # # # # #     # 1. Rename columns
# # # # # # # # # #     df = df.rename(columns=col_map)
    
# # # # # # # # # #     # 2. Keep only valid columns
# # # # # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # # # # #     df = df[valid_cols].copy() 

# # # # # # # # # #     # 3. Clean Dates (revert to DATE objects for database, strip time)
# # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # #     for col in date_cols:
# # # # # # # # # #         if col in df.columns:
# # # # # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # #     # 4. Save
# # # # # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # import os
# # # # # # # # # # # import pandas as pd
# # # # # # # # # # # import numpy as np
# # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # Database Path
# # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # def get_engine():
# # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # def init_db():
# # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # #             )
# # # # # # # # # # #         """))

# # # # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # #                 initial_investment_date_qy TEXT,
# # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # #                 status TEXT,
# # # # # # # # # # #                 country TEXT,
# # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # #                 description TEXT,
# # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # #                 url TEXT,
# # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # #             )
# # # # # # # # # # #         """))
        
# # # # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # #                 status TEXT,
# # # # # # # # # # #                 country TEXT,
# # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # #                 description TEXT,
# # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # #             )
# # # # # # # # # # #         """))

# # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # #     column_map = {
# # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # #     }
# # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # --- HELPER FUNCTIONS ---
# # # # # # # # # # # def _clean_year(val):
# # # # # # # # # # #     """
# # # # # # # # # # #     Normalise the Invest Year column:
# # # # # # # # # # #     - NaNs / None → None
# # # # # # # # # # #     - Floats like 2014.0 → "2014"
# # # # # # # # # # #     - Anything else → stripped string
# # # # # # # # # # #     """
# # # # # # # # # # #     if pd.isna(val) or str(val).lower() == 'nan':
# # # # # # # # # # #         return None
# # # # # # # # # # #     # Force to string, drop any decimal part
# # # # # # # # # # #     return str(val).split('.')[0].strip()

# # # # # # # # # # # def _make_qy(row):
# # # # # # # # # # #     """
# # # # # # # # # # #     Build the "Q2 2014" string.
# # # # # # # # # # #     Returns None if either quarter or year is missing.
# # # # # # # # # # #     """
# # # # # # # # # # #     quarter = row.get('invest_quarter')
# # # # # # # # # # #     year = row.get('_clean_year')
# # # # # # # # # # #     if pd.isna(quarter) or pd.isna(year):
# # # # # # # # # # #         return None
# # # # # # # # # # #     return f"{quarter} {year}"

# # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # #     col_map = {
# # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # #     }
    
# # # # # # # # # # #     # 1. Rename columns
# # # # # # # # # # #     df = df.rename(columns=col_map)
    
# # # # # # # # # # #     # 2. Keep only valid columns
# # # # # # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # # # # # #     df = df[valid_cols].copy() 

# # # # # # # # # # #     # 3. Clean Dates (revert to DATE objects for database)
# # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # #         if col in df.columns:
# # # # # # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # #     # 4. Build "Q2 2014" Logic using helper functions
# # # # # # # # # # #     if 'invest_year' in df.columns:
# # # # # # # # # # #         df['_clean_year'] = df['invest_year'].apply(_clean_year)

# # # # # # # # # # #     if {'invest_quarter', '_clean_year'}.issubset(df.columns):
# # # # # # # # # # #         df['initial_investment_date_qy'] = df.apply(_make_qy, axis=1)
# # # # # # # # # # #         df.drop(columns=['_clean_year'], inplace=True)

# # # # # # # # # # #     # 5. Save
# # # # # # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # import os
# # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # import numpy as np
# # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # Database Path
# # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # def get_engine():
# # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # def init_db():
# # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # # #             )
# # # # # # # # # # # #         """))

# # # # # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # #                 initial_investment_date_qy TEXT,
# # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # #             )
# # # # # # # # # # # #         """))
        
# # # # # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # #             )
# # # # # # # # # # # #         """))

# # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # #     column_map = {
# # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # #     }
# # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # --- HELPER FUNCTIONS ---
# # # # # # # # # # # # def _clean_year(val):
# # # # # # # # # # # #     """
# # # # # # # # # # # #     Turn whatever comes in for `invest_year` into a plain string year.
# # # # # # # # # # # #     - Handles floats like 2014.0 → "2014"
# # # # # # # # # # # #     - Returns None for NaN / None / empty strings
# # # # # # # # # # # #     """
# # # # # # # # # # # #     if pd.isna(val) or str(val).lower() == 'nan':
# # # # # # # # # # # #         return None
# # # # # # # # # # # #     # Cast to string, split on '.' to drop any decimal part
# # # # # # # # # # # #     return str(val).split('.')[0]

# # # # # # # # # # # # def _make_qy(row):
# # # # # # # # # # # #     """
# # # # # # # # # # # #     Row-wise helper that builds "Q2 2014" only when both parts exist.
# # # # # # # # # # # #     """
# # # # # # # # # # # #     quarter = row.get('invest_quarter')
# # # # # # # # # # # #     year = row.get('_clean_year')   # This column is injected below
    
# # # # # # # # # # # #     if pd.isna(quarter) or pd.isna(year):
# # # # # # # # # # # #         return None
# # # # # # # # # # # #     return f"{quarter} {year}"

# # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # #     col_map = {
# # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # #     }
    
# # # # # # # # # # # #     # 1. Rename columns
# # # # # # # # # # # #     df = df.rename(columns=col_map)
    
# # # # # # # # # # # #     # 2. Keep only valid columns
# # # # # # # # # # # #     valid_cols = [v for v in col_map.values() if v in df.columns]
# # # # # # # # # # # #     df = df[valid_cols].copy() 

# # # # # # # # # # # #     # 3. Clean Dates (revert to DATE objects for database)
# # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # #         if col in df.columns:
# # # # # # # # # # # #             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
# # # # # # # # # # # #             df[col] = df[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # # #     # 4. Build "Q2 2014" Logic
# # # # # # # # # # # #     if 'invest_year' in df.columns:
# # # # # # # # # # # #         df['_clean_year'] = df['invest_year'].apply(_clean_year)

# # # # # # # # # # # #     if {'invest_quarter', '_clean_year'}.issubset(df.columns):
# # # # # # # # # # # #         df['initial_investment_date_qy'] = df.apply(_make_qy, axis=1)
# # # # # # # # # # # #         df.drop(columns=['_clean_year'], inplace=True)

# # # # # # # # # # # #     # 5. Save
# # # # # # # # # # # #     df.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # import os
# # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # import numpy as np
# # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # # # #             )
# # # # # # # # # # # # #         """))

# # # # # # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # #                 initial_investment_date_qy TEXT,
# # # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # #             )
# # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # #             )
# # # # # # # # # # # # #         """))

# # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # #     }
# # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # #     }
    
# # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # #     # --- DATE CLEANING ---
# # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date
# # # # # # # # # # # # #             df_to_save[col] = df_to_save[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # # # #     # --- 🛠️ ROBUST QY CREATION (Force Integer String) ---
# # # # # # # # # # # # #     if 'invest_quarter' in df_to_save.columns and 'invest_year' in df_to_save.columns:
        
# # # # # # # # # # # # #         def clean_year_val(val):
# # # # # # # # # # # # #             # 1. Handle NaNs/None
# # # # # # # # # # # # #             if pd.isna(val) or str(val).lower() == 'nan':
# # # # # # # # # # # # #                 return None
# # # # # # # # # # # # #             # 2. Force to string
# # # # # # # # # # # # #             s = str(val)
# # # # # # # # # # # # #             # 3. Split on decimal and take the left part ("2014.0" -> "2014")
# # # # # # # # # # # # #             return s.split('.')[0]

# # # # # # # # # # # # #         # Apply helper to the whole column
# # # # # # # # # # # # #         clean_years = df_to_save['invest_year'].apply(clean_year_val)
        
# # # # # # # # # # # # #         # Combine: "Q2" + " " + "2014"
# # # # # # # # # # # # #         df_to_save['initial_investment_date_qy'] = df_to_save['invest_quarter'].astype(str) + " " + clean_years.astype(str)
        
# # # # # # # # # # # # #         # Cleanup "nan" artifacts (e.g. "Q1 None" or "nan 2014")
# # # # # # # # # # # # #         mask_bad = df_to_save['initial_investment_date_qy'].str.contains('nan|None', case=False)
# # # # # # # # # # # # #         df_to_save.loc[mask_bad, 'initial_investment_date_qy'] = None
# # # # # # # # # # # # #     # ----------------------------------

# # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # import numpy as np
# # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # #                 isomer_ic_date DATE,
# # # # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # # # # #             )
# # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data
# # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # #                 initial_investment_date_qy TEXT,  -- <--- NEW COLUMN
# # # # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # #             )
# # # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # # #         # 3. Raw Data Vault
# # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # #             )
# # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # # #     # --- DATE CLEANING ---
# # # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date
# # # # # # # # # # # # # #             df_to_save[col] = df_to_save[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # # # # #     # --- 🛠️ SIMPLE QY CREATION (String Force) ---
# # # # # # # # # # # # # #     if 'invest_quarter' in df_to_save.columns and 'invest_year' in df_to_save.columns:
# # # # # # # # # # # # # #         # 1. Force Year to String, remove decimals
# # # # # # # # # # # # # #         # "2014.0" -> "2014", "nan" -> "nan"
# # # # # # # # # # # # # #         str_year = df_to_save['invest_year'].astype(str).str.split('.').str[0]
        
# # # # # # # # # # # # # #         # 2. Force Quarter to String
# # # # # # # # # # # # # #         str_quarter = df_to_save['invest_quarter'].astype(str)
        
# # # # # # # # # # # # # #         # 3. Concatenate
# # # # # # # # # # # # # #         df_to_save['initial_investment_date_qy'] = str_quarter + " " + str_year
        
# # # # # # # # # # # # # #         # 4. Clean up "nan" artifacts (e.g. "nan 2014" or "Q1 nan")
# # # # # # # # # # # # # #         mask_invalid = df_to_save['initial_investment_date_qy'].str.contains('nan|None', case=False)
# # # # # # # # # # # # # #         df_to_save.loc[mask_invalid, 'initial_investment_date_qy'] = None
# # # # # # # # # # # # # #     # ----------------------------------

# # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # # # #     # --- DATE CLEANING ---
# # # # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date
# # # # # # # # # # # # # # #             df_to_save[col] = df_to_save[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # # # # # #     # --- 🛠️ SIMPLIFIED QY CREATION ---
# # # # # # # # # # # # # # #     if 'invest_quarter' in df_to_save.columns and 'invest_year' in df_to_save.columns:
# # # # # # # # # # # # # # #         # 1. Clean Year: Convert to numeric, handle NaN, convert to Int, then String
# # # # # # # # # # # # # # #         # casting to 'Int64' (nullable int) handles NaN gracefully before string conversion
# # # # # # # # # # # # # # #         clean_year = pd.to_numeric(df_to_save['invest_year'], errors='coerce').astype('Int64').astype(str)
        
# # # # # # # # # # # # # # #         # 2. Vectorized Concat: "Qx" + " " + "20xx"
# # # # # # # # # # # # # # #         # We use .replace('<NA>', np.nan) because nullable Int64 produces '<NA>' string
# # # # # # # # # # # # # # #         clean_year = clean_year.replace('<NA>', np.nan)
        
# # # # # # # # # # # # # # #         df_to_save['initial_investment_date_qy'] = (
# # # # # # # # # # # # # # #             df_to_save['invest_quarter'].astype(str) + " " + clean_year
# # # # # # # # # # # # # # #         )
        
# # # # # # # # # # # # # # #         # 3. Cleanup: If either part was NaN, the result will look like "nan 2014" or "Q1 nan"
# # # # # # # # # # # # # # #         # We wipe those out to be safe.
# # # # # # # # # # # # # # #         mask_bad = df_to_save['initial_investment_date_qy'].str.contains('nan', case=False)
# # # # # # # # # # # # # # #         df_to_save.loc[mask_bad, 'initial_investment_date_qy'] = None
# # # # # # # # # # # # # # #     # ----------------------------------

# # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # # # #     # --- DATE CLEANING (Reverts to DATE object) ---
# # # # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date
# # # # # # # # # # # # # # #             df_to_save[col] = df_to_save[col].replace({pd.NaT: None, np.nan: None})

# # # # # # # # # # # # # # #     # --- 🛠️ NEW: Combine Q + Y (Cleaned) ---
# # # # # # # # # # # # # # #     if 'invest_quarter' in df_to_save.columns and 'invest_year' in df_to_save.columns:
# # # # # # # # # # # # # # #         # 1. Force year to numeric first (handles strings like '2014.0')
# # # # # # # # # # # # # # #         df_to_save['invest_year'] = pd.to_numeric(df_to_save['invest_year'], errors='coerce')
        
# # # # # # # # # # # # # # #         def format_qy(row):
# # # # # # # # # # # # # # #             q = row['invest_quarter']
# # # # # # # # # # # # # # #             y = row['invest_year']
            
# # # # # # # # # # # # # # #             # If either is missing, we can't make a QY string
# # # # # # # # # # # # # # #             if pd.isna(q) or pd.isna(y):
# # # # # # # # # # # # # # #                 return None
            
# # # # # # # # # # # # # # #             # Convert float year (2014.0) -> int (2014) -> str ("2014")
# # # # # # # # # # # # # # #             try:
# # # # # # # # # # # # # # #                 y_str = str(int(y)) 
# # # # # # # # # # # # # # #                 return f"{q} {y_str}"
# # # # # # # # # # # # # # #             except:
# # # # # # # # # # # # # # #                 return None

# # # # # # # # # # # # # # #         df_to_save['initial_investment_date_qy'] = df_to_save.apply(format_qy, axis=1)
# # # # # # # # # # # # # # #     # ----------------------------------------

# # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data (The Result)
# # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # # # #         # 3. Raw Data Vault (Bronze Table)
# # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # # # #     # --- 🛠️ FIX: Strip Time from Dates ---
# # # # # # # # # # # # # # #     # This forces the column to be just "YYYY-MM-DD"
# # # # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date
# # # # # # # # # # # # # # #     # --------------------------------------

# # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # # # #         # TABLE: isomer_funds (The Brain)
# # # # # # # # # # # # # # # #         # Stores the default deal type for each fund entity
# # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # # # # # #                 alt_name_2 TEXT,
# # # # # # # # # # # # # # # #                 default_deal_type TEXT 
# # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data (The Result)
# # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # #                 multiple REAL,
                
# # # # # # # # # # # # # # # #                 -- GRANULARITY FLAGS
# # # # # # # # # # # # # # # #                 deal_type TEXT,
# # # # # # # # # # # # # # # #                 is_secondary BOOLEAN,
# # # # # # # # # # # # # # # #                 is_coinvest BOOLEAN,
                
# # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # # # # #         # 3. Raw Data Vault (Bronze Table) - standard schema
# # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # #     # Simplified standard map
# # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url',
# # # # # # # # # # # # # # # #         'Deal Type': 'deal_type', 'Is Secondary': 'is_secondary', 'Is CoInvest': 'is_coinvest'
# # # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]

# # # # # # # # # # # # # # # #     # This forces the column to be just "YYYY-MM-DD"
# # # # # # # # # # # # # # # #     date_cols = ['initial_investment_date', 'data_as_of_date']
# # # # # # # # # # # # # # # #     for col in date_cols:
# # # # # # # # # # # # # # # #         if col in df_to_save.columns:
# # # # # # # # # # # # # # # #             df_to_save[col] = pd.to_datetime(df_to_save[col], errors='coerce').dt.date

# # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # # #     """Initializes the database with all necessary tables."""
# # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # # # # #         # UPDATED TABLE: Added alt_name_1 and alt_name_2
# # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN,
# # # # # # # # # # # # # # # # #                 alt_name_1 TEXT,
# # # # # # # # # # # # # # # # #                 alt_name_2 TEXT
# # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data (Gold Table)
# # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # # #                 initial_investment_date DATE,
# # # # # # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # # #                 multiple REAL,
# # # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # #         # 3. Raw Data Vault (Bronze Table)
# # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num', 'Data as of Date': 'data_as_of_date', 'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name', 'Fund Name': 'fund_name', 'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency', 'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy', 'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy', 'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy', 'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy', 'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy', 'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy', 'Company Status': 'status', 'Country': 'country',
# # # # # # # # # # # # # # # # #         'Region Group': 'region_group', 'LP Analyst - Sector': 'sector', 'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry', 'LP Analyst - Industry (Detailed)': 'industry_detailed', 'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # #         'Business Model': 'business_model', 'Description': 'description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # # # # # #     valid_cols = list(column_map.values()) + ['source_file']
# # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num', 'Company Name': 'company_name', 'Isomer Fund': 'isomer_fund', 'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter', 'Invest Quarter': 'invest_quarter', 'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', 'Data as of Date': 'data_as_of_date', 'Status': 'status',
# # # # # # # # # # # # # # # # #         'Country': 'country', 'Technology Tag': 'technology_tag', 'Business Model': 'business_model',
# # # # # # # # # # # # # # # # #         'Description': 'description', 'Long Description': 'long_description', 'SDGs': 'sdgs', 'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur', "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url'
# # # # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
# # # # # # # # # # # # # # # # #     valid_cols = list(col_map.values())
# # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
# # # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # # # #     """Initializes the database with all necessary tables."""
# # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN
# # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data (Gold Table)
# # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # # # #                 invest_quarter TEXT,
# # # # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # # # #                 initial_investment_date DATE,  -- <--- ADDED THIS
# # # # # # # # # # # # # # # # # #                 data_as_of_date DATE,
                
# # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # # # #                 multiple REAL,
# # # # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # #         # 3. Raw Data Vault (Bronze Table)
# # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num',
# # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date',
# # # # # # # # # # # # # # # # # #         'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name',
# # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency',
# # # # # # # # # # # # # # # # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # #         'Company Status': 'status',
# # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # #         'Region Group': 'region_group',
# # # # # # # # # # # # # # # # # #         'LP Analyst - Sector': 'sector',
# # # # # # # # # # # # # # # # # #         'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry',
# # # # # # # # # # # # # # # # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
# # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # # # #     }
# # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
# # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # # # # # # # # # # # # # # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # # # # # # # # # # # # # # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # # # # # # # # # # # # # # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # # # # # # # # # # # # # # # #         'sdgs', 'female_founders', 'long_description'
# # # # # # # # # # # # # # # # # #     ]
# # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # # # #     """Saves cleaned data to portfolio_entries."""
# # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num',
# # # # # # # # # # # # # # # # # #         'Company Name': 'company_name',
# # # # # # # # # # # # # # # # # #         'Isomer Fund': 'isomer_fund',
# # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # #         'Reporting Quarter': 'reporting_quarter',
# # # # # # # # # # # # # # # # # #         'Invest Quarter': 'invest_quarter',
# # # # # # # # # # # # # # # # # #         'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date', # <--- MAPPED HERE
# # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date',
# # # # # # # # # # # # # # # # # #         'Status': 'status',
# # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # #         'Long Description': 'long_description',
# # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # # # # # # # # # # # # # # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur',
# # # # # # # # # # # # # # # # # #         'Multiple': 'multiple',
# # # # # # # # # # # # # # # # # #         'URL': 'url'
# # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
    
# # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 
# # # # # # # # # # # # # # # # # #         'reporting_quarter', 'invest_quarter', 'invest_year', 
# # # # # # # # # # # # # # # # # #         'initial_investment_date', 'data_as_of_date', # <--- ADDED HERE
# # # # # # # # # # # # # # # # # #         'status', 'country', 'technology_tag', 'business_model', 
# # # # # # # # # # # # # # # # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # # # # # # # # # # # # # # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # # # # #     """Initializes the database with all necessary tables."""
# # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # # # # #         # 1. Metadata Tables
# # # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # # # # # # # # # # # # # # # # # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN
# # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # #         # 2. Cleaned Portfolio Data (Gold Table) - ADDED data_as_of_date
# # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # # # # #                 data_as_of_date DATE,  -- <--- NEW COLUMN
# # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # # # # #                 multiple REAL,
# # # # # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # #         # 3. Raw Data Vault (Bronze Table)
# # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # # # # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # # # # #                 fund_currency TEXT,
# # # # # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # #                 region_group TEXT,
# # # # # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # # # # #                 industry_detailed TEXT,
# # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # # # # #     """Saves raw data to raw_portfolio_entries."""
# # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num',
# # # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date',
# # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name',
# # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency',
# # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # # #         'Company Status': 'status',
# # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # #         'Region Group': 'region_group',
# # # # # # # # # # # # # # # # # # #         'LP Analyst - Sector': 'sector',
# # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry',
# # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
# # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
# # # # # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
    
# # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # # # # # # # # # # # # # # # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # # # # # # # # # # # # # # # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # # # # # # # # # # # # # # # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # # # # # # # # # # # # # # # # #         'sdgs', 'female_founders', 'long_description'
# # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols].astype(str)
# # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # # # # #     """Saves cleaned data to portfolio_entries."""
# # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # #     # Updated Map with 'Data as of Date'
# # # # # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num',
# # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name',
# # # # # # # # # # # # # # # # # # #         'Isomer Fund': 'isomer_fund',
# # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # #         'Invest Quarter': 'reporting_quarter',
# # # # # # # # # # # # # # # # # # #         'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date', # <--- MAPPED HERE
# # # # # # # # # # # # # # # # # # #         'Status': 'status',
# # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description',
# # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # # # # # # # # # # # # # # # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur',
# # # # # # # # # # # # # # # # # # #         'Multiple': 'multiple',
# # # # # # # # # # # # # # # # # # #         'URL': 'url'
# # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
    
# # # # # # # # # # # # # # # # # # #     # Updated Valid Columns
# # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # # # # # # # # # # # # # # # # # #         'invest_year', 'data_as_of_date', 'status', 'country', 'technology_tag', 'business_model', 
# # # # # # # # # # # # # # # # # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # # # # # # # # # # # # # # # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # # # # # #     """Initializes the database with all necessary tables, including the comprehensive Raw Vault."""
# # # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # # # # # #         # 1. Metadata: URLs
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_urls (
# # # # # # # # # # # # # # # # # # # #                 lpa_num INTEGER PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # #                 url TEXT
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # #         # 2. Metadata: Name Mappings
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_name_changes (
# # # # # # # # # # # # # # # # # # # #                 original_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # #                 new_name TEXT
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # #         # 3. Metadata: Tech Tags
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_tech_tags (
# # # # # # # # # # # # # # # # # # # #                 original_tag TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # #                 cleaned_tag TEXT
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # #         # 4. Metadata: Fund Commitments
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # # # # # # # # #         # 5. Metadata: Fund Name Map (Messy -> Clean)
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_fund_names (
# # # # # # # # # # # # # # # # # # # #                 original_fund TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # #                 cleaned_fund TEXT
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # #         # 6. Cleaned Portfolio Data (The "Gold" Table)
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # # # # # #                 multiple REAL,
# # # # # # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # #         # 7. Raw Data Vault (The "Bronze" Table)
# # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
# # # # # # # # # # # # # # # # # # # #                 -- Identifiers
# # # # # # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Dates & Currency
# # # # # # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # # # # # #                 fund_currency TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Financials (Fund Currency)
# # # # # # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Financials (Base Currency - EUR)
# # # # # # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Categorization
# # # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # # #                 region_group TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Sector & Industry
# # # # # # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # # # # # #                 industry_detailed TEXT,
                
# # # # # # # # # # # # # # # # # # # #                 -- Tags & Descriptions
# # # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # # # # # #     """Helper to load a metadata table into a pandas DataFrame."""
# # # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # #     Saves raw, uncleaned data to the raw_portfolio_entries table.
# # # # # # # # # # # # # # # # # # # #     Maps columns from the exact CSV structure provided.
# # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # # #     # Complete Mapping based on sample_data.csv
# # # # # # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num',
# # # # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date',
# # # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name',
# # # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency',
        
# # # # # # # # # # # # # # # # # # # #         # Fund Currency Metrics
# # # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
        
# # # # # # # # # # # # # # # # # # # #         # Base Currency Metrics
# # # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
        
# # # # # # # # # # # # # # # # # # # #         # Categorization
# # # # # # # # # # # # # # # # # # # #         'Company Status': 'status',
# # # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # # #         'Region Group': 'region_group',
        
# # # # # # # # # # # # # # # # # # # #         # Industry
# # # # # # # # # # # # # # # # # # # #         'LP Analyst - Sector': 'sector',
# # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry',
# # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
        
# # # # # # # # # # # # # # # # # # # #         # Qualitative
# # # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # # #     # 1. Rename columns
# # # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
    
# # # # # # # # # # # # # # # # # # # #     # 2. Add Source Metadata
# # # # # # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
    
# # # # # # # # # # # # # # # # # # # #     # 3. Filter to only keep columns that exist in our DB table
# # # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # # # # # # # # # # # # # # # # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # # # # # # # # # # # # # # # # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # # # # # # # # # # # # # # # # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # # # # # # # # # # # # # # # # # #         'sdgs', 'female_founders', 'long_description'
# # # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # # #     # Keep only valid cols
# # # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # # # #     # 4. Convert to String for Safety
# # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save.astype(str)
    
# # # # # # # # # # # # # # # # # # # #     # 5. Append to DB
# # # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # #     Saves the cleaned quarterly data to the main portfolio_entries table.
# # # # # # # # # # # # # # # # # # # #     Maps the 'Cleaned' column names to the 'Database' column names.
# # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # # #     # Map DataFrame columns (from cleaning.py) to Database columns (snake_case)
# # # # # # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num',
# # # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name',
# # # # # # # # # # # # # # # # # # # #         'Isomer Fund': 'isomer_fund',
# # # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # # #         'Invest Quarter': 'reporting_quarter',
# # # # # # # # # # # # # # # # # # # #         'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # # # # # #         'Status': 'status',
# # # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description',
# # # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # # # # # # # # # # # # # # # # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur',
# # # # # # # # # # # # # # # # # # # #         'Multiple': 'multiple',
# # # # # # # # # # # # # # # # # # # #         'URL': 'url'
# # # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # # #     # Rename columns
# # # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
    
# # # # # # # # # # # # # # # # # # # #     # Select only the columns that exist in our DB table
# # # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # # # # # # # # # # # # # # # # # # #         'invest_year', 'status', 'country', 'technology_tag', 'business_model', 
# # # # # # # # # # # # # # # # # # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # # # # # # # # # # # # # # # # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # # # #     # Append to the "Gold" table
# # # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # # # import os
# # # # # # # # # # # # # # # # # # # # # import pandas as pd
# # # # # # # # # # # # # # # # # # # # # from sqlalchemy import create_engine, text

# # # # # # # # # # # # # # # # # # # # # # Database Path
# # # # # # # # # # # # # # # # # # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # # # # # # # # # # # # # # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # # # # # # # # # # # # # # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # # # # # # # # # # # # # # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # # # # # # # # # # # # # # # # # def get_engine():
# # # # # # # # # # # # # # # # # # # # #     return create_engine(DB_URL)

# # # # # # # # # # # # # # # # # # # # # def init_db():
# # # # # # # # # # # # # # # # # # # # #     """Initializes the database with all necessary tables, including the comprehensive Raw Vault."""
# # # # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # # # #     with engine.connect() as conn:
        
# # # # # # # # # # # # # # # # # # # # #         # 1. Metadata: URLs
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_urls (
# # # # # # # # # # # # # # # # # # # # #                 lpa_num INTEGER PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # # #                 url TEXT
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # #         # 2. Metadata: Name Mappings
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_name_changes (
# # # # # # # # # # # # # # # # # # # # #                 original_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # # #                 new_name TEXT
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # #         # 3. Metadata: Tech Tags
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_tech_tags (
# # # # # # # # # # # # # # # # # # # # #                 original_tag TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # # #                 cleaned_tag TEXT
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # #         # 4. Metadata: Fund Commitments
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # # # # # # # # # # # # # # # # # #                 fund_name TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # # # #                 vintage_year INTEGER,
# # # # # # # # # # # # # # # # # # # # #                 isomer_commitment_eur REAL,
# # # # # # # # # # # # # # # # # # # # #                 isomer_ic_date TEXT,
# # # # # # # # # # # # # # # # # # # # #                 lpac_seat BOOLEAN
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))
        
# # # # # # # # # # # # # # # # # # # # #         # 5. Metadata: Fund Name Map (Messy -> Clean)
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS meta_fund_names (
# # # # # # # # # # # # # # # # # # # # #                 original_fund TEXT PRIMARY KEY,
# # # # # # # # # # # # # # # # # # # # #                 cleaned_fund TEXT
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # #         # 6. Cleaned Portfolio Data (The "Gold" Table)
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # # # # # # # # # # # # # # # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # # # #                 lpa_num INTEGER,
# # # # # # # # # # # # # # # # # # # # #                 company_name TEXT,
# # # # # # # # # # # # # # # # # # # # #                 isomer_fund TEXT,
# # # # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
# # # # # # # # # # # # # # # # # # # # #                 reporting_quarter TEXT,
# # # # # # # # # # # # # # # # # # # # #                 invest_year INTEGER,
# # # # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # # # #                 long_description TEXT,
# # # # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # # # #                 cost_eur REAL,
# # # # # # # # # # # # # # # # # # # # #                 value_eur REAL,
# # # # # # # # # # # # # # # # # # # # #                 distributions_eur REAL,
# # # # # # # # # # # # # # # # # # # # #                 multiple REAL,
# # # # # # # # # # # # # # # # # # # # #                 url TEXT,
# # # # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # #         # 7. Raw Data Vault (The "Bronze" Table) - UPDATED TO MATCH YOUR CSV
# # # # # # # # # # # # # # # # # # # # #         # We use TEXT for almost everything to ensure valid storage of any input format
# # # # # # # # # # # # # # # # # # # # #         conn.execute(text("""
# # # # # # # # # # # # # # # # # # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # # # # # # # # # # # # # # # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # # # # # # # # # # # # # # # # # #                 source_file TEXT,
# # # # # # # # # # # # # # # # # # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Identifiers
# # # # # # # # # # # # # # # # # # # # #                 lpa_num TEXT,
# # # # # # # # # # # # # # # # # # # # #                 data_as_of_date TEXT,
# # # # # # # # # # # # # # # # # # # # #                 company_name_legal TEXT,
# # # # # # # # # # # # # # # # # # # # #                 company_short_name TEXT,
# # # # # # # # # # # # # # # # # # # # #                 fund_name TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Dates & Currency
# # # # # # # # # # # # # # # # # # # # #                 initial_investment_date TEXT,
# # # # # # # # # # # # # # # # # # # # #                 fund_currency TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Financials (Fund Currency)
# # # # # # # # # # # # # # # # # # # # #                 total_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 current_cost_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 current_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 realized_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 total_value_fund_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 multiple_fund_ccy TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Financials (Base Currency - EUR)
# # # # # # # # # # # # # # # # # # # # #                 total_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 current_cost_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 current_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 realized_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 total_value_base_ccy TEXT,
# # # # # # # # # # # # # # # # # # # # #                 multiple_base_ccy TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Categorization
# # # # # # # # # # # # # # # # # # # # #                 status TEXT,
# # # # # # # # # # # # # # # # # # # # #                 country TEXT,
# # # # # # # # # # # # # # # # # # # # #                 region_group TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Sector & Industry
# # # # # # # # # # # # # # # # # # # # #                 sector TEXT,
# # # # # # # # # # # # # # # # # # # # #                 industry_group TEXT,
# # # # # # # # # # # # # # # # # # # # #                 industry TEXT,
# # # # # # # # # # # # # # # # # # # # #                 industry_detailed TEXT,
                
# # # # # # # # # # # # # # # # # # # # #                 -- Tags & Descriptions
# # # # # # # # # # # # # # # # # # # # #                 technology_tag TEXT,
# # # # # # # # # # # # # # # # # # # # #                 business_model TEXT,
# # # # # # # # # # # # # # # # # # # # #                 description TEXT,
# # # # # # # # # # # # # # # # # # # # #                 sdgs TEXT,
# # # # # # # # # # # # # # # # # # # # #                 female_founders TEXT,
# # # # # # # # # # # # # # # # # # # # #                 long_description TEXT
# # # # # # # # # # # # # # # # # # # # #             )
# # # # # # # # # # # # # # # # # # # # #         """))

# # # # # # # # # # # # # # # # # # # # # def load_metadata(table_name):
# # # # # # # # # # # # # # # # # # # # #     """Helper to load a metadata table into a pandas DataFrame."""
# # # # # # # # # # # # # # # # # # # # #     engine = get_engine()
# # # # # # # # # # # # # # # # # # # # #     try:
# # # # # # # # # # # # # # # # # # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # # # # # # # # # # # # # # # # # #     except Exception:
# # # # # # # # # # # # # # # # # # # # #         return pd.DataFrame()

# # # # # # # # # # # # # # # # # # # # # def save_raw_data(df, source_label):
# # # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # # #     Saves raw, uncleaned data to the raw_portfolio_entries table.
# # # # # # # # # # # # # # # # # # # # #     Maps columns from the exact CSV structure you provided.
# # # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # # # #     # Complete Mapping based on your sample_data.csv
# # # # # # # # # # # # # # # # # # # # #     column_map = {
# # # # # # # # # # # # # # # # # # # # #         'LP Analyst Identifier': 'lpa_num',
# # # # # # # # # # # # # # # # # # # # #         'Data as of Date': 'data_as_of_date',
# # # # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name_legal',
# # # # # # # # # # # # # # # # # # # # #         'Company Short Name': 'company_short_name',
# # # # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # # # #         'Initial Investment Date': 'initial_investment_date',
# # # # # # # # # # # # # # # # # # # # #         'Fund Currency': 'fund_currency',
        
# # # # # # # # # # # # # # # # # # # # #         # Fund Currency Metrics
# # # # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
        
# # # # # # # # # # # # # # # # # # # # #         # Base Currency Metrics
# # # # # # # # # # # # # # # # # # # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
        
# # # # # # # # # # # # # # # # # # # # #         # Categorization
# # # # # # # # # # # # # # # # # # # # #         'Company Status': 'status',
# # # # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # # # #         'Region Group': 'region_group',
        
# # # # # # # # # # # # # # # # # # # # #         # Industry
# # # # # # # # # # # # # # # # # # # # #         'LP Analyst - Sector': 'sector',
# # # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry Group': 'industry_group',
# # # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry': 'industry',
# # # # # # # # # # # # # # # # # # # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
        
# # # # # # # # # # # # # # # # # # # # #         # Qualitative
# # # # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description'
# # # # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # # # #     # 1. Rename columns
# # # # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=column_map)
    
# # # # # # # # # # # # # # # # # # # # #     # 2. Add Source Metadata
# # # # # # # # # # # # # # # # # # # # #     df_to_save['source_file'] = source_label
    
# # # # # # # # # # # # # # # # # # # # #     # 3. Filter to only keep columns that exist in our DB table
# # # # # # # # # # # # # # # # # # # # #     # This prevents errors if the source CSV has extra random columns
# # # # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # # # # # # # # # # # # # # # # # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # # # # # # # # # # # # # # # # # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # # # # # # # # # # # # # # # # # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # # # # # # # # # # # # # # # # # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # # # # # # # # # # # # # # # # # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # # # # # # # # # # # # # # # # # # #         'sdgs', 'female_founders', 'long_description'
# # # # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # # # #     # Keep only valid cols that exist in the dataframe
# # # # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # # # # #     # 4. Convert to String for Safety
# # # # # # # # # # # # # # # # # # # # #     # We store everything as TEXT in the raw vault so we never lose data due to type errors
# # # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save.astype(str)
    
# # # # # # # # # # # # # # # # # # # # #     # 5. Append to DB
# # # # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # # # # # # # # # # # # # # # # # def save_quarterly_data(df):
# # # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # # #     Saves the cleaned quarterly data to the main portfolio_entries table.
# # # # # # # # # # # # # # # # # # # # #     Maps the 'Cleaned' column names to the 'Database' column names.
# # # # # # # # # # # # # # # # # # # # #     """
# # # # # # # # # # # # # # # # # # # # #     engine = get_engine()
    
# # # # # # # # # # # # # # # # # # # # #     # Map DataFrame columns (from cleaning.py) to Database columns (snake_case)
# # # # # # # # # # # # # # # # # # # # #     col_map = {
# # # # # # # # # # # # # # # # # # # # #         'LPA Num': 'lpa_num',
# # # # # # # # # # # # # # # # # # # # #         'Company Name': 'company_name',
# # # # # # # # # # # # # # # # # # # # #         'Isomer Fund': 'isomer_fund',
# # # # # # # # # # # # # # # # # # # # #         'Fund Name': 'fund_name',
# # # # # # # # # # # # # # # # # # # # #         'Invest Quarter': 'reporting_quarter',
# # # # # # # # # # # # # # # # # # # # #         'Invest Year': 'invest_year',
# # # # # # # # # # # # # # # # # # # # #         'Status': 'status',
# # # # # # # # # # # # # # # # # # # # #         'Country': 'country',
# # # # # # # # # # # # # # # # # # # # #         'Technology Tag': 'technology_tag',
# # # # # # # # # # # # # # # # # # # # #         'Business Model': 'business_model',
# # # # # # # # # # # # # # # # # # # # #         'Description': 'description',
# # # # # # # # # # # # # # # # # # # # #         'Long Description': 'long_description',
# # # # # # # # # # # # # # # # # # # # #         'SDGs': 'sdgs',
# # # # # # # # # # # # # # # # # # # # #         'Female Founders': 'female_founders',
# # # # # # # # # # # # # # # # # # # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # # # # # # # # # # # # # # # # # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # # # # # # # # # # # # # # # # # # #         "Distributions EUR": 'distributions_eur',
# # # # # # # # # # # # # # # # # # # # #         'Multiple': 'multiple',
# # # # # # # # # # # # # # # # # # # # #         'URL': 'url'
# # # # # # # # # # # # # # # # # # # # #     }
    
# # # # # # # # # # # # # # # # # # # # #     # Rename columns
# # # # # # # # # # # # # # # # # # # # #     df_to_save = df.rename(columns=col_map)
    
# # # # # # # # # # # # # # # # # # # # #     # Select only the columns that exist in our DB table
# # # # # # # # # # # # # # # # # # # # #     # (This prevents errors if the cleaned DF has extra temp columns)
# # # # # # # # # # # # # # # # # # # # #     valid_cols = [
# # # # # # # # # # # # # # # # # # # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # # # # # # # # # # # # # # # # # # # #         'invest_year', 'status', 'country', 'technology_tag', 'business_model', 
# # # # # # # # # # # # # # # # # # # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # # # # # # # # # # # # # # # # # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # # # # # # # # # # # # # # # # # # #     ]
    
# # # # # # # # # # # # # # # # # # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # # # # # # # # # # # # # # # # # #     df_to_save = df_to_save[final_cols]
    
# # # # # # # # # # # # # # # # # # # # #     # Append to the "Gold" table
# # # # # # # # # # # # # # # # # # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)