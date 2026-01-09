import os
import pandas as pd
from sqlalchemy import create_engine, text

# Database Path
DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
os.makedirs(DB_FOLDER, exist_ok=True)
DB_URL = f"sqlite:///{DB_FILE}"

def get_engine():
    return create_engine(DB_URL)

def init_db():
    engine = get_engine()
    with engine.connect() as conn:
        
        # 1. Metadata Tables
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
        # TABLE: isomer_funds (The Brain)
        # Stores the default deal type for each fund entity
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS isomer_funds (
                fund_name TEXT PRIMARY KEY,
                isomer_fund TEXT,
                vintage_year INTEGER,
                isomer_commitment_eur REAL,
                isomer_ic_date TEXT,
                lpac_seat BOOLEAN,
                alt_name_1 TEXT,
                alt_name_2 TEXT,
                default_deal_type TEXT 
            )
        """))

        # 2. Cleaned Portfolio Data (The Result)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lpa_num INTEGER,
                company_name TEXT,
                isomer_fund TEXT,
                fund_name TEXT,
                
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
                
                -- GRANULARITY FLAGS
                deal_type TEXT,
                is_secondary BOOLEAN,
                is_coinvest BOOLEAN,
                
                url TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # 3. Raw Data Vault (Bronze Table) - standard schema
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
                raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                lpa_num TEXT,
                data_as_of_date TEXT,
                company_name_legal TEXT,
                company_short_name TEXT,
                fund_name TEXT,
                initial_investment_date TEXT,
                fund_currency TEXT,
                total_cost_fund_ccy TEXT,
                current_cost_fund_ccy TEXT,
                current_value_fund_ccy TEXT,
                realized_value_fund_ccy TEXT,
                total_value_fund_ccy TEXT,
                multiple_fund_ccy TEXT,
                total_cost_base_ccy TEXT,
                current_cost_base_ccy TEXT,
                current_value_base_ccy TEXT,
                realized_value_base_ccy TEXT,
                total_value_base_ccy TEXT,
                multiple_base_ccy TEXT,
                status TEXT,
                country TEXT,
                region_group TEXT,
                sector TEXT,
                industry_group TEXT,
                industry TEXT,
                industry_detailed TEXT,
                technology_tag TEXT,
                business_model TEXT,
                description TEXT,
                sdgs TEXT,
                female_founders TEXT,
                long_description TEXT
            )
        """))

def save_raw_data(df, source_label):
    engine = get_engine()
    # Simplified standard map
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

def load_metadata(table_name):
    engine = get_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception:
        return pd.DataFrame()

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
    df_to_save = df.rename(columns=col_map)
    valid_cols = list(col_map.values())
    final_cols = [c for c in valid_cols if c in df_to_save.columns]
    df_to_save = df_to_save[final_cols]
    df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# import os
# import pandas as pd
# from sqlalchemy import create_engine, text

# # Database Path
# DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# os.makedirs(DB_FOLDER, exist_ok=True)
# DB_URL = f"sqlite:///{DB_FILE}"

# def get_engine():
#     return create_engine(DB_URL)

# def init_db():
#     """Initializes the database with all necessary tables."""
#     engine = get_engine()
#     with engine.connect() as conn:
        
#         # 1. Metadata Tables
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
#         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
#         # UPDATED TABLE: Added alt_name_1 and alt_name_2
#         conn.execute(text("""
#             CREATE TABLE IF NOT EXISTS isomer_funds (
#                 fund_name TEXT PRIMARY KEY,
#                 isomer_fund TEXT,
#                 vintage_year INTEGER,
#                 isomer_commitment_eur REAL,
#                 isomer_ic_date TEXT,
#                 lpac_seat BOOLEAN,
#                 alt_name_1 TEXT,
#                 alt_name_2 TEXT
#             )
#         """))

#         # 2. Cleaned Portfolio Data (Gold Table)
#         conn.execute(text("""
#             CREATE TABLE IF NOT EXISTS portfolio_entries (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 lpa_num INTEGER,
#                 company_name TEXT,
#                 isomer_fund TEXT,
#                 fund_name TEXT,
                
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
#                 url TEXT,
#                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#             )
#         """))

