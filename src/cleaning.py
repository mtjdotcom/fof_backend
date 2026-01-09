import pandas as pd
import numpy as np
import re
from difflib import get_close_matches

# Constants
BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
             ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
             ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
             ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']
URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']
BUSINESS_MODEL_MAP = {"Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"}
REGION_MAP = {"MENA": "Europe"}

def parse_hybrid_date(series):
    numeric_dates = pd.to_numeric(series, errors='coerce')
    dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
    dates_from_strings = pd.to_datetime(series, errors='coerce')
    return dates_from_excel.combine_first(dates_from_strings)

def fuzzy_match_funds(df, master_funds, threshold=0.90):
    """
    Tiered Fuzzy Matching: Returns ['matched_isomer_fund', 'matched_deal_type']
    """
    print("   ...Running Tiered Fuzzy Matching (With Deal Types)...")
    
    raw_names = df['Fund Name'].unique()
    mapping_fund = {}
    mapping_type = {}

    def prepare_lookup(col_name):
        if col_name not in master_funds.columns: return {}, []
        subset = master_funds.dropna(subset=[col_name]).copy()
        # Create Dict: Key -> (Isomer Fund, Deal Type)
        lookup = dict(zip(
            subset[col_name].astype(str).str.lower().str.strip(), 
            zip(subset['isomer_fund'], subset['default_deal_type'])
        ))
        return lookup, list(lookup.keys())

    lookup_main, names_main = prepare_lookup('fund_name')
    lookup_alt1, names_alt1 = prepare_lookup('alt_name_1')
    lookup_alt2, names_alt2 = prepare_lookup('alt_name_2')

    for name in raw_names:
        if pd.isna(name): continue
        clean_name = str(name).strip().lower()
        
        def try_match(target_names_list, lookup_map):
            if not target_names_list: return None
            if clean_name in lookup_map: return lookup_map[clean_name]
            matches = get_close_matches(clean_name, target_names_list, n=1, cutoff=threshold)
            if matches: return lookup_map[matches[0]]
            return None

        found = try_match(names_main, lookup_main) or \
                try_match(names_alt1, lookup_alt1) or \
                try_match(names_alt2, lookup_alt2)
        
        if found:
            mapping_fund[name] = found[0]
            mapping_type[name] = found[1]

    result = pd.DataFrame(index=df.index)
    result['matched_isomer_fund'] = df['Fund Name'].map(mapping_fund)
    result['matched_deal_type'] = df['Fund Name'].map(mapping_type)
    return result

def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
    print("--- STARTING CLEANING ---")
    
    # 1. Label and Concatenate
    df_list = []
    for fund_name, df in files_dict.items():
        temp_df = df.copy()
        temp_df['Isomer Fund'] = fund_name
        df_list.append(temp_df)
    
    dfc = pd.concat(df_list, ignore_index=True)

    # 2. Basic Cleaning
    for char in BAD_CHARS:
        dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
    mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
    dfc = dfc[~mask_rag_overlap]

    if 'Company Name' in dfc.columns: dfc.drop(columns=['Company Name'], inplace=True)
    rename_map = {
        'LP Analyst Identifier':'LPA Num', 'Company Short Name':'Company Name',
        'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
        'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
        'Client - Realized Value (Base Currency)': "Distributions EUR",
        'Client - Multiple (Base Currency)': "Multiple", 'Company Status': "Status",
        'LP Analyst - Industry': "LP Analyst - Industry", 'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
    }
    for old, new in rename_map.items():
        if old in dfc.columns: dfc.rename(columns={old: new}, inplace=True)
    
    num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
    for col in num_cols:
        if col not in dfc.columns: dfc[col] = 0.0
        dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)
    
    if 'names' in metadata: dfc['Company Name'] = dfc['Company Name'].replace(dict(zip(metadata['names']['original_name'], metadata['names']['new_name'])))
    if 'tags' in metadata: dfc['Technology Tag'] = dfc['Technology Tag'].replace(dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag'])))
    
    # --- 5b. MASTER LOOKUP ---
    if 'master_funds' in metadata and not metadata['master_funds'].empty:
        mf = metadata['master_funds'].copy()
        
        # Fuzzy Match
        fuzzy_results = fuzzy_match_funds(dfc, mf, threshold=0.90)
        
        dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
        dfc['Isomer Fund'] = fuzzy_results['matched_isomer_fund'].fillna(dfc['File Source'])
        
        # Deal Type Application
        dfc['Deal Type'] = fuzzy_results['matched_deal_type'].fillna('Unknown')
        
        # Derived Flags
        # Important: This catches "Direct Secondary" AND "LP Secondary"
        dfc['Is Secondary'] = dfc['Deal Type'].str.contains('Secondary', case=False, na=False)
        dfc['Is CoInvest'] = dfc['Deal Type'].str.contains('Co-Invest', case=False, na=False)
        
        if 'File Source' in dfc.columns: dfc.drop(columns=['File Source'], inplace=True)

    # 5. URL Merge
    if 'urls' in metadata:
        urls_df = metadata['urls'].copy()
        urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
        urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        for char in URL_CHARS: urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

    # 6. Calc Metrics
    dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
    dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

    if 'Initial Investment Date' in dfc.columns:
        dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
        dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
        dfc['Invest Quarter'] = dfc['Initial Investment Date'].dt.quarter.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

    if 'Data as of Date' in dfc.columns:
        dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(lambda d: f"Q{d.quarter} {d.year}" if pd.notnull(d) else None)

    if 'Status' in dfc.columns:
        mask_private = dfc['Status'] == "Private"
        mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0)
        dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"

    return dfc

# import pandas as pd
# import numpy as np
# import re
# from difflib import get_close_matches

# # Constants
# BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
#              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
#              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
#              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# BUSINESS_MODEL_MAP = {
#     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# }
# REGION_MAP = {"MENA": "Europe"}

# def parse_hybrid_date(series):
#     numeric_dates = pd.to_numeric(series, errors='coerce')
#     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
#     dates_from_strings = pd.to_datetime(series, errors='coerce')
#     return dates_from_excel.combine_first(dates_from_strings)

# def fuzzy_match_funds(df, master_funds, threshold=0.90):
#     """
#     Tiered Fuzzy Matching (Case-Insensitive)
#     1. Fund Name -> 2. Alt Name 1 -> 3. Alt Name 2
#     """
#     print("   ...Running Tiered Fuzzy Matching (Case-Insensitive)...")
    
#     # Debug: Verify columns exist
#     if 'alt_name_1' in master_funds.columns:
#         print(f"   DEBUG: 'alt_name_1' is loaded with {master_funds['alt_name_1'].notna().sum()} entries.")
#     else:
#         print("   DEBUG: 'alt_name_1' column is MISSING in Master Funds.")

#     raw_names = df['Fund Name'].unique()
#     mapping = {}

#     # Helper to prepare lookup dicts (normalized keys)
#     def prepare_lookup(col_name):
#         if col_name not in master_funds.columns: return {}, []
#         subset = master_funds.dropna(subset=[col_name]).copy()
        
#         # Create a dict: { lower_case_name : isomer_fund }
#         # We assume the name in the DB is the "clean" one we want to match against
#         lookup = dict(zip(subset[col_name].astype(str).str.lower().str.strip(), subset['isomer_fund']))
        
#         # List of lower-case names for the fuzzy matcher
#         targets = list(lookup.keys())
#         return lookup, targets

#     lookup_main, names_main = prepare_lookup('fund_name')
#     lookup_alt1, names_alt1 = prepare_lookup('alt_name_1')
#     lookup_alt2, names_alt2 = prepare_lookup('alt_name_2')

#     for name in raw_names:
#         if pd.isna(name): continue
        
#         # NORMALIZE RAW NAME (Lower case + Strip)
#         clean_name = str(name).strip().lower()
        
#         # Helper: Try to match against a specific list
#         def try_match(target_names_list, lookup_map):
#             if not target_names_list: return None
            
#             # A. Exact Match (Fast)
#             if clean_name in lookup_map:
#                 return lookup_map[clean_name]
            
#             # B. Fuzzy Match (Slower)
#             matches = get_close_matches(clean_name, target_names_list, n=1, cutoff=threshold)
#             if matches:
#                 # matches[0] is the lower-case key from our lookup map
#                 return lookup_map[matches[0]]
#             return None

