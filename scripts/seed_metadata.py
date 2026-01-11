import pandas as pd
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.database import init_db, get_engine, clean_fund_name

def seed_metadata():
    engine = get_engine()
    print("🌱 Seeding Metadata Tables...")

    # 1. Standard Metadata
    try:
        # Load Name Mappings (The Fix)
        if os.path.exists("data/fund_name_changes_master.csv"):
            print("   ...Loading Fund Name Overrides...")
            # Load with headers assumed (header=0)
            map_df = pd.read_csv("data/fund_name_changes_master.csv")
            
            # Normalize column names (lowercase, strip)
            map_df.columns = map_df.columns.str.strip().str.lower()
            
            # Rename if needed (handles 'original_fund' or 'original')
            rename_map = {'original': 'original_fund', 'clean': 'cleaned_fund', 'new': 'cleaned_fund', 'suggested_match': 'cleaned_fund'}
            map_df.rename(columns=rename_map, inplace=True)
            
            # Ensure we have the right columns
            if 'original_fund' in map_df.columns and 'cleaned_fund' in map_df.columns:
                # Trim whitespace from the actual data
                map_df['original_fund'] = map_df['original_fund'].astype(str).str.strip()
                map_df['cleaned_fund'] = map_df['cleaned_fund'].astype(str).str.strip()
                
                map_df[['original_fund', 'cleaned_fund']].to_sql('meta_fund_names', engine, if_exists='replace', index=False)
                print(f"   ✅ Loaded {len(map_df)} Fund Name Overrides.")
            else:
                print("   ❌ Error: data/fund_name_changes_master.csv is missing columns 'original_fund' or 'cleaned_fund'")
        else:
            print("   ⚠️  data/fund_name_changes_master.csv not found.")
            
        # Other Meta tables
        if os.path.exists("data/company_urls_master.csv"):
            pd.read_csv("data/company_urls_master.csv").rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}).to_sql('meta_urls', engine, if_exists='replace', index=False)
        if os.path.exists("data/tech_tags_master.csv"):
            pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag']).to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
            
    except Exception as e: 
        print(f"   ❌ Metadata Error: {e}")

    # 2. Internal Funds
    try:
        if os.path.exists("data/isomer_internal_funds.csv"):
            print("   ...Loading Internal Funds...")
            internal_df = pd.read_csv("data/isomer_internal_funds.csv")
            internal_df.columns = internal_df.columns.str.strip().str.lower().str.replace(' ', '_')
            rename_map = {'isomer_fund': 'isomer_fund', 'fund': 'isomer_fund', 'currency': 'currency', 'ccy': 'currency', 'fund_size': 'fund_size', 'size': 'fund_size', 'vintage_year': 'vintage_year', 'vintage': 'vintage_year'}
            internal_df.rename(columns=rename_map, inplace=True)
            valid_cols = ['isomer_fund', 'currency', 'fund_size', 'vintage_year']
            internal_df[[c for c in valid_cols if c in internal_df.columns]].to_sql('isomer_internal_funds', engine, if_exists='replace', index=False)
    except: pass

    # 3. Managers
    try:
        if os.path.exists("data/managers.csv"):
            print("   ...Loading Managers...")
            mgr_df = pd.read_csv("data/managers.csv")
            mgr_df.columns = mgr_df.columns.str.strip().str.lower().str.replace(' ', '_')
            mgr_rename = {'organisation': 'organisation', 'manager': 'organisation', 'headquarters': 'headquarters', 'hq': 'headquarters', 'secondary_offices': 'secondary_offices', 'offices': 'secondary_offices', 'url': 'url', 'website': 'url'}
            mgr_df.rename(columns=mgr_rename, inplace=True)
            mgr_valid = ['organisation', 'headquarters', 'secondary_offices', 'url']
            mgr_df[[c for c in mgr_valid if c in mgr_df.columns]].to_sql('managers', engine, if_exists='replace', index=False)
    except: pass

    # 4. Master Fund List
    print("   ...Merging Master Fund Lists...")
    fund_files = [
        {"path": "data/isomer_funds.csv", "fallback": "Primary Fund", "map": {'fund_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'organisation': 'organisation', 'vintage_year': 'vintage_year', 'isomer_commitment_eur': 'isomer_commitment_eur', 'isomer_ic_date': 'isomer_ic_date', 'lpac_seat': 'lpac_seat', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type'}},
        {"path": "data/secondaries.csv", "fallback": "Direct Secondary", "map": {'transaction': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'ic_date': 'isomer_ic_date', 'purchase_price_eur_drawn_and_undrawn': 'isomer_commitment_eur'}},
        {"path": "data/coinvest.csv", "fallback": "Direct Co-Invest", "map": {'company_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'cost': 'isomer_commitment_eur'}}
    ]
    
    combined_funds = []
    for f in fund_files:
        if os.path.exists(f["path"]):
            try:
                df = pd.read_csv(f["path"])
                df.columns = df.columns.str.strip().str.lower()
                normalized_map = {k.lower(): v for k, v in f["map"].items()}
                actual_rename = {k: v for k, v in normalized_map.items() if k in df.columns}
                df.rename(columns=actual_rename, inplace=True)
                
                if 'default_deal_type' in df.columns:
                    df['default_deal_type'] = df['default_deal_type'].fillna(f["fallback"])
                else:
                    df['default_deal_type'] = f["fallback"]
                combined_funds.append(df)
            except: pass

    if combined_funds:
        master_df = pd.concat(combined_funds, ignore_index=True)
        if 'organisation' not in master_df.columns: master_df['organisation'] = None
        defaults = {'vintage_year': 2020, 'isomer_commitment_eur': 0, 'isomer_ic_date': None, 'lpac_seat': False, 'alt_name_1': None, 'alt_name_2': None, 'default_deal_type': 'Primary Fund'}
        for col, val in defaults.items():
            if col not in master_df.columns: master_df[col] = val
        
        # Apply clean name
        if 'fund_name' in master_df.columns:
            master_df['clean_fund_name'] = master_df['fund_name'].apply(clean_fund_name)

        db_cols = ['fund_name', 'clean_fund_name', 'isomer_fund', 'organisation', 'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2', 'default_deal_type']
        master_df[[c for c in db_cols if c in master_df.columns]].to_sql('isomer_funds', engine, if_exists='replace', index=False)
        print(f"✅ Loaded {len(master_df)} Total Master Funds.")

if __name__ == "__main__":
    init_db()
    seed_metadata()

# import pandas as pd
# import sys
# import os
# from sqlalchemy import text

# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # IMPORT NEW FUNCTION
# from src.database import init_db, get_engine, clean_fund_name

# def seed_metadata():
#     engine = get_engine()
#     print("🌱 Seeding Metadata Tables...")

#     # 1. Standard Metadata
#     try:
#         pd.read_csv("data/company_urls_master.csv").rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}).to_sql('meta_urls', engine, if_exists='replace', index=False)
#         pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name']).to_sql('meta_name_changes', engine, if_exists='replace', index=False)
#         pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag']).to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
#         pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund']).to_sql('meta_fund_names', engine, if_exists='replace', index=False)
#     except: pass

#     # 2. Internal Isomer Funds
#     print("   ...Loading Internal Isomer Funds...")
#     try:
#         internal_df = pd.read_csv("data/isomer_internal_funds.csv")
#         internal_df.columns = internal_df.columns.str.strip().str.lower().str.replace(' ', '_')
        
#         rename_map = {'isomer_fund': 'isomer_fund', 'fund': 'isomer_fund', 'currency': 'currency', 'ccy': 'currency', 'fund_size': 'fund_size', 'size': 'fund_size', 'vintage_year': 'vintage_year', 'vintage': 'vintage_year'}
#         internal_df.rename(columns=rename_map, inplace=True)
        
#         valid_cols = ['isomer_fund', 'currency', 'fund_size', 'vintage_year']
#         internal_df[[c for c in valid_cols if c in internal_df.columns]].to_sql('isomer_internal_funds', engine, if_exists='replace', index=False)
#     except FileNotFoundError:
#         print("   ⚠️  Skipping data/isomer_internal_funds.csv (Not found)")

#     # 3. Managers
#     print("   ...Loading Manager Data...")
#     try:
#         mgr_df = pd.read_csv("data/managers.csv")
#         mgr_df.columns = mgr_df.columns.str.strip().str.lower().str.replace(' ', '_')
        
#         mgr_rename = {'organisation': 'organisation', 'manager': 'organisation', 'headquarters': 'headquarters', 'hq': 'headquarters', 'secondary_offices': 'secondary_offices', 'offices': 'secondary_offices', 'url': 'url', 'website': 'url'}
#         mgr_df.rename(columns=mgr_rename, inplace=True)
        
#         mgr_valid = ['organisation', 'headquarters', 'secondary_offices', 'url']
#         mgr_df[[c for c in mgr_valid if c in mgr_df.columns]].to_sql('managers', engine, if_exists='replace', index=False)
#     except FileNotFoundError:
#         print("   ⚠️  Skipping data/managers.csv (Not found)")

#     # 4. Isomer Master Fund List
#     print("   ...Merging Primary, Secondary, and Co-invest lists...")
#     fund_files = [
#         {
#             "path": "data/isomer_funds.csv", "fallback": "Primary Fund",
#             "map": {'fund_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'organisation': 'organisation', 'vintage_year': 'vintage_year', 'isomer_commitment_eur': 'isomer_commitment_eur', 'isomer_ic_date': 'isomer_ic_date', 'lpac_seat': 'lpac_seat', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type'}
#         },
#         {
#             "path": "data/secondaries.csv", "fallback": "Direct Secondary",
#             "map": {'transaction': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'ic_date': 'isomer_ic_date', 'purchase_price_eur_drawn_and_undrawn': 'isomer_commitment_eur'}
#         },
#         {
#             "path": "data/coinvest.csv", "fallback": "Direct Co-Invest",
#             "map": {'company_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'cost': 'isomer_commitment_eur'}
#         }
#     ]
    
#     combined_funds = []
#     for f in fund_files:
#         if os.path.exists(f["path"]):
#             try:
#                 df = pd.read_csv(f["path"])
#                 df.columns = df.columns.str.strip().str.lower()
#                 normalized_map = {k.lower(): v for k, v in f["map"].items()}
#                 actual_rename = {k: v for k, v in normalized_map.items() if k in df.columns}
#                 df.rename(columns=actual_rename, inplace=True)
                
#                 if 'default_deal_type' in df.columns:
#                     df['default_deal_type'] = df['default_deal_type'].fillna(f["fallback"])
#                 else:
#                     df['default_deal_type'] = f["fallback"]
#                 combined_funds.append(df)
#             except: pass

#     if combined_funds:
#         master_df = pd.concat(combined_funds, ignore_index=True)
#         if 'organisation' not in master_df.columns:
#             master_df['organisation'] = None

#         defaults = {'vintage_year': 2020, 'isomer_commitment_eur': 0, 'isomer_ic_date': None, 'lpac_seat': False, 'alt_name_1': None, 'alt_name_2': None, 'default_deal_type': 'Primary Fund'}
#         for col, val in defaults.items():
#             if col not in master_df.columns: master_df[col] = val
        
#         # --- APPLY CLEAN NAME ---
#         if 'fund_name' in master_df.columns:
#             master_df['clean_fund_name'] = master_df['fund_name'].apply(clean_fund_name)

#         db_cols = ['fund_name', 'clean_fund_name', 'isomer_fund', 'organisation', 'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2', 'default_deal_type']
        
#         final_df = master_df[[c for c in db_cols if c in master_df.columns]]
#         final_df.to_sql('isomer_funds', engine, if_exists='replace', index=False)
#         print(f"✅ Loaded {len(final_df)} Total Master Funds into the Brain.")

# if __name__ == "__main__":
#     init_db()
#     seed_metadata()

# # import pandas as pd
# # import sys
# # import os
# # from sqlalchemy import text

# # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # from src.database import init_db, get_engine

# # def seed_metadata():
# #     engine = get_engine()
# #     print("🌱 Seeding Metadata Tables...")

# #     # 1. Standard Metadata (URLs, Tags, Renames)
# #     try:
# #         pd.read_csv("data/company_urls_master.csv").rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}).to_sql('meta_urls', engine, if_exists='replace', index=False)
# #         pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name']).to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# #         pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag']).to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# #         pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund']).to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# #     except: pass

# #     # --- 2. Internal Isomer Funds (Dimension Table) ---
# #     print("   ...Loading Internal Isomer Funds...")
# #     try:
# #         internal_df = pd.read_csv("data/isomer_internal_funds.csv")
# #         internal_df.columns = internal_df.columns.str.strip().str.lower().str.replace(' ', '_')
        
# #         rename_map = {'isomer_fund': 'isomer_fund', 'fund': 'isomer_fund', 'currency': 'currency', 'ccy': 'currency', 'fund_size': 'fund_size', 'size': 'fund_size', 'vintage_year': 'vintage_year', 'vintage': 'vintage_year'}
# #         internal_df.rename(columns=rename_map, inplace=True)
        
# #         valid_cols = ['isomer_fund', 'currency', 'fund_size', 'vintage_year']
# #         internal_df[[c for c in valid_cols if c in internal_df.columns]].to_sql('isomer_internal_funds', engine, if_exists='replace', index=False)
# #         print(f"   ✅ Loaded {len(internal_df)} Internal Funds.")
# #     except FileNotFoundError:
# #         print("   ⚠️  Skipping data/isomer_internal_funds.csv (Not found)")

# #     # --- 3. Manager Metadata (Dimension Table) ---
# #     print("   ...Loading Manager Data...")
# #     try:
# #         mgr_df = pd.read_csv("data/managers.csv")
# #         mgr_df.columns = mgr_df.columns.str.strip().str.lower().str.replace(' ', '_')
        
# #         mgr_rename = {
# #             'organisation': 'organisation', 'manager': 'organisation',
# #             'headquarters': 'headquarters', 'hq': 'headquarters',
# #             'secondary_offices': 'secondary_offices', 'offices': 'secondary_offices',
# #             'url': 'url', 'website': 'url'
# #         }
# #         mgr_df.rename(columns=mgr_rename, inplace=True)
        
# #         mgr_valid = ['organisation', 'headquarters', 'secondary_offices', 'url']
# #         mgr_df[[c for c in mgr_valid if c in mgr_df.columns]].to_sql('managers', engine, if_exists='replace', index=False)
# #         print(f"   ✅ Loaded {len(mgr_df)} Managers.")
# #     except FileNotFoundError:
# #         print("   ⚠️  Skipping data/managers.csv (Not found)")

# #     # --- 4. Isomer Master Fund List (The Brain) ---
# #     print("   ...Merging Primary, Secondary, and Co-invest lists...")
# #     fund_files = [
# #         {
# #             "path": "data/isomer_funds.csv", 
# #             "fallback": "Primary Fund",
# #             "map": {
# #                 # EXACT COLUMN MAPPING FROM YOUR CSV
# #                 'fund_name': 'fund_name',
# #                 'isomer_fund': 'isomer_fund',
# #                 'organisation': 'organisation',
# #                 'vintage_year': 'vintage_year',
# #                 'isomer_commitment_eur': 'isomer_commitment_eur',
# #                 'isomer_ic_date': 'isomer_ic_date',
# #                 'lpac_seat': 'lpac_seat',
# #                 'alt_name_1': 'alt_name_1',
# #                 'alt_name_2': 'alt_name_2',
# #                 'deal_type': 'default_deal_type'
# #                 # Note: 'stage', 'hq', 'ccy' etc. are read but dropped 
# #                 # because they aren't in the database schema yet.
# #             }
# #         },
# #         {
# #             "path": "data/secondaries.csv", 
# #             "fallback": "Direct Secondary",
# #             "map": {
# #                 'transaction': 'fund_name', 
# #                 'isomer_fund': 'isomer_fund', 
# #                 'alt_name_1': 'alt_name_1', 
# #                 'alt_name_2': 'alt_name_2', 
# #                 'deal_type': 'default_deal_type', 
# #                 'ic_date': 'isomer_ic_date', 
# #                 'purchase_price_eur_drawn_and_undrawn': 'isomer_commitment_eur'
# #             }
# #         },
# #         {
# #             "path": "data/coinvest.csv", 
# #             "fallback": "Direct Co-Invest",
# #             "map": {
# #                 'company_name': 'fund_name', 
# #                 'isomer_fund': 'isomer_fund', 
# #                 'alt_name_1': 'alt_name_1', 
# #                 'alt_name_2': 'alt_name_2', 
# #                 'deal_type': 'default_deal_type', 
# #                 'cost': 'isomer_commitment_eur'
# #             }
# #         }
# #     ]
    
# #     combined_funds = []
# #     for f in fund_files:
# #         if os.path.exists(f["path"]):
# #             try:
# #                 df = pd.read_csv(f["path"])
# #                 # Clean headers: lowercase, strip space
# #                 df.columns = df.columns.str.strip().str.lower()
                
# #                 # Apply renaming map (lowercase keys to match cleaned headers)
# #                 normalized_map = {k.lower(): v for k, v in f["map"].items()}
# #                 actual_rename = {k: v for k, v in normalized_map.items() if k in df.columns}
# #                 df.rename(columns=actual_rename, inplace=True)
                
# #                 # Apply default deal type
# #                 if 'default_deal_type' in df.columns:
# #                     df['default_deal_type'] = df['default_deal_type'].fillna(f["fallback"])
# #                 else:
# #                     df['default_deal_type'] = f["fallback"]
                    
# #                 combined_funds.append(df)
# #                 print(f"   -> Found {f['path']} (Merged {len(df)} rows)")
# #             except Exception as e: 
# #                 print(f"   ❌ Error reading {f['path']}: {e}")

# #     if combined_funds:
# #         master_df = pd.concat(combined_funds, ignore_index=True)
        
# #         # Ensure 'organisation' exists (fill with None if missing from other files)
# #         if 'organisation' not in master_df.columns:
# #             master_df['organisation'] = None

# #         # Defaults for DB schema
# #         defaults = {
# #             'vintage_year': 2020, 
# #             'isomer_commitment_eur': 0, 
# #             'isomer_ic_date': None, 
# #             'lpac_seat': False, 
# #             'alt_name_1': None, 
# #             'alt_name_2': None, 
# #             'default_deal_type': 'Primary Fund'
# #         }
# #         for col, val in defaults.items():
# #             if col not in master_df.columns: 
# #                 master_df[col] = val
            
# #         # Select ONLY columns that exist in the DB Schema
# #         db_cols = ['fund_name', 'isomer_fund', 'organisation', 'vintage_year', 
# #                    'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat', 
# #                    'alt_name_1', 'alt_name_2', 'default_deal_type']
                   
# #         final_df = master_df[[c for c in db_cols if c in master_df.columns]]
# #         final_df.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# #         print(f"✅ Loaded {len(final_df)} Total Master Funds into the Brain.")

# # if __name__ == "__main__":
# #     init_db()
# #     seed_metadata()

# # # import pandas as pd
# # # import sys
# # # import os
# # # from sqlalchemy import text

# # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # # from src.database import init_db, get_engine

# # # def seed_metadata():
# # #     engine = get_engine()
# # #     print("🌱 Seeding Metadata Tables...")

# # #     # 1. URLs, Names, Tags, Cleaners
# # #     try:
# # #         pd.read_csv("data/company_urls_master.csv").rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}).to_sql('meta_urls', engine, if_exists='replace', index=False)
# # #         pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name']).to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # #         pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag']).to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # #         pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund']).to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # #     except: pass

# # #     # --- 2. NEW: Isomer Internal Funds ---
# # #     print("   ...Loading Internal Isomer Funds...")
# # #     try:
# # #         internal_df = pd.read_csv("data/isomer_internal_funds.csv")
# # #         # Normalize Headers (lowercase, strip space)
# # #         internal_df.columns = internal_df.columns.str.strip().str.lower().str.replace(' ', '_')
        
# # #         # Map to DB Columns
# # #         rename_map = {
# # #             'isomer_fund': 'isomer_fund', 'fund': 'isomer_fund',
# # #             'currency': 'currency', 'ccy': 'currency',
# # #             'fund_size': 'fund_size', 'size': 'fund_size',
# # #             'vintage_year': 'vintage_year', 'vintage': 'vintage_year'
# # #         }
# # #         internal_df.rename(columns=rename_map, inplace=True)
        
# # #         # Save valid columns only
# # #         valid_cols = ['isomer_fund', 'currency', 'fund_size', 'vintage_year']
# # #         final_internal = internal_df[[c for c in valid_cols if c in internal_df.columns]]
        
# # #         final_internal.to_sql('isomer_internal_funds', engine, if_exists='replace', index=False)
# # #         print(f"   ✅ Loaded {len(final_internal)} Internal Funds.")
# # #     except FileNotFoundError:
# # #         print("   ⚠️  Skipping data/isomer_internal_funds.csv (Not found)")

# # #     # --- 3. Isomer Master Fund List (Combined) ---
# # #     print("   ...Merging Primary, Secondary, and Co-invest lists...")
# # #     fund_files = [
# # #         {
# # #             "path": "data/isomer_funds.csv", "fallback": "Primary Fund",
# # #             "map": {'fund_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type'}
# # #         },
# # #         {
# # #             "path": "data/secondaries.csv", "fallback": "Direct Secondary",
# # #             "map": {'transaction': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'ic_date': 'isomer_ic_date', 'purchase_price_eur_drawn_and_undrawn': 'isomer_commitment_eur'}
# # #         },
# # #         {
# # #             "path": "data/coinvest.csv", "fallback": "Direct Co-Invest",
# # #             "map": {'company_name': 'fund_name', 'isomer_fund': 'isomer_fund', 'alt_name_1': 'alt_name_1', 'alt_name_2': 'alt_name_2', 'deal_type': 'default_deal_type', 'cost': 'isomer_commitment_eur'}
# # #         }
# # #     ]
    
# # #     combined_funds = []
# # #     for f in fund_files:
# # #         if os.path.exists(f["path"]):
# # #             try:
# # #                 df = pd.read_csv(f["path"])
# # #                 df.columns = df.columns.str.strip().str.lower()
# # #                 normalized_map = {k.lower(): v for k, v in f["map"].items()}
# # #                 actual_rename = {k: v for k, v in normalized_map.items() if k in df.columns}
# # #                 df.rename(columns=actual_rename, inplace=True)
                
# # #                 if 'default_deal_type' in df.columns:
# # #                     df['default_deal_type'] = df['default_deal_type'].fillna(f["fallback"])
# # #                 else:
# # #                     df['default_deal_type'] = f["fallback"]
# # #                 combined_funds.append(df)
# # #             except: pass

# # #     if combined_funds:
# # #         master_df = pd.concat(combined_funds, ignore_index=True)
# # #         defaults = {'vintage_year': 2020, 'isomer_commitment_eur': 0, 'isomer_ic_date': None, 'lpac_seat': False, 'alt_name_1': None, 'alt_name_2': None, 'default_deal_type': 'Primary Fund'}
# # #         for col, val in defaults.items():
# # #             if col not in master_df.columns: master_df[col] = val
            
# # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2', 'default_deal_type']
# # #         master_df[db_cols].to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # #         print(f"✅ Loaded {len(master_df)} Total Master Funds into the Brain.")

# # # if __name__ == "__main__":
# # #     init_db()
# # #     seed_metadata()

# # # # import pandas as pd
# # # # import sys
# # # # import os
# # # # from sqlalchemy import text

# # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # # # from src.database import init_db, get_engine

# # # # def seed_metadata():
# # # #     engine = get_engine()
# # # #     print("🌱 Seeding Metadata Tables...")

# # # #     # 1. URLs, Names, Tags (Standard Loading)
# # # #     try:
# # # #         pd.read_csv("data/company_urls_master.csv").rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}).to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # #         pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name']).to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # #         pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag']).to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # #         pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund']).to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # #     except: pass

# # # #     # --- Step 5. Isomer Master Fund List (Consolidated) ---
# # # #     print("   ...Merging Primary, Secondary, and Co-invest lists...")
    
# # # #     # Configuration for each file type
# # # #     fund_files = [
# # # #         {
# # # #             "path": "data/isomer_funds.csv", 
# # # #             "fallback": "Primary Fund",
# # # #             "map": { # Explicit Mapping for Primary Funds
# # # #                 'fund_name': 'fund_name',
# # # #                 'isomer_fund': 'isomer_fund',
# # # #                 'alt_name_1': 'alt_name_1',
# # # #                 'alt_name_2': 'alt_name_2',
# # # #                 'deal_type': 'default_deal_type',
# # # #                 'vintage_year': 'vintage_year',
# # # #                 'isomer_commitment_eur': 'isomer_commitment_eur',
# # # #                 'isomer_ic_date': 'isomer_ic_date',
# # # #                 'lpac_seat': 'lpac_seat'
# # # #                 # Note: 'stage', 'ccy', 'hq', etc. are not currently in the DB schema, 
# # # #                 # so they will be skipped during DB insert, which is correct.
# # # #             }
# # # #         },
# # # #         {
# # # #             "path": "data/secondaries.csv", 
# # # #             "fallback": "Direct Secondary", 
# # # #             "map": { # Explicit Mapping for Secondaries
# # # #                 'transaction': 'fund_name',          # Key
# # # #                 'isomer_fund': 'isomer_fund',
# # # #                 'alt_name_1': 'alt_name_1',
# # # #                 'alt_name_2': 'alt_name_2',
# # # #                 'deal_type': 'default_deal_type',
# # # #                 'ic_date': 'isomer_ic_date',
# # # #                 'purchase_price_eur_drawn_and_undrawn': 'isomer_commitment_eur'
# # # #             }
# # # #         },
# # # #         {
# # # #             "path": "data/coinvest.csv", 
# # # #             "fallback": "Direct Co-Invest",
# # # #             "map": { # Explicit Mapping for Co-Invest
# # # #                 'company_name': 'fund_name',         # Key
# # # #                 'isomer_fund': 'isomer_fund',
# # # #                 'alt_name_1': 'alt_name_1',
# # # #                 'alt_name_2': 'alt_name_2',
# # # #                 'deal_type': 'default_deal_type',
# # # #                 'cost': 'isomer_commitment_eur'      # Cost = Commitment
# # # #             }
# # # #         }
# # # #     ]
    
# # # #     combined_funds = []
    
# # # #     for f in fund_files:
# # # #         f_path = f["path"]
# # # #         fallback_type = f["fallback"]
# # # #         col_map = f["map"]
        
# # # #         if os.path.exists(f_path):
# # # #             try:
# # # #                 df = pd.read_csv(f_path)
# # # #                 df.columns = df.columns.str.strip().str.lower() # Normalize file headers to lowercase
                
# # # #                 # 1. Rename Columns based on specific file map
# # # #                 # (We lowercase the map keys to match the normalized headers)
# # # #                 normalized_map = {k.lower(): v for k, v in col_map.items()}
# # # #                 actual_rename = {k: v for k, v in normalized_map.items() if k in df.columns}
                
# # # #                 df.rename(columns=actual_rename, inplace=True)
                
# # # #                 # 2. Handle Defaults
# # # #                 if 'default_deal_type' in df.columns:
# # # #                     df['default_deal_type'] = df['default_deal_type'].fillna(fallback_type)
# # # #                 else:
# # # #                     df['default_deal_type'] = fallback_type
                
# # # #                 combined_funds.append(df)
# # # #                 print(f"   -> Found {f_path} (Merged {len(df)} rows)")
# # # #             except Exception as e:
# # # #                 print(f"   ❌ Error reading {f_path}: {e}")
# # # #         else:
# # # #             print(f"   ⚠️  Skipping {f_path} (Not found)")

# # # #     if combined_funds:
# # # #         master_df = pd.concat(combined_funds, ignore_index=True)
        
# # # #         # Ensure Schema Completeness
# # # #         defaults = {
# # # #             'vintage_year': 2020, 'isomer_commitment_eur': 0, 
# # # #             'isomer_ic_date': None, 'lpac_seat': False,
# # # #             'alt_name_1': None, 'alt_name_2': None,
# # # #             'default_deal_type': 'Primary Fund'
# # # #         }
# # # #         for col, val in defaults.items():
# # # #             if col not in master_df.columns:
# # # #                 master_df[col] = val
        
# # # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 
# # # #                    'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2', 'default_deal_type']
        
# # # #         final_funds = master_df[[c for c in db_cols if c in master_df.columns]]
        
# # # #         final_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # # #         print(f"✅ Loaded {len(final_funds)} Total Master Funds into the Brain.")
# # # #     else:
# # # #         print("❌ Error: No fund files found!")

# # # # if __name__ == "__main__":
# # # #     init_db()
# # # #     seed_metadata()

# # # # # import pandas as pd
# # # # # import sys
# # # # # import os
# # # # # from sqlalchemy import text

# # # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # # # # from src.database import init_db, get_engine

# # # # # def seed_metadata():
# # # # #     engine = get_engine()
# # # # #     print("🌱 Seeding Metadata Tables...")

# # # # #     # 1. URLs
# # # # #     try:
# # # # #         urls_df = pd.read_csv("data/company_urls_master.csv")
# # # # #         urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
# # # # #         urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # # #         print(f"✅ Loaded {len(urls_df)} URLs.")
# # # # #     except FileNotFoundError:
# # # # #         print("❌ Warning: 'company_urls_master.csv' not found.")

# # # # #     # 2. Name Changes
# # # # #     try:
# # # # #         names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
# # # # #         names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # # #         print(f"✅ Loaded {len(names_df)} Name Mappings.")
# # # # #     except FileNotFoundError:
# # # # #         print("❌ Warning: 'name_change_master.csv' not found.")

# # # # #     # 3. Tech Tags
# # # # #     try:
# # # # #         tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
# # # # #         tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # # #         print(f"✅ Loaded {len(tags_df)} Tech Tags.")
# # # # #     except FileNotFoundError:
# # # # #         print("❌ Warning: 'tech_tags_master.csv' not found.")

# # # # #     # 4. Fund Names
# # # # #     try:
# # # # #         funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
# # # # #         funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # # #         print(f"✅ Loaded {len(funds_df)} Fund Name Cleaners.")
# # # # #     except FileNotFoundError:
# # # # #         print("❌ Warning: 'fund_name_changes_master.csv' not found.")

# # # # #     # --- Step 5. Isomer Master Fund List ---
# # # # #     try:
# # # # #         master_df = pd.read_csv("data/isomer_funds.csv")
        
# # # # #         # DEBUG: Tell us exactly what columns pandas sees
# # # # #         print(f"   DEBUG: CSV Columns Found: {list(master_df.columns)}")
        
# # # # #         # A. Clean Headers (strip whitespace and lowercase)
# # # # #         master_df.columns = master_df.columns.str.strip()
        
# # # # #         # B. Smart Rename (Handle "Alt Name 1", "alt name 1", etc.)
# # # # #         rename_map = {
# # # # #             'Alt Name 1': 'alt_name_1', 'alt name 1': 'alt_name_1', 'Alternative Name 1': 'alt_name_1',
# # # # #             'Alt Name 2': 'alt_name_2', 'alt name 2': 'alt_name_2', 'Alternative Name 2': 'alt_name_2',
# # # # #             'Fund Name': 'fund_name', 'Isomer Fund': 'isomer_fund'
# # # # #         }
# # # # #         # Only rename if the column actually exists
# # # # #         actual_rename = {k: v for k, v in rename_map.items() if k in master_df.columns}
# # # # #         master_df.rename(columns=actual_rename, inplace=True)
        
# # # # #         # C. Ensure defaults for missing columns
# # # # #         defaults = {
# # # # #             'vintage_year': 2020, 'isomer_commitment_eur': 0, 
# # # # #             'isomer_ic_date': None, 'lpac_seat': False,
# # # # #             'alt_name_1': None, 'alt_name_2': None
# # # # #         }
# # # # #         for col, val in defaults.items():
# # # # #             if col not in master_df.columns:
# # # # #                 master_df[col] = val
        
# # # # #         # D. Save
# # # # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 
# # # # #                    'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2']
# # # # #         final_funds = master_df[db_cols]
        
# # # # #         final_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
        
# # # # #         # Check count of non-empty alt names
# # # # #         count_alt1 = final_funds['alt_name_1'].notna().sum()
# # # # #         print(f"✅ Loaded {len(final_funds)} Master Funds. (Alt Name 1 Entries: {count_alt1})")
        
# # # # #     except FileNotFoundError:
# # # # #         print("❌ Warning: 'data/isomer_funds.csv' not found.")
# # # # #     except Exception as e:
# # # # #         print(f"❌ Error loading Master Funds: {e}")

# # # # # if __name__ == "__main__":
# # # # #     init_db()
# # # # #     seed_metadata()

# # # # # # import pandas as pd
# # # # # # import sys
# # # # # # import os
# # # # # # from sqlalchemy import text

# # # # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# # # # # # from src.database import init_db, get_engine

# # # # # # def seed_metadata():
# # # # # #     engine = get_engine()
# # # # # #     print("🌱 Seeding Metadata Tables...")

# # # # # #     # 1. URLs
# # # # # #     try:
# # # # # #         urls_df = pd.read_csv("data/company_urls_master.csv")
# # # # # #         urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
# # # # # #         urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # # # #         print(f"✅ Loaded {len(urls_df)} URLs.")
# # # # # #     except FileNotFoundError:
# # # # # #         print("❌ Warning: 'company_urls_master.csv' not found.")

# # # # # #     # 2. Name Changes
# # # # # #     try:
# # # # # #         names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
# # # # # #         names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # # # #         print(f"✅ Loaded {len(names_df)} Name Mappings.")
# # # # # #     except FileNotFoundError:
# # # # # #         print("❌ Warning: 'name_change_master.csv' not found.")

# # # # # #     # 3. Tech Tags
# # # # # #     try:
# # # # # #         tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
# # # # # #         tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # # # #         print(f"✅ Loaded {len(tags_df)} Tech Tags.")
# # # # # #     except FileNotFoundError:
# # # # # #         print("❌ Warning: 'tech_tags_master.csv' not found.")

# # # # # #     # 4. Fund Names
# # # # # #     try:
# # # # # #         funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
# # # # # #         funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # # # #         print(f"✅ Loaded {len(funds_df)} Fund Name Cleaners.")
# # # # # #     except FileNotFoundError:
# # # # # #         print("❌ Warning: 'fund_name_changes_master.csv' not found.")

# # # # # #     # --- Step 5. Isomer Master Fund List ---
# # # # # #     try:
# # # # # #         master_df = pd.read_csv("data/isomer_funds.csv")
# # # # # #         master_df.columns = master_df.columns.str.strip()
        
# # # # # #         # Ensure default cols
# # # # # #         defaults = {
# # # # # #             'vintage_year': 2020, 'isomer_commitment_eur': 0, 
# # # # # #             'isomer_ic_date': None, 'lpac_seat': False,
# # # # # #             'alt_name_1': None, 'alt_name_2': None  # <--- NEW DEFAULTS
# # # # # #         }
# # # # # #         for col, val in defaults.items():
# # # # # #             if col not in master_df.columns:
# # # # # #                 master_df[col] = val
        
# # # # # #         # Select valid columns
# # # # # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 
# # # # # #                    'isomer_ic_date', 'lpac_seat', 'alt_name_1', 'alt_name_2']
                   
# # # # # #         final_funds = master_df[db_cols]
# # # # # #         final_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # # # # #         print(f"✅ Loaded {len(final_funds)} Master Funds from data/isomer_funds.csv.")
        
# # # # # #     except FileNotFoundError:
# # # # # #         print("❌ Warning: 'data/isomer_funds.csv' not found (Skipping Master Funds).")
# # # # # #     except Exception as e:
# # # # # #         print(f"❌ Error loading Master Funds: {e}")

# # # # # # if __name__ == "__main__":
# # # # # #     init_db()
# # # # # #     seed_metadata()

# # # # # # # import pandas as pd
# # # # # # # import sys
# # # # # # # import os
# # # # # # # from sqlalchemy import text

# # # # # # # # Add project root to path
# # # # # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# # # # # # # from src.database import init_db, get_engine

# # # # # # # def seed_metadata():
# # # # # # #     engine = get_engine()
# # # # # # #     print("🌱 Seeding Metadata Tables...")

# # # # # # #     # 1. URLs
# # # # # # #     try:
# # # # # # #         urls_df = pd.read_csv("data/company_urls_master.csv")
# # # # # # #         urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
# # # # # # #         urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # # # # #         print(f"✅ Loaded {len(urls_df)} URLs.")
# # # # # # #     except FileNotFoundError:
# # # # # # #         print("❌ Warning: 'company_urls_master.csv' not found.")

# # # # # # #     # 2. Name Changes
# # # # # # #     try:
# # # # # # #         names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
# # # # # # #         names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # # # # #         print(f"✅ Loaded {len(names_df)} Name Mappings.")
# # # # # # #     except FileNotFoundError:
# # # # # # #         print("❌ Warning: 'name_change_master.csv' not found.")

# # # # # # #     # 3. Tech Tags
# # # # # # #     try:
# # # # # # #         tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
# # # # # # #         tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # # # # #         print(f"✅ Loaded {len(tags_df)} Tech Tags.")
# # # # # # #     except FileNotFoundError:
# # # # # # #         print("❌ Warning: 'tech_tags_master.csv' not found.")

# # # # # # #     # 4. Fund Names
# # # # # # #     try:
# # # # # # #         funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
# # # # # # #         funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # # # # #         print(f"✅ Loaded {len(funds_df)} Fund Name Cleaners.")
# # # # # # #     except FileNotFoundError:
# # # # # # #         print("❌ Warning: 'fund_name_changes_master.csv' not found.")

# # # # # # #     # --- Step 5. Isomer Master Fund List ---
# # # # # # #     try:
# # # # # # #         # UPDATED: Pointing to the real master file
# # # # # # #         master_df = pd.read_csv("data/isomer_funds.csv")
        
# # # # # # #         master_df.columns = master_df.columns.str.strip()
        
# # # # # # #         # Ensure default columns exist if the CSV is just a simple mapping list
# # # # # # #         if 'vintage_year' not in master_df.columns: master_df['vintage_year'] = 2020
# # # # # # #         if 'isomer_commitment_eur' not in master_df.columns: master_df['isomer_commitment_eur'] = 0
# # # # # # #         if 'isomer_ic_date' not in master_df.columns: master_df['isomer_ic_date'] = None
# # # # # # #         if 'lpac_seat' not in master_df.columns: master_df['lpac_seat'] = False
            
# # # # # # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat']
        
# # # # # # #         # Only keep columns that actually exist (intersection)
# # # # # # #         available_cols = [c for c in db_cols if c in master_df.columns]
# # # # # # #         final_funds = master_df[available_cols]
        
# # # # # # #         final_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # # # # # #         print(f"✅ Loaded {len(final_funds)} Master Funds from data/isomer_funds.csv.")
        
# # # # # # #     except FileNotFoundError:
# # # # # # #         print("❌ Warning: 'data/isomer_funds.csv' not found (Skipping Master Funds).")
# # # # # # #     except Exception as e:
# # # # # # #         print(f"❌ Error loading Master Funds: {e}")

# # # # # # # if __name__ == "__main__":
# # # # # # #     init_db()
# # # # # # #     seed_metadata()

# # # # # # # # import pandas as pd
# # # # # # # # import sys
# # # # # # # # import os
# # # # # # # # from sqlalchemy import text

# # # # # # # # # Add project root to path
# # # # # # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# # # # # # # # from src.database import init_db, get_engine

# # # # # # # # def seed_metadata():
# # # # # # # #     engine = get_engine()
# # # # # # # #     print("🌱 Seeding Metadata Tables...")

# # # # # # # #     # 1. URLs (Has Header: LPA Num, Organization URL)
# # # # # # # #     try:
# # # # # # # #         urls_df = pd.read_csv("data/company_urls_master.csv")
# # # # # # # #         # Rename to match DB columns
# # # # # # # #         urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
# # # # # # # #         urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # # # # # #         print(f"✅ Loaded {len(urls_df)} URLs.")
# # # # # # # #     except FileNotFoundError:
# # # # # # # #         print("❌ Warning: 'company_urls_master.csv' not found (Skipping URLs).")

# # # # # # # #     # 2. Name Changes (No Header, Col 0 = original, Col 1 = new)
# # # # # # # #     try:
# # # # # # # #         names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
# # # # # # # #         names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # # # # # #         print(f"✅ Loaded {len(names_df)} Name Mappings.")
# # # # # # # #     except FileNotFoundError:
# # # # # # # #         print("❌ Warning: 'name_change_master.csv' not found (Skipping Names).")

# # # # # # # #     # 3. Tech Tags (No Header)
# # # # # # # #     try:
# # # # # # # #         tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
# # # # # # # #         tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # # # # # #         print(f"✅ Loaded {len(tags_df)} Tech Tags.")
# # # # # # # #     except FileNotFoundError:
# # # # # # # #         print("❌ Warning: 'tech_tags_master.csv' not found (Skipping Tags).")

# # # # # # # #     # 4. Fund Name Cleaning (No Header)
# # # # # # # #     try:
# # # # # # # #         funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
# # # # # # # #         funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # # # # # #         print(f"✅ Loaded {len(funds_df)} Fund Name Cleaners.")
# # # # # # # #     except FileNotFoundError:
# # # # # # # #         print("❌ Warning: 'fund_name_changes_master.csv' not found (Skipping Fund Name Cleaning).")

# # # # # # # #     # --- NEW: Step 5. Isomer Master Fund List ---
# # # # # # # #     # This populates the 'isomer_funds' table used for the merge lookup
# # # # # # # #     try:
# # # # # # # #         # Load your specific file
# # # # # # # #         master_df = pd.read_csv("isomer_funds_no_commit.csv")
        
# # # # # # # #         # 1. Normalize Columns (strip whitespace from headers)
# # # # # # # #         master_df.columns = master_df.columns.str.strip()
        
# # # # # # # #         # 2. Add default values for the database schema
# # # # # # # #         # (The CSV has names, but the DB needs these extra columns to exist)
# # # # # # # #         if 'vintage_year' not in master_df.columns:
# # # # # # # #             master_df['vintage_year'] = 2020
# # # # # # # #         if 'isomer_commitment_eur' not in master_df.columns:
# # # # # # # #             master_df['isomer_commitment_eur'] = 0
# # # # # # # #         if 'isomer_ic_date' not in master_df.columns:
# # # # # # # #             master_df['isomer_ic_date'] = None
# # # # # # # #         if 'lpac_seat' not in master_df.columns:
# # # # # # # #             master_df['lpac_seat'] = False
            
# # # # # # # #         # 3. Select only the columns that match the DB table
# # # # # # # #         db_cols = ['fund_name', 'isomer_fund', 'vintage_year', 'isomer_commitment_eur', 'isomer_ic_date', 'lpac_seat']
# # # # # # # #         final_funds = master_df[db_cols]
        
# # # # # # # #         # 4. Save to DB
# # # # # # # #         final_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
# # # # # # # #         print(f"✅ Loaded {len(final_funds)} Master Funds (The Brain).")
        
# # # # # # # #     except FileNotFoundError:
# # # # # # # #         print("❌ Warning: 'isomer_funds_no_commit.csv' not found (Skipping Master Funds).")
# # # # # # # #     except Exception as e:
# # # # # # # #         print(f"❌ Error loading Master Funds: {e}")

# # # # # # # # if __name__ == "__main__":
# # # # # # # #     init_db()
# # # # # # # #     seed_metadata()
# # # # # # # # # import pandas as pd
# # # # # # # # # import sys
# # # # # # # # # import os
# # # # # # # # # from sqlalchemy import text

# # # # # # # # # # Add project root to path
# # # # # # # # # sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# # # # # # # # # from src.database import init_db, get_engine

# # # # # # # # # def seed_metadata():
# # # # # # # # #     engine = get_engine()
# # # # # # # # #     print("🌱 Seeding Metadata Tables...")

# # # # # # # # #     # 1. URLs (Has Header: LPA Num, Organization URL)
# # # # # # # # #     try:
# # # # # # # # #         urls_df = pd.read_csv("data/company_urls_master.csv")
# # # # # # # # #         # Rename to match DB columns
# # # # # # # # #         urls_df.rename(columns={'LPA Num': 'lpa_num', 'Organization URL': 'url'}, inplace=True)
# # # # # # # # #         urls_df.to_sql('meta_urls', engine, if_exists='replace', index=False)
# # # # # # # # #         print(f"✅ Loaded {len(urls_df)} URLs.")
# # # # # # # # #     except FileNotFoundError:
# # # # # # # # #         print("❌ Warning: 'company_urls_master.csv' not found.")

# # # # # # # # #     # 2. Name Changes (No Header, Col 0 = original, Col 1 = new)
# # # # # # # # #     try:
# # # # # # # # #         names_df = pd.read_csv("data/name_change_master.csv", header=None, names=['original_name', 'new_name'])
# # # # # # # # #         names_df.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
# # # # # # # # #         print(f"✅ Loaded {len(names_df)} Name Mappings.")
# # # # # # # # #     except FileNotFoundError:
# # # # # # # # #         print("❌ Warning: 'name_change_master.csv' not found.")

# # # # # # # # #     # 3. Tech Tags (No Header)
# # # # # # # # #     try:
# # # # # # # # #         tags_df = pd.read_csv("data/tech_tags_master.csv", header=None, names=['original_tag', 'cleaned_tag'])
# # # # # # # # #         tags_df.to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
# # # # # # # # #         print(f"✅ Loaded {len(tags_df)} Tech Tags.")
# # # # # # # # #     except FileNotFoundError:
# # # # # # # # #         print("❌ Warning: 'tech_tags_master.csv' not found.")

# # # # # # # # #     # 4. Fund Names (No Header)
# # # # # # # # #     try:
# # # # # # # # #         funds_df = pd.read_csv("data/fund_name_changes_master.csv", header=None, names=['original_fund', 'cleaned_fund'])
# # # # # # # # #         funds_df.to_sql('meta_fund_names', engine, if_exists='replace', index=False)
# # # # # # # # #         print(f"✅ Loaded {len(funds_df)} Fund Name Mappings.")
# # # # # # # # #     except FileNotFoundError:
# # # # # # # # #         print("❌ Warning: 'fund_name_changes_master.csv' not found.")

# # # # # # # # # if __name__ == "__main__":
# # # # # # # # #     init_db()
# # # # # # # # #     seed_metadata()