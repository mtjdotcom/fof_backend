import pandas as pd
import numpy as np
import re

# Constants
BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
             ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
             ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
             ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

BUSINESS_MODEL_MAP = {
    "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
}
REGION_MAP = {"MENA": "Europe"}

def parse_hybrid_date(series):
    """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
    numeric_dates = pd.to_numeric(series, errors='coerce')
    dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
    dates_from_strings = pd.to_datetime(series, errors='coerce')
    return dates_from_excel.combine_first(dates_from_strings)

def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
    """
    Robust cleaning function with hybrid date parsing and strict type matching.
    """
    # 1. Label and Concatenate
    df_list = []
    for fund_name, df in files_dict.items():
        temp_df = df.copy()
        # Initial set from source (e.g. "Historic_Dump" or "Isomer Capital I")
        temp_df['Isomer Fund'] = fund_name
        df_list.append(temp_df)
    
    dfc = pd.concat(df_list, ignore_index=True)

    # 2. Basic Regex Cleaning
    for char in BAD_CHARS:
        dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
    # 3. RAG Exclusion Logic
    rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
    mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
    dfc = dfc[~mask_rag_overlap]

    # 4. Column Selection & Renaming
    if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
        dfc.drop(columns=['Company Name'], inplace=True)

    rename_map = {
        'LP Analyst Identifier':'LPA Num',
        'Company Short Name':'Company Name',
        'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
        'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
        'Client - Realized Value (Base Currency)': "Distributions EUR",
        'Client - Realized (Base Currency)': "Distributions EUR", 
        'Client - Multiple (Base Currency)': "Multiple",
        'Current Multiple (Base Currency)': "Multiple",
        'Company Status': "Status",
        'LP Analyst - Industry': "LP Analyst - Industry",
        'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
    }
    
    for old, new in rename_map.items():
        if old in dfc.columns:
            dfc.rename(columns={old: new}, inplace=True)

    # Ensure numeric financial columns
    num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
    for col in num_cols:
        if col not in dfc.columns: dfc[col] = 0.0
        dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

    # 5. Metadata Mapping (Cleaning Names)
    if 'names' in metadata and not metadata['names'].empty:
        name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
        if 'Company Name' in dfc.columns:
            dfc['Company Name'] = dfc['Company Name'].replace(name_map)

    if 'funds' in metadata and not metadata['funds'].empty:
        fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
        if 'Fund Name' in dfc.columns:
            dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)

    if 'tags' in metadata and not metadata['tags'].empty:
        tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))
        if 'Technology Tag' in dfc.columns:
            dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
    dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
    dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

    # --- 5b. Map Isomer Fund from Master List ---
    # This overwrites the file source (e.g. "Historic_Dump") with the actual Isomer Fund (e.g. "Isomer Capital I")
    if 'master_funds' in metadata and not metadata['master_funds'].empty:
        mf = metadata['master_funds']
        if 'fund_name' in mf.columns and 'isomer_fund' in mf.columns:
            # Create Map: Fund Name -> Isomer Fund
            isomer_fund_map = dict(zip(mf['fund_name'], mf['isomer_fund']))
            # Map values, fill missing with existing value
            dfc['Isomer Fund'] = dfc['Fund Name'].map(isomer_fund_map).fillna(dfc['Isomer Fund'])
    # --------------------------------------------

    # 6. Merge URLs
    if 'urls' in metadata and not metadata['urls'].empty and 'LPA Num' in dfc.columns:
        urls_df = metadata['urls'].copy()
        urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
        dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
        urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
        for char in URL_CHARS:
             urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
        dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

    # 7. Mode Specific Logic
    if mode == 'rollup':
        agg_rules = {
            "Fund Name": lambda x: ', '.join(set(x.dropna())),
            "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
            "Cost in Isomer's Share EUR": 'sum',
            "Valuation of Isomer's Share EUR": 'sum',
            "Distributions EUR": 'sum',
            "Company Name": 'first',
            "Initial Investment Date": 'first',
            "Data as of Date": 'first',
            "Status": 'first', 
            "Country": 'first',
            "URL": 'first'
        }
        for c in dfc.columns:
            if c not in agg_rules and c != 'LPA Num':
                agg_rules[c] = 'first'

        dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

    # 8. Final Metrics
    dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
    dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

    # 9. Dates Parsing (Hybrid)
    if 'Initial Investment Date' in dfc.columns:
        dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
        dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
        quarter_num = dfc['Initial Investment Date'].dt.quarter
        dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

    if 'Data as of Date' in dfc.columns:
        dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        
        def format_report_quarter(d):
            if pd.isnull(d): return None
            return f"Q{d.quarter} {d.year}"
            
        dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)

    # 10. Status Logic
    if 'Status' in dfc.columns:
        mask_private = dfc['Status'] == "Private"
        mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
        dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
        
        mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
        dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
        
        mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
        dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

    return dfc

# import pandas as pd
# import numpy as np
# import re

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
#     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
#     numeric_dates = pd.to_numeric(series, errors='coerce')
#     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
#     dates_from_strings = pd.to_datetime(series, errors='coerce')
#     return dates_from_excel.combine_first(dates_from_strings)

# def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
#     """
#     Robust cleaning function with hybrid date parsing and strict type matching.
#     """
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