#         # 3. Raw Data Vault (Bronze Table)
#         conn.execute(text("""
#             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
#                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 source_file TEXT,
#                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
#                 lpa_num TEXT,
#                 data_as_of_date TEXT,
#                 company_name_legal TEXT,
#                 company_short_name TEXT,
#                 fund_name TEXT,
#                 initial_investment_date TEXT,
#                 fund_currency TEXT,
#                 total_cost_fund_ccy TEXT,
#                 current_cost_fund_ccy TEXT,
#                 current_value_fund_ccy TEXT,
#                 realized_value_fund_ccy TEXT,
#                 total_value_fund_ccy TEXT,
#                 multiple_fund_ccy TEXT,
#                 total_cost_base_ccy TEXT,
#                 current_cost_base_ccy TEXT,
#                 current_value_base_ccy TEXT,
#                 realized_value_base_ccy TEXT,
#                 total_value_base_ccy TEXT,
#                 multiple_base_ccy TEXT,
#                 status TEXT,
#                 country TEXT,
#                 region_group TEXT,
#                 sector TEXT,
#                 industry_group TEXT,
#                 industry TEXT,
#                 industry_detailed TEXT,
#                 technology_tag TEXT,
#                 business_model TEXT,
#                 description TEXT,
#                 sdgs TEXT,
#                 female_founders TEXT,
#                 long_description TEXT
#             )
#         """))

# def load_metadata(table_name):
#     engine = get_engine()
#     try:
#         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
#     except Exception:
#         return pd.DataFrame()

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
#         "Distributions EUR": 'distributions_eur', 'Multiple': 'multiple', 'URL': 'url'
#     }
#     df_to_save = df.rename(columns=col_map)
#     valid_cols = list(col_map.values())
#     final_cols = [c for c in valid_cols if c in df_to_save.columns]
#     df_to_save = df_to_save[final_cols]
#     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # import os
# # import pandas as pd
# # from sqlalchemy import create_engine, text

# # # Database Path
# # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # os.makedirs(DB_FOLDER, exist_ok=True)
# # DB_URL = f"sqlite:///{DB_FILE}"

# # def get_engine():
# #     return create_engine(DB_URL)

# # def init_db():
# #     """Initializes the database with all necessary tables."""
# #     engine = get_engine()
# #     with engine.connect() as conn:
        
# #         # 1. Metadata Tables
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# #         conn.execute(text("""
# #             CREATE TABLE IF NOT EXISTS isomer_funds (
# #                 fund_name TEXT PRIMARY KEY,
# #                 isomer_fund TEXT,
# #                 vintage_year INTEGER,
# #                 isomer_commitment_eur REAL,
# #                 isomer_ic_date TEXT,
# #                 lpac_seat BOOLEAN
# #             )
# #         """))

# #         # 2. Cleaned Portfolio Data (Gold Table)
# #         conn.execute(text("""
# #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# #                 lpa_num INTEGER,
# #                 company_name TEXT,
# #                 isomer_fund TEXT,
# #                 fund_name TEXT,
                
# #                 reporting_quarter TEXT,
# #                 invest_quarter TEXT,
# #                 invest_year INTEGER,
# #                 initial_investment_date DATE,  -- <--- ADDED THIS
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
# #                 url TEXT,
# #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# #             )
# #         """))

# #         # 3. Raw Data Vault (Bronze Table)
# #         conn.execute(text("""
# #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# #                 source_file TEXT,
# #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# #                 lpa_num TEXT,
# #                 data_as_of_date TEXT,
# #                 company_name_legal TEXT,
# #                 company_short_name TEXT,
# #                 fund_name TEXT,
# #                 initial_investment_date TEXT,
# #                 fund_currency TEXT,
# #                 total_cost_fund_ccy TEXT,
# #                 current_cost_fund_ccy TEXT,
# #                 current_value_fund_ccy TEXT,
# #                 realized_value_fund_ccy TEXT,
# #                 total_value_fund_ccy TEXT,
# #                 multiple_fund_ccy TEXT,
# #                 total_cost_base_ccy TEXT,
# #                 current_cost_base_ccy TEXT,
# #                 current_value_base_ccy TEXT,
# #                 realized_value_base_ccy TEXT,
# #                 total_value_base_ccy TEXT,
# #                 multiple_base_ccy TEXT,
# #                 status TEXT,
# #                 country TEXT,
# #                 region_group TEXT,
# #                 sector TEXT,
# #                 industry_group TEXT,
# #                 industry TEXT,
# #                 industry_detailed TEXT,
# #                 technology_tag TEXT,
# #                 business_model TEXT,
# #                 description TEXT,
# #                 sdgs TEXT,
# #                 female_founders TEXT,
# #                 long_description TEXT
# #             )
# #         """))

# # def load_metadata(table_name):
# #     engine = get_engine()
# #     try:
# #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# #     except Exception:
# #         return pd.DataFrame()

