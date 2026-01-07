import pandas as pd
from sqlalchemy import create_engine, text
import streamlit as st
import os

# Import the sync function (Wrap in try/except to avoid errors if running locally without Drive setup yet)
try:
    from src.drive_sync import upload_db_to_drive
except ImportError:
    def upload_db_to_drive():
        pass

# Use Streamlit secrets for DB URL if available, else local SQLite
try:
    DB_PATH = st.secrets["DB_URL"]
except:
    DB_PATH = "sqlite:///data/isomer_central_repo.db"

def get_engine():
    return create_engine(DB_PATH)

def init_db():
    """Creates the necessary tables if they don't exist."""
    engine = get_engine()
    with engine.connect() as conn:
        # 1. Metadata Tables
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_urls (lpa_num INTEGER PRIMARY KEY, url TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_name_changes (original_name TEXT, new_name TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_tech_tags (original_tag TEXT, cleaned_tag TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta_fund_names (original_fund TEXT, cleaned_fund TEXT)"))

        # 2. Portfolio Entries (The Granular History)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lpa_num INTEGER,
                company_name TEXT,
                isomer_fund TEXT,
                fund_name TEXT,
                reporting_quarter TEXT,
                invest_year INTEGER,
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
                url TEXT,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # 3. Isomer Fund Commitments (The Dimension Table)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS isomer_funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_name TEXT UNIQUE,
                vintage_year INTEGER,
                ccy TEXT,
                size_ccy REAL,
                isomer_commitment_ccy REAL,
                isomer_commitment_eur REAL,
                share_of_partnership REAL,
                isomer_fund TEXT,
                organisation TEXT,
                hq TEXT,
                stage_of_investment TEXT,
                allocation_type TEXT,
                lpac_seat TEXT,
                isomer_ic_date DATE
            )
        """))

def load_metadata(table_name):
    """Loads a metadata table into a DataFrame."""
    engine = get_engine()
    try:
        return pd.read_sql(table_name, engine)
    except Exception:
        # Return empty DF if table doesn't exist yet
        return pd.DataFrame()

def save_quarterly_data(df, quarter_label):
    """
    Appends cleaned, granular data to the DB.
    Checks for duplicates by quarter to prevent double-uploading.
    """
    engine = get_engine()
    
    # 1. Check if data for this quarter already exists
    try:
        existing = pd.read_sql(
            f"SELECT count(*) as count FROM portfolio_entries WHERE reporting_quarter = '{quarter_label}'", 
            engine
        )
        if existing['count'].iloc[0] > 0:
            raise ValueError(f"Data for '{quarter_label}' already exists in the database!")
    except Exception:
        # If table doesn't exist, we can proceed safely
        pass
    
    # 2. Map DataFrame columns to Database columns
    column_map = {
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
        'Female Founders': 'female_founders'
    }
    
    # 3. Rename columns
    df_to_save = df.rename(columns=column_map)
    
    # --- THIS WAS THE LINE CAUSING YOUR ERROR ---
    df_to_save['reporting_quarter'] = quarter_label
    # --------------------------------------------
    
    # 4. Ensure qualitative columns exist (fill with None if missing)
    text_cols = ['description', 'long_description', 'sdgs', 'female_founders']
    for col in text_cols:
        if col not in df_to_save.columns:
            df_to_save[col] = None

    # 5. Filter for only valid DB columns
    valid_cols = list(column_map.values()) + ['reporting_quarter']
    # Only keep columns that are actually in our new dataframe
    final_cols = [c for c in valid_cols if c in df_to_save.columns]
    
    df_to_save = df_to_save[final_cols]
    
    # 6. Save to SQLite
    df_to_save.to_sql('portfolio_entries', engine, if_exists='append', index=False)
    
    # 7. Trigger Drive Sync (Back up the file immediately)
    if "sqlite" in DB_PATH:
        upload_db_to_drive()