#     # Ensure numeric financial columns
#     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
#     for col in num_cols:
#         if col not in dfc.columns: dfc[col] = 0.0
#         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

#     # 5. Metadata Mapping
#     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
#     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
#     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

#     if 'Company Name' in dfc.columns:
#         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
#     if 'Fund Name' in dfc.columns:
#         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
#     if 'Technology Tag' in dfc.columns:
#         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
#     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
#     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

#     # 6. Merge URLs
#     if not metadata['urls'].empty and 'LPA Num' in dfc.columns:
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
#             "Status": 'first', 
#             "Country": 'first',
#             "URL": 'first'
#         }
#         for c in dfc.columns:
#             if c not in agg_rules and c != 'LPA Num':
#                 agg_rules[c] = 'first'

#         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

#     # 8. Final Metrics
#     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
#     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

#     # 9. Dates Parsing (Hybrid)
    
#     # A. Invest Quarter (from Initial Investment Date) -> "Q1" (Year is separate)
#     if 'Initial Investment Date' in dfc.columns:
#         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
#         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
#         quarter_num = dfc['Initial Investment Date'].dt.quarter
#         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

#     # B. Reporting Quarter (from Data as of Date) -> "Q1 2025" (Quarter + Year)
#     if 'Data as of Date' in dfc.columns:
#         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
        
#         # --- NEW LOGIC HERE ---
#         def format_report_quarter(d):
#             if pd.isnull(d): return None
#             return f"Q{d.quarter} {d.year}"
            
#         dfc['Reporting Quarter'] = dfc['Data as of Date'].apply(format_report_quarter)
#         # ----------------------

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
# #     """Helper to parse columns that mix Excel Serials (41754) and Strings (2014-05-20)."""
# #     # Step A: Coerce to numeric (catches Excel serials)
# #     numeric_dates = pd.to_numeric(series, errors='coerce')
    
# #     # Step B: Convert numeric to datetime (Excel Epoch)
# #     dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
    
# #     # Step C: Parse standard strings
# #     dates_from_strings = pd.to_datetime(series, errors='coerce')
    
# #     # Step D: Combine
# #     return dates_from_excel.combine_first(dates_from_strings)

# # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# #     """
# #     Robust cleaning function with hybrid date parsing and strict type matching.
# #     """
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
    
# #     # Prevent duplicate 'Company Name' columns if both Short and Long exist
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
# #         # Note: 'Data as of Date' usually comes in with that name, so no rename needed.
# #     }
    