#         # --- TIER 1: Main Fund Name ---
#         found = try_match(names_main, lookup_main)
#         if found:
#             mapping[name] = found
#             continue 

#         # --- TIER 2: Alt Name 1 ---
#         found = try_match(names_alt1, lookup_alt1)
#         if found:
#             mapping[name] = found
#             continue 

#         # --- TIER 3: Alt Name 2 ---
#         found = try_match(names_alt2, lookup_alt2)
#         if found:
#             mapping[name] = found
#             continue 

#     # Apply mapping
#     df['matched_isomer_fund'] = df['Fund Name'].map(mapping)
#     return df['matched_isomer_fund']

# def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
#     print("--- STARTING CLEANING ---")
    
#     # 1. Label and Concatenate
#     df_list = []
#     for fund_name, df in files_dict.items():
#         temp_df = df.copy()
#         temp_df['Isomer Fund'] = fund_name
#         df_list.append(temp_df)
    
#     dfc = pd.concat(df_list, ignore_index=True)

#     # 2. Basic Regex Cleaning
#     for char in BAD_CHARS:
#         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
#     # 3. RAG Exclusion Logic
#     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
#     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
#     dfc = dfc[~mask_rag_overlap]

#     # 4. Column Selection & Renaming
#     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
#         dfc.drop(columns=['Company Name'], inplace=True)

#     rename_map = {
#         'LP Analyst Identifier':'LPA Num',
#         'Company Short Name':'Company Name',
#         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
#         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
#         'Client - Realized Value (Base Currency)': "Distributions EUR",
#         'Client - Realized (Base Currency)': "Distributions EUR", 
#         'Client - Multiple (Base Currency)': "Multiple",
#         'Current Multiple (Base Currency)': "Multiple",
#         'Company Status': "Status",
#         'LP Analyst - Industry': "LP Analyst - Industry",
#         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
#     }
    
#     for old, new in rename_map.items():
#         if old in dfc.columns:
#             dfc.rename(columns={old: new}, inplace=True)

#     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
#     for col in num_cols:
#         if col not in dfc.columns: dfc[col] = 0.0
#         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

#     # 5. Metadata Mapping
#     if 'names' in metadata and not metadata['names'].empty:
#         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
#         if 'Company Name' in dfc.columns:
#             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

#     if 'funds' in metadata and not metadata['funds'].empty:
#         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
#         if 'Fund Name' in dfc.columns:
#             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

#     if 'tags' in metadata and not metadata['tags'].empty:
#         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
#         if 'Technology Tag' in dfc.columns:
#             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
#     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
#     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

#     # --- 5b. MASTER LOOKUP: TIERED FUZZY MATCHING ---
#     if 'master_funds' in metadata and not metadata['master_funds'].empty:
#         mf = metadata['master_funds'].copy()
        
#         # Run tiered fuzzy logic
#         fuzzy_results = fuzzy_match_funds(dfc, mf, threshold=0.90)
        
#         # Backup Original Source
#         dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
        
#         # Fill results
#         dfc['Isomer Fund'] = fuzzy_results.fillna(dfc['File Source'])
        
#         matched_count = fuzzy_results.notna().sum()
#         print(f"DEBUG: Tiered Fuzzy Match found {matched_count} rows out of {len(dfc)}.")
        
#         if 'File Source' in dfc.columns:
#             dfc.drop(columns=['File Source'], inplace=True)
#     else:
#         print("DEBUG: 'master_funds' metadata is MISSING. Skipping lookup.")
#     # ------------------------------------------------

#     # 6. Merge URLs
#     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
#         urls_df = metadata['urls'].copy()
#         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
#         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
#         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
#         for char in URL_CHARS:
#              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
#         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

#     # 7. Mode Specific Logic
#     if mode == 'rollup':
#         agg_rules = {
#             "Fund Name": lambda x: ', '.join(set(x.dropna())),
#             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
#             "Cost in Isomer's Share EUR": 'sum',
#             "Valuation of Isomer's Share EUR": 'sum',
#             "Distributions EUR": 'sum',
#             "Company Name": 'first',
#             "Initial Investment Date": 'first',
#             "Data as of Date": 'first',
#             "Status": 'first', "Country": 'first', "URL": 'first'
#         }
#         for c in dfc.columns:
#             if c not in agg_rules and c != 'LPA Num':
#                 agg_rules[c] = 'first'
#         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

#     # 8. Final Metrics
#     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
#     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

#     # 9. Dates Parsing
#     if 'Initial Investment Date' in dfc.columns:
#         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
#         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
#         quarter_num = dfc['Initial Investment Date'].dt.quarter
#         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

#     if 'Data as of Date' in dfc.columns:
#         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
#         def format_report_quarter(d):
#             if pd.isnull(d): return None
#             return f"Q{d.quarter} {d.year}"
#         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

#     # 10. Status Logic
#     if 'Status' in dfc.columns:
#         mask_private = dfc['Status'] == "Private"
#         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
#         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
#         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
#         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

#     return dfc

# # import pandas as pd
# # import numpy as np
# # import re
# # from difflib import get_close_matches

# # # Constants
# # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # BUSINESS_MODEL_MAP = {
# #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # }
# # REGION_MAP = {"MENA": "Europe"}

# # def parse_hybrid_date(series):
# #     numeric_dates = pd.to_numeric(series, errors='coerce')
# #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# #     return dates_from_excel.combine_first(dates_from_strings)

# # def fuzzy_match_funds(df, master_funds, threshold=0.92):
# #     """
# #     Tiered Fuzzy Matching:
# #     1. Check 'fund_name'
# #     2. Check 'alt_name_1'
# #     3. Check 'alt_name_2'
# #     """
# #     print("   ...Running Tiered Fuzzy Matching...")
    
# #     raw_names = df['Fund Name'].unique()
# #     mapping = {}

# #     # 1. Prepare Lookup Dictionaries for each column
# #     # Helper to create lookups (Name -> Isomer Fund)
# #     def create_lookup(col_name):
# #         if col_name not in master_funds.columns: return {}, []
# #         subset = master_funds.dropna(subset=[col_name])
# #         return dict(zip(subset[col_name], subset['isomer_fund'])), subset[col_name].astype(str).unique()

# #     lookup_main, names_main = create_lookup('fund_name')
# #     lookup_alt1, names_alt1 = create_lookup('alt_name_1')
# #     lookup_alt2, names_alt2 = create_lookup('alt_name_2')

# #     # 2. Iterate through every raw fund name
# #     for name in raw_names:
# #         if pd.isna(name): continue
# #         clean_name = str(name).strip()
        
# #         # Helper: Try to match against a specific list
# #         def try_match(target_names, lookup_map):
# #             # A. Exact Match (Fast)
# #             if clean_name in target_names:
# #                 return lookup_map[clean_name]
# #             # B. Fuzzy Match (Slower)
# #             matches = get_close_matches(clean_name, target_names, n=1, cutoff=threshold)
# #             if matches:
# #                 return lookup_map[matches[0]]
# #             return None

# #         # --- TIER 1: Main Fund Name ---
# #         found = try_match(names_main, lookup_main)
# #         if found:
# #             mapping[name] = found
# #             continue # Success! Move to next fund

# #         # --- TIER 2: Alt Name 1 ---
# #         if len(names_alt1) > 0:
# #             found = try_match(names_alt1, lookup_alt1)
# #             if found:
# #                 mapping[name] = found
# #                 continue # Success!

# #         # --- TIER 3: Alt Name 2 ---
# #         if len(names_alt2) > 0:
# #             found = try_match(names_alt2, lookup_alt2)
# #             if found:
# #                 mapping[name] = found
# #                 continue # Success!

# #     # 3. Apply the mapping
# #     # Map raw names to the found Isomer Fund
# #     df['matched_isomer_fund'] = df['Fund Name'].map(mapping)
# #     return df['matched_isomer_fund']

# # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# #     print("--- STARTING CLEANING ---")
    
# #     # 1. Label and Concatenate
# #     df_list = []
# #     for fund_name, df in files_dict.items():
# #         temp_df = df.copy()
# #         temp_df['Isomer Fund'] = fund_name
# #         df_list.append(temp_df)
    
# #     dfc = pd.concat(df_list, ignore_index=True)