# # def save_raw_data(df, source_label):
# #     engine = get_engine()
# #     column_map = {
# #         'LP Analyst Identifier': 'lpa_num',
# #         'Data as of Date': 'data_as_of_date',
# #         'Company Name': 'company_name_legal',
# #         'Company Short Name': 'company_short_name',
# #         'Fund Name': 'fund_name',
# #         'Initial Investment Date': 'initial_investment_date',
# #         'Fund Currency': 'fund_currency',
# #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
# #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
# #         'Company Status': 'status',
# #         'Country': 'country',
# #         'Region Group': 'region_group',
# #         'LP Analyst - Sector': 'sector',
# #         'LP Analyst - Industry Group': 'industry_group',
# #         'LP Analyst - Industry': 'industry',
# #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
# #         'Technology Tag': 'technology_tag',
# #         'Business Model': 'business_model',
# #         'Description': 'description',
# #         'SDGs': 'sdgs',
# #         'Female Founders': 'female_founders',
# #         'Long Description': 'long_description'
# #     }
# #     df_to_save = df.rename(columns=column_map)
# #     df_to_save['source_file'] = source_label
# #     valid_cols = [
# #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# #         'fund_name', 'initial_investment_date', 'fund_currency',
# #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# #         'sdgs', 'female_founders', 'long_description'
# #     ]
# #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# #     df_to_save = df_to_save[final_cols].astype(str)
# #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # def save_quarterly_data(df):
# #     """Saves cleaned data to portfolio_entries."""
# #     engine = get_engine()
    
# #     col_map = {
# #         'LPA Num': 'lpa_num',
# #         'Company Name': 'company_name',
# #         'Isomer Fund': 'isomer_fund',
# #         'Fund Name': 'fund_name',
# #         'Reporting Quarter': 'reporting_quarter',
# #         'Invest Quarter': 'invest_quarter',
# #         'Invest Year': 'invest_year',
# #         'Initial Investment Date': 'initial_investment_date', # <--- MAPPED HERE
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
    
# #     df_to_save = df.rename(columns=col_map)
    
# #     valid_cols = [
# #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 
# #         'reporting_quarter', 'invest_quarter', 'invest_year', 
# #         'initial_investment_date', 'data_as_of_date', # <--- ADDED HERE
# #         'status', 'country', 'technology_tag', 'business_model', 
# #         'description', 'long_description', 'sdgs', 'female_founders', 
# #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# #     ]
    
# #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# #     df_to_save = df_to_save[final_cols]
    
# #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # import os
# # # import pandas as pd
# # # from sqlalchemy import create_engine, text

# # # # Database Path
# # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # DB_URL = f"sqlite:///{DB_FILE}"

# # # def get_engine():
# # #     return create_engine(DB_URL)

# # # def init_db():
# # #     """Initializes the database with all necessary tables."""
# # #     engine = get_engine()
# # #     with engine.connect() as conn:
        
# # #         # 1. Metadata Tables
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT PRIMARY KEY, new_name TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT PRIMARY KEY, cleaned_tag TEXT)"))
# # #         conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT PRIMARY KEY, cleaned_fund TEXT)"))
        
# # #         conn.execute(text("""
# # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # #                 fund_name TEXT PRIMARY KEY,
# # #                 isomer_fund TEXT,
# # #                 vintage_year INTEGER,
# # #                 isomer_commitment_eur REAL,
# # #                 isomer_ic_date TEXT,
# # #                 lpac_seat BOOLEAN
# # #             )
# # #         """))

# # #         # 2. Cleaned Portfolio Data (Gold Table) - ADDED data_as_of_date
# # #         conn.execute(text("""
# # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # #                 lpa_num INTEGER,
# # #                 company_name TEXT,
# # #                 isomer_fund TEXT,
# # #                 fund_name TEXT,
# # #                 reporting_quarter TEXT,
# # #                 invest_year INTEGER,
# # #                 data_as_of_date DATE,  -- <--- NEW COLUMN
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
# # #                 url TEXT,
# # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # #             )
# # #         """))

# # #         # 3. Raw Data Vault (Bronze Table)
# # #         conn.execute(text("""
# # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # #                 source_file TEXT,
# # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
# # #                 lpa_num TEXT,
# # #                 data_as_of_date TEXT,
# # #                 company_name_legal TEXT,
# # #                 company_short_name TEXT,
# # #                 fund_name TEXT,
# # #                 initial_investment_date TEXT,
# # #                 fund_currency TEXT,
# # #                 total_cost_fund_ccy TEXT,
# # #                 current_cost_fund_ccy TEXT,
# # #                 current_value_fund_ccy TEXT,
# # #                 realized_value_fund_ccy TEXT,
# # #                 total_value_fund_ccy TEXT,
# # #                 multiple_fund_ccy TEXT,
# # #                 total_cost_base_ccy TEXT,
# # #                 current_cost_base_ccy TEXT,
# # #                 current_value_base_ccy TEXT,
# # #                 realized_value_base_ccy TEXT,
# # #                 total_value_base_ccy TEXT,
# # #                 multiple_base_ccy TEXT,
# # #                 status TEXT,
# # #                 country TEXT,
# # #                 region_group TEXT,
# # #                 sector TEXT,
# # #                 industry_group TEXT,
# # #                 industry TEXT,
# # #                 industry_detailed TEXT,
# # #                 technology_tag TEXT,
# # #                 business_model TEXT,
# # #                 description TEXT,
# # #                 sdgs TEXT,
# # #                 female_founders TEXT,
# # #                 long_description TEXT
# # #             )
# # #         """))