# #     for old, new in rename_map.items():
# #         if old in dfc.columns:
# #             dfc.rename(columns={old: new}, inplace=True)

# #     # Ensure numeric financial columns
# #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# #     for col in num_cols:
# #         if col not in dfc.columns: dfc[col] = 0.0
# #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# #     # 5. Metadata Mapping
# #     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# #     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# #     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

# #     if 'Company Name' in dfc.columns:
# #         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
# #     if 'Fund Name' in dfc.columns:
# #         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
# #     if 'Technology Tag' in dfc.columns:
# #         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# #     # 6. Merge URLs
# #     if not metadata['urls'].empty and 'LPA Num' in dfc.columns:
# #         urls_df = metadata['urls'].copy()
# #         urls_df.rename(columns={'lpa_num': 'LPA Num', 'url': 'URL', 'Organization URL': 'URL'}, inplace=True)
        
# #         # Force Integer Match
# #         dfc['LPA Num'] = pd.to_numeric(dfc['LPA Num'], errors='coerce').fillna(0).astype(int)
# #         urls_df['LPA Num'] = pd.to_numeric(urls_df['LPA Num'], errors='coerce').fillna(0).astype(int)
        
# #         for char in URL_CHARS:
# #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# #         dfc = dfc.merge(urls_df[['LPA Num', 'URL']], on='LPA Num', how='left')

# #     # 7. Mode Specific Logic (Rollup)
# #     if mode == 'rollup':
# #         agg_rules = {
# #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# #             "Cost in Isomer's Share EUR": 'sum',
# #             "Valuation of Isomer's Share EUR": 'sum',
# #             "Distributions EUR": 'sum',
# #             "Company Name": 'first',
# #             "Initial Investment Date": 'first',
# #             "Data as of Date": 'first',  # <--- Ensure we keep this in rollup
# #             "Status": 'first', 
# #             "Country": 'first',
# #             "URL": 'first'
# #         }
# #         for c in dfc.columns:
# #             if c not in agg_rules and c != 'LPA Num':
# #                 agg_rules[c] = 'first'

# #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# #     # 8. Final Metrics
# #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# #     # 9. Dates Parsing (Hybrid)
# #     if 'Initial Investment Date' in dfc.columns:
# #         dfc['Initial Investment Date'] = parse_hybrid_date(dfc['Initial Investment Date'])
# #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

# #     # --- NEW: Parse Data as of Date ---
# #     if 'Data as of Date' in dfc.columns:
# #         dfc['Data as of Date'] = parse_hybrid_date(dfc['Data as of Date'])
# #     # ----------------------------------

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

# # # def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
# # #     """
# # #     Robust cleaning function with hybrid date parsing and strict type matching.
# # #     """
# # #     # 1. Label and Concatenate
# # #     df_list = []
# # #     for fund_name, df in files_dict.items():
# # #         temp_df = df.copy()
# # #         temp_df['Isomer Fund'] = fund_name
# # #         df_list.append(temp_df)
    
# # #     dfc = pd.concat(df_list, ignore_index=True)

# # #     # 2. Basic Regex Cleaningcd
# # #     for char in BAD_CHARS:
# # #         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
# # #     # 3. RAG Exclusion Logic
# # #     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
# # #     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
# # #     dfc = dfc[~mask_rag_overlap]

# # #     # 4. Column Selection & Renaming
    
# # #     # --- CRITICAL FIX: PREVENT DUPLICATES ---
# # #     # If the file has both 'Company Name' and 'Company Short Name', 
# # #     # drop the original 'Company Name' so we don't end up with two after renaming.
# # #     if 'Company Name' in dfc.columns and 'Company Short Name' in dfc.columns:
# # #         dfc.drop(columns=['Company Name'], inplace=True)
# # #     # ----------------------------------------

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
    
# # #     # Robust Rename
# # #     for old, new in rename_map.items():
# # #         if old in dfc.columns:
# # #             dfc.rename(columns={old: new}, inplace=True)