# #     # 2. Basic Regex Cleaning
# #     for char in BAD_CHARS:
# #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# #     # 3. RAG Exclusion Logic
# #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# #     dfc = dfc[~mask_rag_overlap]

# #     # 4. Column Selection & Renaming
# #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# #         dfc.drop(columns=['Company Name'], inplace=True)

# #     rename_map = {
# #         'LP Analyst Identifier':'LPA Num',
# #         'Company Short Name':'Company Name',
# #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# #         'Client - Realized (Base Currency)': "Distributions EUR", 
# #         'Client - Multiple (Base Currency)': "Multiple",
# #         'Current Multiple (Base Currency)': "Multiple",
# #         'Company Status': "Status",
# #         'LP Analyst - Industry': "LP Analyst - Industry",
# #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# #     }
    
# #     for old, new in rename_map.items():
# #         if old in dfc.columns:
# #             dfc.rename(columns={old: new}, inplace=True)

# #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# #     for col in num_cols:
# #         if col not in dfc.columns: dfc[col] = 0.0
# #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# #     # 5. Metadata Mapping
# #     if 'names' in metadata and not metadata['names'].empty:
# #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# #         if 'Company Name' in dfc.columns:
# #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# #     if 'funds' in metadata and not metadata['funds'].empty:
# #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# #         if 'Fund Name' in dfc.columns:
# #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# #     if 'tags' in metadata and not metadata['tags'].empty:
# #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# #         if 'Technology Tag' in dfc.columns:
# #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# #     # --- 5b. MASTER LOOKUP: TIERED FUZZY MATCHING ---
# #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# #         mf = metadata['master_funds'].copy()
        
# #         # Run the new tiered function
# #         fuzzy_results = fuzzy_match_funds(dfc, mf, threshold=0.92)
        
# #         # Backup and Apply
# #         dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
# #         dfc['Isomer Fund'] = fuzzy_results.fillna(dfc['File Source'])
        
# #         matched_count = fuzzy_results.notna().sum()
# #         print(f"DEBUG: Tiered Fuzzy Match found {matched_count} rows out of {len(dfc)}.")
        
# #         if 'File Source' in dfc.columns:
# #             dfc.drop(columns=['File Source'], inplace=True)
# #     else:
# #         print("DEBUG: 'master_funds' metadata is MISSING. Skipping lookup.")
# #     # ------------------------------------------------

# #     # 6. Merge URLs
# #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# #         urls_df = metadata['urls'].copy()
# #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
# #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
# #         for char in URL_CHARS:
# #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
# #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# #     # 7. Mode Specific Logic
# #     if mode == 'rollup':
# #         agg_rules = {
# #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# #             "Cost in Isomer's Share EUR": 'sum',
# #             "Valuation of Isomer's Share EUR": 'sum',
# #             "Distributions EUR": 'sum',
# #             "Company Name": 'first',
# #             "Initial Investment Date": 'first',
# #             "Data as of Date": 'first',
# #             "Status": 'first', "Country": 'first', "URL": 'first'
# #         }
# #         for c in dfc.columns:
# #             if c not in agg_rules and c != 'LPA Num':
# #                 agg_rules[c] = 'first'
# #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# #     # 8. Final Metrics
# #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# #     # 9. Dates Parsing
# #     if 'Initial Investment Date' in dfc.columns:
# #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# #     if 'Data as of Date' in dfc.columns:
# #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# #         def format_report_quarter(d):
# #             if pd.isnull(d): return None
# #             return f"Q{d.quarter} {d.year}"
# #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# #     # 10. Status Logic
# #     if 'Status' in dfc.columns:
# #         mask_private = dfc['Status'] == "Private"
# #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
# #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
# #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# #     return dfc

# # # import pandas as pd
# # # import numpy as np
# # # import re
# # # from difflib import get_close_matches

# # # # Constants
# # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # BUSINESS_MODEL_MAP = {
# # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # }
# # # REGION_MAP = {"MENA": "Europe"}

# # # def parse_hybrid_date(series):
# # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # #     return dates_from_excel.combine_first(dates_from_strings)

# # # def fuzzy_match_funds(df, master_funds, threshold=0.92):
# # #     """
# # #     Matches raw fund names to master list using fuzzy logic.
# # #     """
# # #     print("   ...Running Fuzzy Matching on Fund Names...")
    
# # #     # 1. Get unique names from both sides
# # #     raw_names = df['Fund Name'].unique()
# # #     master_names = master_funds['fund_name'].unique()
    
# # #     # 2. Build a Dictionary: {Raw Name -> Matched Master Name}
# # #     mapping = {}
    
# # #     for name in raw_names:
# # #         if pd.isna(name): continue
        
# # #         # Clean string for comparison (lowercase, strip)
# # #         clean_name = str(name).strip()
        
# # #         # Exact match check first (Fastest)
# # #         if clean_name in master_names:
# # #             mapping[name] = clean_name
# # #             continue
            
# # #         # Fuzzy Match
# # #         # get_close_matches returns list of matches ordered by similarity.
# # #         # cutoff=0.92 means 92% similarity required.
# # #         matches = get_close_matches(clean_name, master_names, n=1, cutoff=threshold)
        
# # #         if matches:
# # #             mapping[name] = matches[0] # Take the best match
# # #             # Optional: Print matches to verify
# # #             # print(f"   Matched: '{name}' -> '{matches[0]}'")
            
# # #     # 3. Create the Lookup Series
# # #     # Map the Raw Name -> Master Name -> Isomer Fund
    
# # #     # First, turn the name mapping into a dataframe or series
# # #     name_map_series = pd.Series(mapping, name='matched_name')
    
# # #     # Second, merge the original dataframe with this map
# # #     df = df.merge(name_map_series, left_on='Fund Name', right_index=True, how='left')
    
# # #     # Third, map the 'matched_name' to the 'isomer_fund' using the master table
# # #     master_lookup = dict(zip(master_funds['fund_name'], master_funds['isomer_fund']))
# # #     df['fuzzy_isomer_fund'] = df['matched_name'].map(master_lookup)
    
# # #     return df['fuzzy_isomer_fund']

# # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # #     print("--- STARTING CLEANING ---")
    
# # #     # 1. Label and Concatenate
# # #     df_list = []
# # #     for fund_name, df in files_dict.items():
# # #         temp_df = df.copy()
# # #         temp_df['Isomer Fund'] = fund_name
# # #         df_list.append(temp_df)
    
# # #     dfc = pd.concat(df_list, ignore_index=True)

# # #     # 2. Basic Regex Cleaning
# # #     for char in BAD_CHARS:
# # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # #     # 3. RAG Exclusion Logic
# # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # #     dfc = dfc[~mask_rag_overlap]

# # #     # 4. Column Selection & Renaming
# # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # #         dfc.drop(columns=['Company Name'], inplace=True)

# # #     rename_map = {
# # #         'LP Analyst Identifier':'LPA Num',
# # #         'Company Short Name':'Company Name',
# # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # #         'Client - Multiple (Base Currency)': "Multiple",
# # #         'Current Multiple (Base Currency)': "Multiple",
# # #         'Company Status': "Status",
# # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # #     }
    
# # #     for old, new in rename_map.items():
# # #         if old in dfc.columns:
# # #             dfc.rename(columns={old: new}, inplace=True)

# # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # #     for col in num_cols:
# # #         if col not in dfc.columns: dfc[col] = 0.0
# # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # #     # 5. Metadata Mapping
# # #     if 'names' in metadata and not metadata['names'].empty:
# # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # #         if 'Company Name' in dfc.columns:
# # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # #     if 'funds' in metadata and not metadata['funds'].empty:
# # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # #         if 'Fund Name' in dfc.columns:
# # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # #     if 'tags' in metadata and not metadata['tags'].empty:
# # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # #         if 'Technology Tag' in dfc.columns:
# # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # #     # --- 5b. MASTER LOOKUP: FUZZY MATCHING ---
# # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # #         mf = metadata['master_funds'].copy()
# # #         print(f"DEBUG: Master Funds table has {len(mf)} rows.")
        
# # #         # Call the fuzzy matcher
# # #         # This returns a Series of correct Isomer Funds (aligned with dfc index)
# # #         fuzzy_results = fuzzy_match_funds(dfc, mf, threshold=0.90) # slightly relaxed to 0.90 for better catching
        
# # #         # Create 'File Source' backup
# # #         dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
        