# # # def load_metadata(table_name):
# # #     engine = get_engine()
# # #     try:
# # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # #     except Exception:
# # #         return pd.DataFrame()

# # # def save_raw_data(df, source_label):
# # #     """Saves raw data to raw_portfolio_entries."""
# # #     engine = get_engine()
    
# # #     column_map = {
# # #         'LP Analyst Identifier': 'lpa_num',
# # #         'Data as of Date': 'data_as_of_date',
# # #         'Company Name': 'company_name_legal',
# # #         'Company Short Name': 'company_short_name',
# # #         'Fund Name': 'fund_name',
# # #         'Initial Investment Date': 'initial_investment_date',
# # #         'Fund Currency': 'fund_currency',
# # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
# # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
# # #         'Company Status': 'status',
# # #         'Country': 'country',
# # #         'Region Group': 'region_group',
# # #         'LP Analyst - Sector': 'sector',
# # #         'LP Analyst - Industry Group': 'industry_group',
# # #         'LP Analyst - Industry': 'industry',
# # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
# # #         'Technology Tag': 'technology_tag',
# # #         'Business Model': 'business_model',
# # #         'Description': 'description',
# # #         'SDGs': 'sdgs',
# # #         'Female Founders': 'female_founders',
# # #         'Long Description': 'long_description'
# # #     }
    
# # #     df_to_save = df.rename(columns=column_map)
# # #     df_to_save['source_file'] = source_label
    
# # #     valid_cols = [
# # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # #         'sdgs', 'female_founders', 'long_description'
# # #     ]
    
# # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # #     df_to_save = df_to_save[final_cols].astype(str)
# # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # def save_quarterly_data(df):
# # #     """Saves cleaned data to portfolio_entries."""
# # #     engine = get_engine()
    
# # #     # Updated Map with 'Data as of Date'
# # #     col_map = {
# # #         'LPA Num': 'lpa_num',
# # #         'Company Name': 'company_name',
# # #         'Isomer Fund': 'isomer_fund',
# # #         'Fund Name': 'fund_name',
# # #         'Invest Quarter': 'reporting_quarter',
# # #         'Invest Year': 'invest_year',
# # #         'Data as of Date': 'data_as_of_date', # <--- MAPPED HERE
# # #         'Status': 'status',
# # #         'Country': 'country',
# # #         'Technology Tag': 'technology_tag',
# # #         'Business Model': 'business_model',
# # #         'Description': 'description',
# # #         'Long Description': 'long_description',
# # #         'SDGs': 'sdgs',
# # #         'Female Founders': 'female_founders',
# # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # #         "Distributions EUR": 'distributions_eur',
# # #         'Multiple': 'multiple',
# # #         'URL': 'url'
# # #     }
    
# # #     df_to_save = df.rename(columns=col_map)
    
# # #     # Updated Valid Columns
# # #     valid_cols = [
# # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # #         'invest_year', 'data_as_of_date', 'status', 'country', 'technology_tag', 'business_model', 
# # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # #     ]
    
# # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # #     df_to_save = df_to_save[final_cols]
    
# # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # import os
# # # # import pandas as pd
# # # # from sqlalchemy import create_engine, text

# # # # # Database Path
# # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # def get_engine():
# # # #     return create_engine(DB_URL)

# # # # def init_db():
# # # #     """Initializes the database with all necessary tables, including the comprehensive Raw Vault."""
# # # #     engine = get_engine()
# # # #     with engine.connect() as conn:
        