# # #     # Drop unwanted columns if they exist
# # #     cols_to_drop = ['Client - Current Cost (Base Currency)', 'Client - Total Value (Base Currency)', 'LP Analyst - Sector']
# # #     dfc.drop(columns=[c for c in cols_to_drop if c in dfc.columns], inplace=True)
    
# # #     # Ensure numeric financial columns
# # #     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
# # #     for col in num_cols:
# # #         if col not in dfc.columns: dfc[col] = 0.0
# # #         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

# # #     # 5. Metadata Mapping (Names, Funds, Tags)
# # #     # We use exact matching dictionaries
# # #     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
# # #     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
# # #     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

# # #     if 'Company Name' in dfc.columns:
# # #         dfc['Company Name'] = dfc['Company Name'].replace(name_map)
# # #     if 'Fund Name' in dfc.columns:
# # #         dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
# # #     if 'Technology Tag' in dfc.columns:
# # #         dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    
# # #     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
# # #     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

# # #     # 6. Merge URLs
# # #     if not metadata['urls'].empty:
# # #         urls_df = metadata['urls'].copy()
        
# # #         # RENAME FIX: Handle both CSV style ('Organization URL') and DB style ('url')
# # #         urls_df.rename(columns={
# # #             'Organization URL': 'URL', 
# # #             'url': 'URL',
# # #             'lpa_num': 'LPA Num',
# # #             'LPA Num': 'LPA Num'
# # #         }, inplace=True)
        
# # #         # Clean the URLs
# # #         for char in URL_CHARS:
# # #              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
# # #         # Merge
# # #         dfc = dfc.merge(urls_df, on='LPA Num', how='left')

# # #     # 7. Mode Specific Logic (Rollup)
# # #     if mode == 'rollup':
# # #         # Default aggregation rules
# # #         agg_rules = {
# # #             "Fund Name": lambda x: ', '.join(set(x.dropna())),
# # #             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
# # #             "Cost in Isomer's Share EUR": 'sum',
# # #             "Valuation of Isomer's Share EUR": 'sum',
# # #             "Distributions EUR": 'sum',
# # #             "Company Name": 'first',
# # #             "Initial Investment Date": 'first',
# # #             "Status": 'first', 
# # #             "Country": 'first',
# # #             "URL": 'first'
# # #         }
# # #         # Add any other columns present in dfc as 'first'
# # #         for c in dfc.columns:
# # #             if c not in agg_rules and c != 'LPA Num':
# # #                 agg_rules[c] = 'first'

# # #         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

# # #     # 8. Final Metrics
# # #     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
# # #     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

# # #     # --- 9. ROBUST HYBRID DATE PARSING ---
# # #     if 'Initial Investment Date' in dfc.columns:
# # #         # Step A: Coerce to numeric (catches Excel serials like 41754)
# # #         numeric_dates = pd.to_numeric(dfc['Initial Investment Date'], errors='coerce')
        
# # #         # Step B: Convert numeric to datetime (Excel Epoch)
# # #         dates_from_excel = pd.to_datetime(numeric_dates, unit='D', origin='1899-12-30', errors='coerce')
        
# # #         # Step C: Parse standard strings (e.g. "2014-05-20") using original column
# # #         dates_from_strings = pd.to_datetime(dfc['Initial Investment Date'], errors='coerce')
        
# # #         # Step D: Combine - prefer the Excel result, fill holes with String result
# # #         dfc['Initial Investment Date'] = dates_from_excel.combine_first(dates_from_strings)

# # #         # Calculate Year/Quarter
# # #         dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
# # #         # Handle cases where Date is NaT -> Quarter is NaN
# # #         quarter_num = dfc['Initial Investment Date'].dt.quarter
# # #         dfc['Invest Quarter'] = quarter_num.apply(lambda x: f"Q{int(x)}" if pd.notnull(x) else None)

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