# # #         # Apply the fuzzy results
# # #         # If fuzzy match found something, use it. If not, fallback to File Source.
# # #         dfc['Isomer Fund'] = fuzzy_results.fillna(dfc['File Source'])
        
# # #         matched_count = fuzzy_results.notna().sum()
# # #         print(f"DEBUG: Fuzzy Match found {matched_count} rows out of {len(dfc)}.")
        
# # #         # Cleanup
# # #         if 'File Source' in dfc.columns:
# # #             dfc.drop(columns=['File Source'], inplace=True)
# # #     else:
# # #         print("DEBUG: 'master_funds' metadata is MISSING or EMPTY. Skipping lookup.")
# # #     # --------------------------------------------------------

# # #     # 6. Merge URLs
# # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # #         urls_df = metadata['urls'].copy()
# # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # #         for char in URL_CHARS:
# # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # #     # 7. Mode Specific Logic
# # #     if mode == 'rollup':
# # #         agg_rules = {
# # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # #             "Cost in Isomer's Share EUR": 'sum',
# # #             "Valuation of Isomer's Share EUR": 'sum',
# # #             "Distributions EUR": 'sum',
# # #             "Company Name": 'first',
# # #             "Initial Investment Date": 'first',
# # #             "Data as of Date": 'first',
# # #             "Status": 'first', 
# # #             "Country": 'first',
# # #             "URL": 'first'
# # #         }
# # #         for c in dfc.columns:
# # #             if c not in agg_rules and c != 'LPA Num':
# # #                 agg_rules[c] = 'first'
# # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # #     # 8. Final Metrics
# # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # #     # 9. Dates Parsing
# # #     if 'Initial Investment Date' in dfc.columns:
# # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # #     if 'Data as of Date' in dfc.columns:
# # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# # #         def format_report_quarter(d):
# # #             if pd.isnull(d): return None
# # #             return f"Q{d.quarter} {d.year}"
# # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # #     # 10. Status Logic
# # #     if 'Status' in dfc.columns:
# # #         mask_private = dfc['Status'] == "Private"
# # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
# # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
# # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # #     return dfc

# # # # import pandas as pd
# # # # import numpy as np
# # # # import re

# # # # # Constants
# # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # BUSINESS_MODEL_MAP = {
# # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # }
# # # # REGION_MAP = {"MENA": "Europe"}

# # # # def parse_hybrid_date(series):
# # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # #     print("--- STARTING CLEANING ---")
    
# # # #     # 1. Label and Concatenate
# # # #     df_list = []
# # # #     for fund_name, df in files_dict.items():
# # # #         temp_df = df.copy()
# # # #         temp_df['Isomer Fund'] = fund_name
# # # #         df_list.append(temp_df)
    
# # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # #     # 2. Basic Regex Cleaning
# # # #     for char in BAD_CHARS:
# # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # #     # 3. RAG Exclusion Logic
# # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # #     dfc = dfc[~mask_rag_overlap]

# # # #     # 4. Column Selection & Renaming
# # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # #     rename_map = {
# # # #         'LP Analyst Identifier':'LPA Num',
# # # #         'Company Short Name':'Company Name',
# # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # #         'Current Multiple (Base Currency)': "Multiple",
# # # #         'Company Status': "Status",
# # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # #     }
    
# # # #     for old, new in rename_map.items():
# # # #         if old in dfc.columns:
# # # #             dfc.rename(columns={old: new}, inplace=True)

# # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # #     for col in num_cols:
# # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # #     # 5. Metadata Mapping
# # # #     if 'names' in metadata and not metadata['names'].empty:
# # # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # #         if 'Company Name' in dfc.columns:
# # # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # # #     if 'funds' in metadata and not metadata['funds'].empty:
# # # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # #         if 'Fund Name' in dfc.columns:
# # # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # # #     if 'tags' in metadata and not metadata['tags'].empty:
# # # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # # #         if 'Technology Tag' in dfc.columns:
# # # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # #     # --- 5b. MASTER LOOKUP: Normalization + Merge ---
# # # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # # #         mf = metadata['master_funds'].copy()
        
# # # #         # DEBUG: Print what we have
# # # #         print(f"DEBUG: Master Funds table has {len(mf)} rows.")
# # # #         print(f"DEBUG: Data has {len(dfc)} rows.")

# # # #         # NORMALIZE KEYS (Strip whitespace + Lowercase) to ensure match
# # # #         dfc['join_key'] = dfc['Fund Name'].astype(str).str.strip().str.lower()
# # # #         mf['join_key'] = mf['fund_name'].astype(str).str.strip().str.lower()
        
# # # #         # Rename old column to keep as backup
# # # #         dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
        
# # # #         # MERGE
# # # #         dfc = dfc.merge(
# # # #             mf[['join_key', 'isomer_fund']], 
# # # #             on='join_key', 
# # # #             how='left'
# # # #         )
        
# # # #         # CHECK MATCHES
# # # #         matched_count = dfc['isomer_fund'].notna().sum()
# # # #         print(f"DEBUG: Successfully matched {matched_count} rows out of {len(dfc)}.")
        
# # # #         # FILL FALLBACK
# # # #         dfc['isomer_fund'] = dfc['isomer_fund'].fillna(dfc['File Source'])
        
# # # #         # Restore Name
# # # #         dfc.rename(columns={'isomer_fund': 'Isomer Fund'}, inplace=True)
        
# # # #         # Cleanup
# # # #         dfc.drop(columns=['join_key', 'File Source'], inplace=True, errors='ignore')
# # # #     else:
# # # #         print("DEBUG: 'master_funds' metadata is MISSING or EMPTY. Skipping lookup.")
# # # #     # --------------------------------------------------------

# # # #     # 6. Merge URLs
# # # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # #         urls_df = metadata['urls'].copy()
# # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # #         for char in URL_CHARS:
# # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # #     # 7. Mode Specific Logic
# # # #     if mode == 'rollup':
# # # #         agg_rules = {
# # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # #             "Cost in Isomer's Share EUR": 'sum',
# # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # #             "Distributions EUR": 'sum',
# # # #             "Company Name": 'first',
# # # #             "Initial Investment Date": 'first',
# # # #             "Data as of Date": 'first',
# # # #             "Status": 'first', 
# # # #             "Country": 'first',
# # # #             "URL": 'first'
# # # #         }
# # # #         for c in dfc.columns:
# # # #             if c not in agg_rules and c != 'LPA Num':
# # # #                 agg_rules[c] = 'first'
# # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # #     # 8. Final Metrics
# # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # #     # 9. Dates Parsing
# # # #     if 'Initial Investment Date' in dfc.columns:
# # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # #     if 'Data as of Date' in dfc.columns:
# # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# # # #         def format_report_quarter(d):
# # # #             if pd.isnull(d): return None
# # # #             return f"Q{d.quarter} {d.year}"
# # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # # #     # 10. Status Logic
# # # #     if 'Status' in dfc.columns:
# # # #         mask_private = dfc['Status'] == "Private"
# # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
# # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
# # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # #     return dfc

# # # # # import pandas as pd
# # # # # import numpy as np
# # # # # import re

# # # # # # Constants
# # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # BUSINESS_MODEL_MAP = {
# # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # }
# # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # def parse_hybrid_date(series):
# # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # #     """
# # # # #     Robust cleaning function with clean Merge/Join logic for Isomer Funds.
# # # # #     """
# # # # #     # 1. Label and Concatenate
# # # # #     df_list = []
# # # # #     for fund_name, df in files_dict.items():
# # # # #         temp_df = df.copy()
# # # # #         # Initial 'Isomer Fund' is just the filename/source (e.g. "Historic_Dump")
# # # # #         temp_df['Isomer Fund'] = fund_name
# # # # #         df_list.append(temp_df)
    
# # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # #     # 2. Basic Regex Cleaning
# # # # #     for char in BAD_CHARS:
# # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # #     # 3. RAG Exclusion Logic
# # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # #     dfc = dfc[~mask_rag_overlap]

# # # # #     # 4. Column Selection & Renaming
# # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # #     rename_map = {
# # # # #         'LP Analyst Identifier':'LPA Num',
# # # # #         'Company Short Name':'Company Name',
# # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # #         'Company Status': "Status",
# # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # #     }
    