# # # #         # 1. Metadata: URLs
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS meta_urls (
# # # #                 lpa_num INTEGER PRIMARY KEY,
# # # #                 url TEXT
# # # #             )
# # # #         """))

# # # #         # 2. Metadata: Name Mappings
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS meta_name_changes (
# # # #                 original_name TEXT PRIMARY KEY,
# # # #                 new_name TEXT
# # # #             )
# # # #         """))

# # # #         # 3. Metadata: Tech Tags
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS meta_tech_tags (
# # # #                 original_tag TEXT PRIMARY KEY,
# # # #                 cleaned_tag TEXT
# # # #             )
# # # #         """))

# # # #         # 4. Metadata: Fund Commitments
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # #                 fund_name TEXT PRIMARY KEY,
# # # #                 isomer_fund TEXT,
# # # #                 vintage_year INTEGER,
# # # #                 isomer_commitment_eur REAL,
# # # #                 isomer_ic_date TEXT,
# # # #                 lpac_seat BOOLEAN
# # # #             )
# # # #         """))
        
# # # #         # 5. Metadata: Fund Name Map (Messy -> Clean)
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS meta_fund_names (
# # # #                 original_fund TEXT PRIMARY KEY,
# # # #                 cleaned_fund TEXT
# # # #             )
# # # #         """))

# # # #         # 6. Cleaned Portfolio Data (The "Gold" Table)
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # #                 lpa_num INTEGER,
# # # #                 company_name TEXT,
# # # #                 isomer_fund TEXT,
# # # #                 fund_name TEXT,
# # # #                 reporting_quarter TEXT,
# # # #                 invest_year INTEGER,
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
# # # #                 url TEXT,
# # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # #             )
# # # #         """))

# # # #         # 7. Raw Data Vault (The "Bronze" Table)
# # # #         conn.execute(text("""
# # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # #                 source_file TEXT,
# # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
# # # #                 -- Identifiers
# # # #                 lpa_num TEXT,
# # # #                 data_as_of_date TEXT,
# # # #                 company_name_legal TEXT,
# # # #                 company_short_name TEXT,
# # # #                 fund_name TEXT,
                
# # # #                 -- Dates & Currency
# # # #                 initial_investment_date TEXT,
# # # #                 fund_currency TEXT,
                
# # # #                 -- Financials (Fund Currency)
# # # #                 total_cost_fund_ccy TEXT,
# # # #                 current_cost_fund_ccy TEXT,
# # # #                 current_value_fund_ccy TEXT,
# # # #                 realized_value_fund_ccy TEXT,
# # # #                 total_value_fund_ccy TEXT,
# # # #                 multiple_fund_ccy TEXT,
                
# # # #                 -- Financials (Base Currency - EUR)
# # # #                 total_cost_base_ccy TEXT,
# # # #                 current_cost_base_ccy TEXT,
# # # #                 current_value_base_ccy TEXT,
# # # #                 realized_value_base_ccy TEXT,
# # # #                 total_value_base_ccy TEXT,
# # # #                 multiple_base_ccy TEXT,
                
# # # #                 -- Categorization
# # # #                 status TEXT,
# # # #                 country TEXT,
# # # #                 region_group TEXT,
                
# # # #                 -- Sector & Industry
# # # #                 sector TEXT,
# # # #                 industry_group TEXT,
# # # #                 industry TEXT,
# # # #                 industry_detailed TEXT,
                
# # # #                 -- Tags & Descriptions
# # # #                 technology_tag TEXT,
# # # #                 business_model TEXT,
# # # #                 description TEXT,
# # # #                 sdgs TEXT,
# # # #                 female_founders TEXT,
# # # #                 long_description TEXT
# # # #             )
# # # #         """))

# # # # def load_metadata(table_name):
# # # #     """Helper to load a metadata table into a pandas DataFrame."""
# # # #     engine = get_engine()
# # # #     try:
# # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # #     except Exception:
# # # #         return pd.DataFrame()

# # # # def save_raw_data(df, source_label):
# # # #     """
# # # #     Saves raw, uncleaned data to the raw_portfolio_entries table.
# # # #     Maps columns from the exact CSV structure provided.
# # # #     """
# # # #     engine = get_engine()
    
# # # #     # Complete Mapping based on sample_data.csv
# # # #     column_map = {
# # # #         'LP Analyst Identifier': 'lpa_num',
# # # #         'Data as of Date': 'data_as_of_date',
# # # #         'Company Name': 'company_name_legal',
# # # #         'Company Short Name': 'company_short_name',
# # # #         'Fund Name': 'fund_name',
# # # #         'Initial Investment Date': 'initial_investment_date',
# # # #         'Fund Currency': 'fund_currency',
        
# # # #         # Fund Currency Metrics
# # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
        
# # # #         # Base Currency Metrics
# # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
        
# # # #         # Categorization
# # # #         'Company Status': 'status',
# # # #         'Country': 'country',
# # # #         'Region Group': 'region_group',
        
# # # #         # Industry
# # # #         'LP Analyst - Sector': 'sector',
# # # #         'LP Analyst - Industry Group': 'industry_group',
# # # #         'LP Analyst - Industry': 'industry',
# # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
        
# # # #         # Qualitative
# # # #         'Technology Tag': 'technology_tag',
# # # #         'Business Model': 'business_model',
# # # #         'Description': 'description',
# # # #         'SDGs': 'sdgs',
# # # #         'Female Founders': 'female_founders',
# # # #         'Long Description': 'long_description'
# # # #     }
    
# # # #     # 1. Rename columns
# # # #     df_to_save = df.rename(columns=column_map)
    
# # # #     # 2. Add Source Metadata
# # # #     df_to_save['source_file'] = source_label
    
# # # #     # 3. Filter to only keep columns that exist in our DB table
# # # #     valid_cols = [
# # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # #         'sdgs', 'female_founders', 'long_description'
# # # #     ]
    
# # # #     # Keep only valid cols
# # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # #     df_to_save = df_to_save[final_cols]
    
# # # #     # 4. Convert to String for Safety
# # # #     df_to_save = df_to_save.astype(str)
    
# # # #     # 5. Append to DB
# # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # def save_quarterly_data(df):
# # # #     """
# # # #     Saves the cleaned quarterly data to the main portfolio_entries table.
# # # #     Maps the 'Cleaned' column names to the 'Database' column names.
# # # #     """
# # # #     engine = get_engine()
    
# # # #     # Map DataFrame columns (from cleaning.py) to Database columns (snake_case)
# # # #     col_map = {
# # # #         'LPA Num': 'lpa_num',
# # # #         'Company Name': 'company_name',
# # # #         'Isomer Fund': 'isomer_fund',
# # # #         'Fund Name': 'fund_name',
# # # #         'Invest Quarter': 'reporting_quarter',
# # # #         'Invest Year': 'invest_year',
# # # #         'Status': 'status',
# # # #         'Country': 'country',
# # # #         'Technology Tag': 'technology_tag',
# # # #         'Business Model': 'business_model',
# # # #         'Description': 'description',
# # # #         'Long Description': 'long_description',
# # # #         'SDGs': 'sdgs',
# # # #         'Female Founders': 'female_founders',
# # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # #         "Distributions EUR": 'distributions_eur',
# # # #         'Multiple': 'multiple',
# # # #         'URL': 'url'
# # # #     }
    
# # # #     # Rename columns
# # # #     df_to_save = df.rename(columns=col_map)
    
# # # #     # Select only the columns that exist in our DB table
# # # #     valid_cols = [
# # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # # #         'invest_year', 'status', 'country', 'technology_tag', 'business_model', 
# # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # #     ]
    
# # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # #     df_to_save = df_to_save[final_cols]
    
# # # #     # Append to the "Gold" table
# # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)

# # # # # import os
# # # # # import pandas as pd
# # # # # from sqlalchemy import create_engine, text

# # # # # # Database Path
# # # # # DB_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')
# # # # # DB_FILE = os.path.join(DB_FOLDER, 'isomer_central_repo.db')
# # # # # os.makedirs(DB_FOLDER, exist_ok=True)
# # # # # DB_URL = f"sqlite:///{DB_FILE}"

# # # # # def get_engine():
# # # # #     return create_engine(DB_URL)

# # # # # def init_db():
# # # # #     """Initializes the database with all necessary tables, including the comprehensive Raw Vault."""
# # # # #     engine = get_engine()
# # # # #     with engine.connect() as conn:
        
# # # # #         # 1. Metadata: URLs
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS meta_urls (
# # # # #                 lpa_num INTEGER PRIMARY KEY,
# # # # #                 url TEXT
# # # # #             )
# # # # #         """))

# # # # #         # 2. Metadata: Name Mappings
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS meta_name_changes (
# # # # #                 original_name TEXT PRIMARY KEY,
# # # # #                 new_name TEXT
# # # # #             )
# # # # #         """))

# # # # #         # 3. Metadata: Tech Tags
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS meta_tech_tags (
# # # # #                 original_tag TEXT PRIMARY KEY,
# # # # #                 cleaned_tag TEXT
# # # # #             )
# # # # #         """))

# # # # #         # 4. Metadata: Fund Commitments
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS isomer_funds (
# # # # #                 fund_name TEXT PRIMARY KEY,
# # # # #                 isomer_fund TEXT,
# # # # #                 vintage_year INTEGER,
# # # # #                 isomer_commitment_eur REAL,
# # # # #                 isomer_ic_date TEXT,
# # # # #                 lpac_seat BOOLEAN
# # # # #             )
# # # # #         """))
        
# # # # #         # 5. Metadata: Fund Name Map (Messy -> Clean)
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS meta_fund_names (
# # # # #                 original_fund TEXT PRIMARY KEY,
# # # # #                 cleaned_fund TEXT
# # # # #             )
# # # # #         """))

# # # # #         # 6. Cleaned Portfolio Data (The "Gold" Table)
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS portfolio_entries (
# # # # #                 id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # #                 lpa_num INTEGER,
# # # # #                 company_name TEXT,
# # # # #                 isomer_fund TEXT,
# # # # #                 fund_name TEXT,
# # # # #                 reporting_quarter TEXT,
# # # # #                 invest_year INTEGER,
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
# # # # #                 url TEXT,
# # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
# # # # #             )
# # # # #         """))

# # # # #         # 7. Raw Data Vault (The "Bronze" Table) - UPDATED TO MATCH YOUR CSV
# # # # #         # We use TEXT for almost everything to ensure valid storage of any input format
# # # # #         conn.execute(text("""
# # # # #             CREATE TABLE IF NOT EXISTS raw_portfolio_entries (
# # # # #                 raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
# # # # #                 source_file TEXT,
# # # # #                 upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                
# # # # #                 -- Identifiers
# # # # #                 lpa_num TEXT,
# # # # #                 data_as_of_date TEXT,
# # # # #                 company_name_legal TEXT,
# # # # #                 company_short_name TEXT,
# # # # #                 fund_name TEXT,
                
# # # # #                 -- Dates & Currency
# # # # #                 initial_investment_date TEXT,
# # # # #                 fund_currency TEXT,
                
# # # # #                 -- Financials (Fund Currency)
# # # # #                 total_cost_fund_ccy TEXT,
# # # # #                 current_cost_fund_ccy TEXT,
# # # # #                 current_value_fund_ccy TEXT,
# # # # #                 realized_value_fund_ccy TEXT,
# # # # #                 total_value_fund_ccy TEXT,
# # # # #                 multiple_fund_ccy TEXT,
                
# # # # #                 -- Financials (Base Currency - EUR)
# # # # #                 total_cost_base_ccy TEXT,
# # # # #                 current_cost_base_ccy TEXT,
# # # # #                 current_value_base_ccy TEXT,
# # # # #                 realized_value_base_ccy TEXT,
# # # # #                 total_value_base_ccy TEXT,
# # # # #                 multiple_base_ccy TEXT,
                
# # # # #                 -- Categorization
# # # # #                 status TEXT,
# # # # #                 country TEXT,
# # # # #                 region_group TEXT,
                
# # # # #                 -- Sector & Industry
# # # # #                 sector TEXT,
# # # # #                 industry_group TEXT,
# # # # #                 industry TEXT,
# # # # #                 industry_detailed TEXT,
                
# # # # #                 -- Tags & Descriptions
# # # # #                 technology_tag TEXT,
# # # # #                 business_model TEXT,
# # # # #                 description TEXT,
# # # # #                 sdgs TEXT,
# # # # #                 female_founders TEXT,
# # # # #                 long_description TEXT
# # # # #             )
# # # # #         """))

# # # # # def load_metadata(table_name):
# # # # #     """Helper to load a metadata table into a pandas DataFrame."""
# # # # #     engine = get_engine()
# # # # #     try:
# # # # #         return pd.read_sql(f"SELECT * FROM {table_name}", engine)
# # # # #     except Exception:
# # # # #         return pd.DataFrame()

# # # # # def save_raw_data(df, source_label):
# # # # #     """
# # # # #     Saves raw, uncleaned data to the raw_portfolio_entries table.
# # # # #     Maps columns from the exact CSV structure you provided.
# # # # #     """
# # # # #     engine = get_engine()
    
# # # # #     # Complete Mapping based on your sample_data.csv
# # # # #     column_map = {
# # # # #         'LP Analyst Identifier': 'lpa_num',
# # # # #         'Data as of Date': 'data_as_of_date',
# # # # #         'Company Name': 'company_name_legal',
# # # # #         'Company Short Name': 'company_short_name',
# # # # #         'Fund Name': 'fund_name',
# # # # #         'Initial Investment Date': 'initial_investment_date',
# # # # #         'Fund Currency': 'fund_currency',
        
# # # # #         # Fund Currency Metrics
# # # # #         'Client - Total Cost (Fund Currency)': 'total_cost_fund_ccy',
# # # # #         'Client - Current Cost (Fund Currency)': 'current_cost_fund_ccy',
# # # # #         'Client - Current Value (Fund Currency)': 'current_value_fund_ccy',
# # # # #         'Client - Realized Value (Fund Currency)': 'realized_value_fund_ccy',
# # # # #         'Client - Total Value (Fund Currency)': 'total_value_fund_ccy',
# # # # #         'Client - Multiple (Fund Currency)': 'multiple_fund_ccy',
        
# # # # #         # Base Currency Metrics
# # # # #         'Client - Total Cost (Base Currency)': 'total_cost_base_ccy',
# # # # #         'Client - Current Cost (Base Currency)': 'current_cost_base_ccy',
# # # # #         'Client - Current Value (Base Currency)': 'current_value_base_ccy',
# # # # #         'Client - Realized Value (Base Currency)': 'realized_value_base_ccy',
# # # # #         'Client - Total Value (Base Currency)': 'total_value_base_ccy',
# # # # #         'Client - Multiple (Base Currency)': 'multiple_base_ccy',
        
# # # # #         # Categorization
# # # # #         'Company Status': 'status',
# # # # #         'Country': 'country',
# # # # #         'Region Group': 'region_group',
        
# # # # #         # Industry
# # # # #         'LP Analyst - Sector': 'sector',
# # # # #         'LP Analyst - Industry Group': 'industry_group',
# # # # #         'LP Analyst - Industry': 'industry',
# # # # #         'LP Analyst - Industry (Detailed)': 'industry_detailed',
        
# # # # #         # Qualitative
# # # # #         'Technology Tag': 'technology_tag',
# # # # #         'Business Model': 'business_model',
# # # # #         'Description': 'description',
# # # # #         'SDGs': 'sdgs',
# # # # #         'Female Founders': 'female_founders',
# # # # #         'Long Description': 'long_description'
# # # # #     }
    
# # # # #     # 1. Rename columns
# # # # #     df_to_save = df.rename(columns=column_map)
    
# # # # #     # 2. Add Source Metadata
# # # # #     df_to_save['source_file'] = source_label
    
# # # # #     # 3. Filter to only keep columns that exist in our DB table
# # # # #     # This prevents errors if the source CSV has extra random columns
# # # # #     valid_cols = [
# # # # #         'source_file', 'lpa_num', 'data_as_of_date', 'company_name_legal', 'company_short_name',
# # # # #         'fund_name', 'initial_investment_date', 'fund_currency',
# # # # #         'total_cost_fund_ccy', 'current_cost_fund_ccy', 'current_value_fund_ccy',
# # # # #         'realized_value_fund_ccy', 'total_value_fund_ccy', 'multiple_fund_ccy',
# # # # #         'total_cost_base_ccy', 'current_cost_base_ccy', 'current_value_base_ccy',
# # # # #         'realized_value_base_ccy', 'total_value_base_ccy', 'multiple_base_ccy',
# # # # #         'status', 'country', 'region_group', 'sector', 'industry_group', 'industry',
# # # # #         'industry_detailed', 'technology_tag', 'business_model', 'description',
# # # # #         'sdgs', 'female_founders', 'long_description'
# # # # #     ]
    
# # # # #     # Keep only valid cols that exist in the dataframe
# # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # #     df_to_save = df_to_save[final_cols]
    
# # # # #     # 4. Convert to String for Safety
# # # # #     # We store everything as TEXT in the raw vault so we never lose data due to type errors
# # # # #     df_to_save = df_to_save.astype(str)
    
# # # # #     # 5. Append to DB
# # # # #     df_to_save.to_sql('raw_portfolio_entries', engine, if_exists='append', index=False)

# # # # # def save_quarterly_data(df):
# # # # #     """
# # # # #     Saves the cleaned quarterly data to the main portfolio_entries table.
# # # # #     Maps the 'Cleaned' column names to the 'Database' column names.
# # # # #     """
# # # # #     engine = get_engine()
    
# # # # #     # Map DataFrame columns (from cleaning.py) to Database columns (snake_case)
# # # # #     col_map = {
# # # # #         'LPA Num': 'lpa_num',
# # # # #         'Company Name': 'company_name',
# # # # #         'Isomer Fund': 'isomer_fund',
# # # # #         'Fund Name': 'fund_name',
# # # # #         'Invest Quarter': 'reporting_quarter',
# # # # #         'Invest Year': 'invest_year',
# # # # #         'Status': 'status',
# # # # #         'Country': 'country',
# # # # #         'Technology Tag': 'technology_tag',
# # # # #         'Business Model': 'business_model',
# # # # #         'Description': 'description',
# # # # #         'Long Description': 'long_description',
# # # # #         'SDGs': 'sdgs',
# # # # #         'Female Founders': 'female_founders',
# # # # #         "Cost in Isomer's Share EUR": 'cost_eur',
# # # # #         "Valuation of Isomer's Share EUR": 'value_eur',
# # # # #         "Distributions EUR": 'distributions_eur',
# # # # #         'Multiple': 'multiple',
# # # # #         'URL': 'url'
# # # # #     }
    
# # # # #     # Rename columns
# # # # #     df_to_save = df.rename(columns=col_map)
    
# # # # #     # Select only the columns that exist in our DB table
# # # # #     # (This prevents errors if the cleaned DF has extra temp columns)
# # # # #     valid_cols = [
# # # # #         'lpa_num', 'company_name', 'isomer_fund', 'fund_name', 'reporting_quarter', 
# # # # #         'invest_year', 'status', 'country', 'technology_tag', 'business_model', 
# # # # #         'description', 'long_description', 'sdgs', 'female_founders', 
# # # # #         'cost_eur', 'value_eur', 'distributions_eur', 'multiple', 'url'
# # # # #     ]
    
# # # # #     final_cols = [c for c in valid_cols if c in df_to_save.columns]
# # # # #     df_to_save = df_to_save[final_cols]
    
# # # # #     # Append to the "Gold" table
# # # # #     df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)