# # # # #     for old, new in rename_map.items():
# # # # #         if old in dfc.columns:
# # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # #     # Ensure numeric financial columns
# # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # #     for col in num_cols:
# # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # #     # 5. Metadata Mapping (Names, Funds, Tags)
# # # # #     if 'names' in metadata and not metadata['names'].empty:
# # # # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # #         if 'Company Name' in dfc.columns:
# # # # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # # # #     if 'funds' in metadata and not metadata['funds'].empty:
# # # # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # #         if 'Fund Name' in dfc.columns:
# # # # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # # # #     if 'tags' in metadata and not metadata['tags'].empty:
# # # # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # # # #         if 'Technology Tag' in dfc.columns:
# # # # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # #     # --- 5b. MASTER LOOKUP: Rename -> Merge -> Fallback ---
# # # # #     # This logic completely replaces the old column with data from the DB
# # # # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # # # #         mf = metadata['master_funds'].copy()
        
# # # # #         # A. Prepare Keys (Strip whitespace to be safe)
# # # # #         dfc['join_key'] = dfc['Fund Name'].astype(str).str.strip()
# # # # #         mf['join_key'] = mf['fund_name'].astype(str).str.strip()
        
# # # # #         # B. Move the old column out of the way
# # # # #         # "Isomer Fund" (e.g. Historic_Dump) becomes "File Source"
# # # # #         dfc.rename(columns={'Isomer Fund': 'File Source'}, inplace=True)
        
# # # # #         # C. Perform the Left Join
# # # # #         # This pulls the official 'isomer_fund' from the database
# # # # #         dfc = dfc.merge(
# # # # #             mf[['join_key', 'isomer_fund']], 
# # # # #             on='join_key', 
# # # # #             how='left'
# # # # #         )
        
# # # # #         # D. Intelligent Fill
# # # # #         # If the DB had a match, we use it. If not (NaN), we fall back to "File Source".
# # # # #         dfc['isomer_fund'] = dfc['isomer_fund'].fillna(dfc['File Source'])
        
# # # # #         # E. Restore Column Name
# # # # #         dfc.rename(columns={'isomer_fund': 'Isomer Fund'}, inplace=True)
        
# # # # #         # F. Cleanup Temps
# # # # #         dfc.drop(columns=['join_key', 'File Source'], inplace=True, errors='ignore')
# # # # #     # --------------------------------------------------------

# # # # #     # 6. Merge URLs
# # # # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # #         urls_df = metadata['urls'].copy()
# # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # #         for char in URL_CHARS:
# # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # #     # 7. Mode Specific Logic
# # # # #     if mode == 'rollup':
# # # # #         agg_rules = {
# # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # #             "Distributions EUR": 'sum',
# # # # #             "Company Name": 'first',
# # # # #             "Initial Investment Date": 'first',
# # # # #             "Data as of Date": 'first',
# # # # #             "Status": 'first', 
# # # # #             "Country": 'first',
# # # # #             "URL": 'first'
# # # # #         }
# # # # #         for c in dfc.columns:
# # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # #                 agg_rules[c] = 'first'

# # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # #     # 8. Final Metrics
# # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # #     # 9. Dates Parsing
# # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # #     if 'Data as of Date' in dfc.columns:
# # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# # # # #         def format_report_quarter(d):
# # # # #             if pd.isnull(d): return None
# # # # #             return f"Q{d.quarter} {d.year}"
# # # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # # # #     # 10. Status Logic
# # # # #     if 'Status' in dfc.columns:
# # # # #         mask_private = dfc['Status'] == "Private"
# # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
# # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
# # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # #     return dfc

# # # # # # import pandas as pd
# # # # # # import numpy as np
# # # # # # import re

# # # # # # # Constants
# # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # BUSINESS_MODEL_MAP = {
# # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # }
# # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # def parse_hybrid_date(series):
# # # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # #     # 1. Label and Concatenate
# # # # # #     df_list = []
# # # # # #     for fund_name, df in files_dict.items():
# # # # # #         temp_df = df.copy()
# # # # # #         # "Isomer Fund" starts as the filename/source (e.g. "Historic_Dump")
# # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # #         df_list.append(temp_df)
    
# # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # #     # 2. Basic Regex Cleaning
# # # # # #     for char in BAD_CHARS:
# # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # #     # 3. RAG Exclusion Logic
# # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # #     # 4. Column Selection & Renaming
# # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # # #     rename_map = {
# # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # #         'Company Short Name':'Company Name',
# # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # #         'Company Status': "Status",
# # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # #     }
    
# # # # # #     for old, new in rename_map.items():
# # # # # #         if old in dfc.columns:
# # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # #     # Ensure numeric financial columns
# # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # #     for col in num_cols:
# # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # #     # 5. Metadata Mapping (Names, Funds, Tags)
# # # # # #     if 'names' in metadata and not metadata['names'].empty:
# # # # # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # #         if 'Company Name' in dfc.columns:
# # # # # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # # # # #     if 'funds' in metadata and not metadata['funds'].empty:
# # # # # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # #         if 'Fund Name' in dfc.columns:
# # # # # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # # # # #     if 'tags' in metadata and not metadata['tags'].empty:
# # # # # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # # # # #         if 'Technology Tag' in dfc.columns:
# # # # # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # #     # --- 5b. MASTER LOOKUP: Merge (Left Join) logic ---
# # # # # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # # # # #         mf = metadata['master_funds']
        
# # # # # #         # Ensure we have clean keys (strip whitespace) for better matching
# # # # # #         dfc['join_key'] = dfc['Fund Name'].astype(str).str.strip()
# # # # # #         mf['join_key'] = mf['fund_name'].astype(str).str.strip()
        
# # # # # #         # Perform LEFT JOIN: dfc + master_funds
# # # # # #         # We only want the 'isomer_fund' column from the master list
# # # # # #         merged = dfc.merge(
# # # # # #             mf[['join_key', 'isomer_fund']], 
# # # # # #             on='join_key', 
# # # # # #             how='left', 
# # # # # #             suffixes=('', '_new')
# # # # # #         )
        
# # # # # #         # 'isomer_fund_new' now contains the lookup value (e.g. Isomer Capital I).
# # # # # #         # We use .combine_first() to prioritize the new value. 
# # # # # #         # If the lookup found nothing (NaN), we keep the original value (e.g. Historic_Dump).
# # # # # #         merged['Isomer Fund'] = merged['isomer_fund_new'].combine_first(merged['Isomer Fund'])
        
# # # # # #         # Cleanup temp columns
# # # # # #         dfc = merged.drop(columns=['join_key', 'isomer_fund_new'])
# # # # # #     # ----------------------------------------------------

# # # # # #     # 6. Merge URLs
# # # # # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # # #         urls_df = metadata['urls'].copy()
# # # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # # #         for char in URL_CHARS:
# # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # # #     # 7. Mode Specific Logic
# # # # # #     if mode == 'rollup':
# # # # # #         agg_rules = {
# # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # #             "Distributions EUR": 'sum',
# # # # # #             "Company Name": 'first',
# # # # # #             "Initial Investment Date": 'first',
# # # # # #             "Data as of Date": 'first',
# # # # # #             "Status": 'first', 
# # # # # #             "Country": 'first',
# # # # # #             "URL": 'first'
# # # # # #         }
# # # # # #         for c in dfc.columns:
# # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # #                 agg_rules[c] = 'first'

# # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # #     # 8. Final Metrics
# # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # #     # 9. Dates Parsing
# # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # #     if 'Data as of Date' in dfc.columns:
# # # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# # # # # #         def format_report_quarter(d):
# # # # # #             if pd.isnull(d): return None
# # # # # #             return f"Q{d.quarter} {d.year}"
# # # # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # # # # #     # 10. Status Logic
# # # # # #     if 'Status' in dfc.columns:
# # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
# # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
# # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # #     return dfc

# # # # # # # import pandas as pd
# # # # # # # import numpy as np
# # # # # # # import re

# # # # # # # # Constants
# # # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # # BUSINESS_MODEL_MAP = {
# # # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # # }
# # # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # # def parse_hybrid_date(series):
# # # # # # #     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
# # # # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # # #     """
# # # # # # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # # # # # #     """
# # # # # # #     # 1. Label and Concatenate
# # # # # # #     df_list = []
# # # # # # #     for fund_name, df in files_dict.items():
# # # # # # #         temp_df = df.copy()
# # # # # # #         # Default 'Isomer Fund' to the file source (e.g. "Historic_Dump")
# # # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # # #         df_list.append(temp_df)
    
# # # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # # #     # 2. Basic Regex Cleaning
# # # # # # #     for char in BAD_CHARS:
# # # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # # #     # 3. RAG Exclusion Logic
# # # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # # #     # 4. Column Selection & Renaming
# # # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # # # #     rename_map = {
# # # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # # #         'Company Short Name':'Company Name',
# # # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # # #         'Company Status': "Status",
# # # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # # #     }
    
# # # # # # #     for old, new in rename_map.items():
# # # # # # #         if old in dfc.columns:
# # # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # # #     # Ensure numeric financial columns
# # # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # # #     for col in num_cols:
# # # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # # #     # 5. Metadata Mapping (Standard Cleanup)
# # # # # # #     if 'names' in metadata and not metadata['names'].empty:
# # # # # # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # # #         if 'Company Name' in dfc.columns:
# # # # # # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # # # # # #     if 'funds' in metadata and not metadata['funds'].empty:
# # # # # # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # # #         if 'Fund Name' in dfc.columns:
# # # # # # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # # # # # #     if 'tags' in metadata and not metadata['tags'].empty:
# # # # # # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # # # # # #         if 'Technology Tag' in dfc.columns:
# # # # # # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # # #     # --- 5b. MASTER LOOKUP: Apply Isomer Fund from DB ---
# # # # # # #     # This is the logic you requested: Look up 'Fund Name' in the master list 
# # # # # # #     # and overwrite 'Isomer Fund' with the correct value (e.g. Isomer Capital I)
# # # # # # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # # # # # #         mf = metadata['master_funds']
# # # # # # #         # Ensure we have the right columns (fund_name = key, isomer_fund = value)
# # # # # # #         if 'fund_name' in mf.columns and 'isomer_fund' in mf.columns:
# # # # # # #             # Create the lookup dictionary
# # # # # # #             lookup_dict = dict(zip(mf['fund_name'], mf['isomer_fund']))
            
# # # # # # #             # Map the values. 
# # # # # # #             # .map(lookup_dict) finds the match.
# # # # # # #             # .fillna(dfc['Isomer Fund']) keeps the original value (e.g. "Historic_Dump") if no match is found.
# # # # # # #             dfc['Isomer Fund'] = dfc['Fund Name'].map(lookup_dict).fillna(dfc['Isomer Fund'])
# # # # # # #     # ----------------------------------------------------

# # # # # # #     # 6. Merge URLs
# # # # # # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # # # #         urls_df = metadata['urls'].copy()
# # # # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # # # #         for char in URL_CHARS:
# # # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # # # #     # 7. Mode Specific Logic
# # # # # # #     if mode == 'rollup':
# # # # # # #         agg_rules = {
# # # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # # #             "Distributions EUR": 'sum',
# # # # # # #             "Company Name": 'first',
# # # # # # #             "Initial Investment Date": 'first',
# # # # # # #             "Data as of Date": 'first',
# # # # # # #             "Status": 'first', 
# # # # # # #             "Country": 'first',
# # # # # # #             "URL": 'first'
# # # # # # #         }
# # # # # # #         for c in dfc.columns:
# # # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # # #                 agg_rules[c] = 'first'

# # # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # # #     # 8. Final Metrics
# # # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # # #     # 9. Dates Parsing
# # # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # # #     if 'Data as of Date' in dfc.columns:
# # # # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        
# # # # # # #         def format_report_quarter(d):
# # # # # # #             if pd.isnull(d): return None
# # # # # # #             return f"Q{d.quarter} {d.year}"
            
# # # # # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # # # # # #     # 10. Status Logic
# # # # # # #     if 'Status' in dfc.columns:
# # # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
# # # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
# # # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # # #     return dfc

# # # # # # # # import pandas as pd
# # # # # # # # import numpy as np
# # # # # # # # import re

# # # # # # # # # Constants
# # # # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # # # BUSINESS_MODEL_MAP = {
# # # # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # # # }
# # # # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # # # def parse_hybrid_date(series):
# # # # # # # #     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
# # # # # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # # # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # # # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # # # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # # # #     """
# # # # # # # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # # # # # # #     """
# # # # # # # #     # 1. Label and Concatenate
# # # # # # # #     df_list = []
# # # # # # # #     for fund_name, df in files_dict.items():
# # # # # # # #         temp_df = df.copy()
# # # # # # # #         # Initial set from source (e.g. "Historic_Dump" or "Isomer Capital I")
# # # # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # # # #         df_list.append(temp_df)
    
# # # # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # # # #     # 2. Basic Regex Cleaning
# # # # # # # #     for char in BAD_CHARS:
# # # # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # # # #     # 3. RAG Exclusion Logic
# # # # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # # # #     # 4. Column Selection & Renaming
# # # # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # # # # #     rename_map = {
# # # # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # # # #         'Company Short Name':'Company Name',
# # # # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # # # #         'Company Status': "Status",
# # # # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # # # #     }
    
# # # # # # # #     for old, new in rename_map.items():
# # # # # # # #         if old in dfc.columns:
# # # # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # # # #     # Ensure numeric financial columns
# # # # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # # # #     for col in num_cols:
# # # # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # # # #     # 5. Metadata Mapping (Cleaning Names)
# # # # # # # #     if 'names' in metadata and not metadata['names'].empty:
# # # # # # # #         name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # # # #         if 'Company Name' in dfc.columns:
# # # # # # # #             dfc['Company Name'] = dfc['Company Name'].replace(name_map)

# # # # # # # #     if 'funds' in metadata and not metadata['funds'].empty:
# # # # # # # #         fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # # # #         if 'Fund Name' in dfc.columns:
# # # # # # # #             dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

# # # # # # # #     if 'tags' in metadata and not metadata['tags'].empty:
# # # # # # # #         tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
# # # # # # # #         if 'Technology Tag' in dfc.columns:
# # # # # # # #             dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # # # #     # --- 5b. Map Isomer Fund from Master List ---
# # # # # # # #     # This overwrites the file source (e.g. "Historic_Dump") with the actual Isomer Fund (e.g. "Isomer Capital I")
# # # # # # # #     if 'master_funds' in metadata and not metadata['master_funds'].empty:
# # # # # # # #         mf = metadata['master_funds']
# # # # # # # #         if 'fund_name' in mf.columns and 'isomer_fund' in mf.columns:
# # # # # # # #             # Create Map: Fund Name -> Isomer Fund
# # # # # # # #             isomer_fund_map = dict(zip(mf['fund_name'], mf['isomer_fund']))
# # # # # # # #             # Map values, fill missing with existing value
# # # # # # # #             dfc['Isomer Fund'] = dfc['Fund Name'].map(isomer_fund_map).fillna(dfc['Isomer Fund'])
# # # # # # # #     # --------------------------------------------

# # # # # # # #     # 6. Merge URLs
# # # # # # # #     if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # # # # #         urls_df = metadata['urls'].copy()
# # # # # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # # # # #         for char in URL_CHARS:
# # # # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # # # # #     # 7. Mode Specific Logic
# # # # # # # #     if mode == 'rollup':
# # # # # # # #         agg_rules = {
# # # # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # # # #             "Distributions EUR": 'sum',
# # # # # # # #             "Company Name": 'first',
# # # # # # # #             "Initial Investment Date": 'first',
# # # # # # # #             "Data as of Date": 'first',
# # # # # # # #             "Status": 'first', 
# # # # # # # #             "Country": 'first',
# # # # # # # #             "URL": 'first'
# # # # # # # #         }
# # # # # # # #         for c in dfc.columns:
# # # # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # # # #                 agg_rules[c] = 'first'

# # # # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # # # #     # 8. Final Metrics
# # # # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # # # #     # 9. Dates Parsing (Hybrid)
# # # # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # # # #     if 'Data as of Date' in dfc.columns:
# # # # # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        
# # # # # # # #         def format_report_quarter(d):
# # # # # # # #             if pd.isnull(d): return None
# # # # # # # #             return f"Q{d.quarter} {d.year}"
            
# # # # # # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

# # # # # # # #     # 10. Status Logic
# # # # # # # #     if 'Status' in dfc.columns:
# # # # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
# # # # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
# # # # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # # # #     return dfc

# # # # # # # # # import pandas as pd
# # # # # # # # # import numpy as np
# # # # # # # # # import re

# # # # # # # # # # Constants
# # # # # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # # # # BUSINESS_MODEL_MAP = {
# # # # # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # # # # }
# # # # # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # # # # def parse_hybrid_date(series):
# # # # # # # # #     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
# # # # # # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
# # # # # # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
# # # # # # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
# # # # # # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # # # # #     """
# # # # # # # # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # # # # # # # #     """
# # # # # # # # #     # 1. Label and Concatenate
# # # # # # # # #     df_list = []
# # # # # # # # #     for fund_name, df in files_dict.items():
# # # # # # # # #         temp_df = df.copy()
# # # # # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # # # # #         df_list.append(temp_df)
    
# # # # # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # # # # #     # 2. Basic Regex Cleaning
# # # # # # # # #     for char in BAD_CHARS:
# # # # # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # # # # #     # 3. RAG Exclusion Logic
# # # # # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # # # # #     # 4. Column Selection & Renaming
# # # # # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # # # # # #     rename_map = {
# # # # # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # # # # #         'Company Short Name':'Company Name',
# # # # # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # # # # #         'Company Status': "Status",
# # # # # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # # # # #     }
    
# # # # # # # # #     for old, new in rename_map.items():
# # # # # # # # #         if old in dfc.columns:
# # # # # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # # # # #     # Ensure numeric financial columns
# # # # # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # # # # #     for col in num_cols:
# # # # # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # # # # #     # 5. Metadata Mapping
# # # # # # # # #     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # # # # #     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # # # # #     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

# # # # # # # # #     if 'Company Name' in dfc.columns:
# # # # # # # # #         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
# # # # # # # # #     if 'Fund Name' in dfc.columns:
# # # # # # # # #         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
# # # # # # # # #     if 'Technology Tag' in dfc.columns:
# # # # # # # # #         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # # # # #     # 6. Merge URLs
# # # # # # # # #     if not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # # # # # #         urls_df = metadata['urls'].copy()
# # # # # # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # # # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # # # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # # # # # #         for char in URL_CHARS:
# # # # # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # # # # # #     # 7. Mode Specific Logic
# # # # # # # # #     if mode == 'rollup':
# # # # # # # # #         agg_rules = {
# # # # # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # # # # #             "Distributions EUR": 'sum',
# # # # # # # # #             "Company Name": 'first',
# # # # # # # # #             "Initial Investment Date": 'first',
# # # # # # # # #             "Data as of Date": 'first',
# # # # # # # # #             "Status": 'first', 
# # # # # # # # #             "Country": 'first',
# # # # # # # # #             "URL": 'first'
# # # # # # # # #         }
# # # # # # # # #         for c in dfc.columns:
# # # # # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # # # # #                 agg_rules[c] = 'first'

# # # # # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # # # # #     # 8. Final Metrics
# # # # # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # # # # #     # 9. Dates Parsing (Hybrid)
    
# # # # # # # # #     # A. Invest Quarter (from Initial Investment Date) -> "Q1" (Year is separate)
# # # # # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # # # # #     # B. Reporting Quarter (from Data as of Date) -> "Q1 2025" (Quarter + Year)
# # # # # # # # #     if 'Data as of Date' in dfc.columns:
# # # # # # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        
# # # # # # # # #         # --- NEW LOGIC HERE ---
# # # # # # # # #         def format_report_quarter(d):
# # # # # # # # #             if pd.isnull(d): return None
# # # # # # # # #             return f"Q{d.quarter} {d.year}"
            
# # # # # # # # #         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)
# # # # # # # # #         # ----------------------

# # # # # # # # #     # 10. Status Logic
# # # # # # # # #     if 'Status' in dfc.columns:
# # # # # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
# # # # # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
# # # # # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # # # # #     return dfc

# # # # # # # # # # import pandas as pd
# # # # # # # # # # import numpy as np
# # # # # # # # # # import re

# # # # # # # # # # # Constants
# # # # # # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # # # # # BUSINESS_MODEL_MAP = {
# # # # # # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # # # # # }
# # # # # # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # # # # # def parse_hybrid_date(series):
# # # # # # # # # #     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
# # # # # # # # # #     # Step A: Coerce to numeric (catches Excel serials)
# # # # # # # # # #     numeric_dates = pd.to_numeric(series, errors='coerce')
    
# # # # # # # # # #     # Step B: Convert numeric to datetime (Excel Epoch)
# # # # # # # # # #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
    
# # # # # # # # # #     # Step C: Parse standard strings
# # # # # # # # # #     dates_from_strings = pd.to_datetime(series, errors='coerce')
    
# # # # # # # # # #     # Step D: Combine
# # # # # # # # # #     return dates_from_excel.combine_first(dates_from_strings)

# # # # # # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # # # # # #     """
# # # # # # # # # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # # # # # # # # #     """
# # # # # # # # # #     # 1. Label and Concatenate
# # # # # # # # # #     df_list = []
# # # # # # # # # #     for fund_name, df in files_dict.items():
# # # # # # # # # #         temp_df = df.copy()
# # # # # # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # # # # # #         df_list.append(temp_df)
    
# # # # # # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # # # # # #     # 2. Basic Regex Cleaning
# # # # # # # # # #     for char in BAD_CHARS:
# # # # # # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # # # # # #     # 3. RAG Exclusion Logic
# # # # # # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # # # # # #     # 4. Column Selection & Renaming
    
# # # # # # # # # #     # Prevent duplicate 'Company Name' columns if both Short and Long exist
# # # # # # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # # # # # #         dfc.drop(columns=['Company Name'], inplace=True)

# # # # # # # # # #     rename_map = {
# # # # # # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # # # # # #         'Company Short Name':'Company Name',
# # # # # # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # # # # # #         'Company Status': "Status",
# # # # # # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # # # # # #         # Note: 'Data as of Date' usually comes in with that name, so no rename needed.
# # # # # # # # # #     }
    
# # # # # # # # # #     for old, new in rename_map.items():
# # # # # # # # # #         if old in dfc.columns:
# # # # # # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # # # # # #     # Ensure numeric financial columns
# # # # # # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # # # # # #     for col in num_cols:
# # # # # # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # # # # # #     # 5. Metadata Mapping
# # # # # # # # # #     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # # # # # #     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # # # # # #     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

# # # # # # # # # #     if 'Company Name' in dfc.columns:
# # # # # # # # # #         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
# # # # # # # # # #     if 'Fund Name' in dfc.columns:
# # # # # # # # # #         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
# # # # # # # # # #     if 'Technology Tag' in dfc.columns:
# # # # # # # # # #         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # # # # # #     # 6. Merge URLs
# # # # # # # # # #     if not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# # # # # # # # # #         urls_df = metadata['urls'].copy()
# # # # # # # # # #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# # # # # # # # # #         # Force Integer Match
# # # # # # # # # #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# # # # # # # # # #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# # # # # # # # # #         for char in URL_CHARS:
# # # # # # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # # # # # #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# # # # # # # # # #     # 7. Mode Specific Logic (Rollup)
# # # # # # # # # #     if mode == 'rollup':
# # # # # # # # # #         agg_rules = {
# # # # # # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # # # # # #             "Distributions EUR": 'sum',
# # # # # # # # # #             "Company Name": 'first',
# # # # # # # # # #             "Initial Investment Date": 'first',
# # # # # # # # # #             "Data as of Date": 'first',  # <--- Ensure we keep this in rollup
# # # # # # # # # #             "Status": 'first', 
# # # # # # # # # #             "Country": 'first',
# # # # # # # # # #             "URL": 'first'
# # # # # # # # # #         }
# # # # # # # # # #         for c in dfc.columns:
# # # # # # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # # # # # #                 agg_rules[c] = 'first'

# # # # # # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # # # # # #     # 8. Final Metrics
# # # # # # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # # # # # #     # 9. Dates Parsing (Hybrid)
# # # # # # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # # # # # #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# # # # # # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # # # # # #     # --- NEW: Parse Data as of Date ---
# # # # # # # # # #     if 'Data as of Date' in dfc.columns:
# # # # # # # # # #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# # # # # # # # # #     # ----------------------------------

# # # # # # # # # #     # 10. Status Logic
# # # # # # # # # #     if 'Status' in dfc.columns:
# # # # # # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
# # # # # # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
# # # # # # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # # # # # #     return dfc

# # # # # # # # # # # import pandas as pd
# # # # # # # # # # # import numpy as np
# # # # # # # # # # # import re

# # # # # # # # # # # # Constants
# # # # # # # # # # # BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
# # # # # # # # # # #              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
# # # # # # # # # # #              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
# # # # # # # # # # #              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# # # # # # # # # # # URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# # # # # # # # # # # BUSINESS_MODEL_MAP = {
# # # # # # # # # # #     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# # # # # # # # # # # }
# # # # # # # # # # # REGION_MAP = {"MENA": "Europe"}

# # # # # # # # # # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # # # # # # # # # #     """
# # # # # # # # # # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # # # # # # # # # #     """
# # # # # # # # # # #     # 1. Label and Concatenate
# # # # # # # # # # #     df_list = []
# # # # # # # # # # #     for fund_name, df in files_dict.items():
# # # # # # # # # # #         temp_df = df.copy()
# # # # # # # # # # #         temp_df['Isomer Fund'] = fund_name
# # # # # # # # # # #         df_list.append(temp_df)
    
# # # # # # # # # # #     dfc = pd.concat(df_list, ignore_index=True)

# # # # # # # # # # #     # 2. Basic Regex Cleaningcd
# # # # # # # # # # #     for char in BAD_CHARS:
# # # # # # # # # # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # # # # # # # # # #     # 3. RAG Exclusion Logic
# # # # # # # # # # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # # # # # # # # # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # # # # # # # # # #     dfc = dfc[~mask_rag_overlap]

# # # # # # # # # # #     # 4. Column Selection & Renaming
    
# # # # # # # # # # #     # --- CRITICAL FIX: PREVENT DUPLICATES ---
# # # # # # # # # # #     # If the file has both 'Company Name' and 'Company Short Name', 
# # # # # # # # # # #     # drop the original 'Company Name' so we don't end up with two after renaming.
# # # # # # # # # # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # # # # # # # # # #         dfc.drop(columns=['Company Name'], inplace=True)
# # # # # # # # # # #     # ----------------------------------------

# # # # # # # # # # #     rename_map = {
# # # # # # # # # # #         'LP Analyst Identifier':'LPA Num',
# # # # # # # # # # #         'Company Short Name':'Company Name',
# # # # # # # # # # #         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
# # # # # # # # # # #         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
# # # # # # # # # # #         'Client - Realized Value (Base Currency)': "Distributions EUR",
# # # # # # # # # # #         'Client - Realized (Base Currency)': "Distributions EUR", 
# # # # # # # # # # #         'Client - Multiple (Base Currency)': "Multiple",
# # # # # # # # # # #         'Current Multiple (Base Currency)': "Multiple",
# # # # # # # # # # #         'Company Status': "Status",
# # # # # # # # # # #         'LP Analyst - Industry': "LP Analyst - Industry",
# # # # # # # # # # #         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
# # # # # # # # # # #     }
    
# # # # # # # # # # #     # Robust Rename
# # # # # # # # # # #     for old, new in rename_map.items():
# # # # # # # # # # #         if old in dfc.columns:
# # # # # # # # # # #             dfc.rename(columns={old: new}, inplace=True)

# # # # # # # # # # #     # Drop unwanted columns if they exist
# # # # # # # # # # #     cols_to_drop = ['Client - Current Cost (Base Currency)', 'Client - Total Value (Base Currency)', 'LP Analyst - Sector']
# # # # # # # # # # #     dfc.drop(columns=[c for c in cols_to_drop if c in dfc.columns], inplace=True)
    
# # # # # # # # # # #     # Ensure numeric financial columns
# # # # # # # # # # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # # # # # # # # # #     for col in num_cols:
# # # # # # # # # # #         if col not in dfc.columns: dfc[col] = 0.0
# # # # # # # # # # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # # # # # # # # # #     # 5. Metadata Mapping (Names, Funds, Tags)
# # # # # # # # # # #     # We use exact matching dictionaries
# # # # # # # # # # #     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # # # # # # # # # #     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # # # # # # # # # #     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

# # # # # # # # # # #     if 'Company Name' in dfc.columns:
# # # # # # # # # # #         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
# # # # # # # # # # #     if 'Fund Name' in dfc.columns:
# # # # # # # # # # #         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
# # # # # # # # # # #     if 'Technology Tag' in dfc.columns:
# # # # # # # # # # #         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # # # # # # # # # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # # # # # # # # # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # # # # # # # # # #     # 6. Merge URLs
# # # # # # # # # # #     if not metadata['urls'].empty:
# # # # # # # # # # #         urls_df = metadata['urls'].copy()
        
# # # # # # # # # # #         # RENAME FIX: Handle both CSV style ('Organization URL') and DB style ('url')
# # # # # # # # # # #         urls_df.rename(columns={
# # # # # # # # # # #             'Organization URL': 'URL', 
# # # # # # # # # # #             'url': 'URL',
# # # # # # # # # # #             'lpa_num': 'LPA Num',
# # # # # # # # # # #             'LPA Num': 'LPA Num'
# # # # # # # # # # #         }, inplace=True)
        
# # # # # # # # # # #         # Clean the URLs
# # # # # # # # # # #         for char in URL_CHARS:
# # # # # # # # # # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # # # # # # # # # #         # Merge
# # # # # # # # # # #         dfc = dfc.merge(urls_df, on='LPA Num', how='left')

# # # # # # # # # # #     # 7. Mode Specific Logic (Rollup)
# # # # # # # # # # #     if mode == 'rollup':
# # # # # # # # # # #         # Default aggregation rules
# # # # # # # # # # #         agg_rules = {
# # # # # # # # # # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # # # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # # # # # # # # # #             "Cost in Isomer's Share EUR": 'sum',
# # # # # # # # # # #             "Valuation of Isomer's Share EUR": 'sum',
# # # # # # # # # # #             "Distributions EUR": 'sum',
# # # # # # # # # # #             "Company Name": 'first',
# # # # # # # # # # #             "Initial Investment Date": 'first',
# # # # # # # # # # #             "Status": 'first', 
# # # # # # # # # # #             "Country": 'first',
# # # # # # # # # # #             "URL": 'first'
# # # # # # # # # # #         }
# # # # # # # # # # #         # Add any other columns present in dfc as 'first'
# # # # # # # # # # #         for c in dfc.columns:
# # # # # # # # # # #             if c not in agg_rules and c != 'LPA Num':
# # # # # # # # # # #                 agg_rules[c] = 'first'

# # # # # # # # # # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # # # # # # # # # #     # 8. Final Metrics
# # # # # # # # # # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # # # # # # # # # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # # # # # # # # # #     # --- 9. ROBUST HYBRID DATE PARSING ---
# # # # # # # # # # #     if 'Initial Investment Date' in dfc.columns:
# # # # # # # # # # #         # Step A: Coerce to numeric (catches Excel serials like 41754)
# # # # # # # # # # #         numeric_dates = pd.to_numeric(dfc['Initial Investment Date'], errors='coerce')
        
# # # # # # # # # # #         # Step B: Convert numeric to datetime (Excel Epoch)
# # # # # # # # # # #         dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
        
# # # # # # # # # # #         # Step C: Parse standard strings (e.g. "2014-05-20") using original column
# # # # # # # # # # #         dates_from_strings = pd.to_datetime(dfc['Initial Investment Date'], errors='coerce')
        
# # # # # # # # # # #         # Step D: Combine - prefer the Excel result, fill holes with String result
# # # # # # # # # # #         dfc['Initial Investment Date'] = dates_from_excel.combine_first(dates_from_strings)

# # # # # # # # # # #         # Calculate Year/Quarter
# # # # # # # # # # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # # # # # # # # # #         # Handle cases where Date is NaT -> Quarter is NaN
# # # # # # # # # # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # # # # # # # # # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# # # # # # # # # # #     # 10. Status Logic
# # # # # # # # # # #     if 'Status' in dfc.columns:
# # # # # # # # # # #         mask_private = dfc['Status'] == "Private"
# # # # # # # # # # #         mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # # # #         dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
# # # # # # # # # # #         mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
# # # # # # # # # # #         dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
# # # # # # # # # # #         mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
# # # # # # # # # # #         dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

# # # # # # # # # # #     return dfc