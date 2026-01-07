import pandas as pd
import numpy as np
import re

# Constants for cleaning
BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
             ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
             ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
             ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

BUSINESS_MODEL_MAP = {
    "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
}
REGION_MAP = {"MENA": "Europe"}

def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
    """
    Main cleaning function.
    files_dict: {'IC I': df1, 'IC II': df2, ...}
    metadata: {'urls': df, 'names': df, 'tags': df, 'funds': df}
    mode: 'duplicates' (keep individual entries) or 'rollup' (merge duplicates)
    """

    # ... (Step 1: Label and Concatenate) ...
    df_list = []
    for fund_name, df in files_dict.items():
        temp_df = df.copy()
        temp_df['Isomer Fund'] = fund_name
        df_list.append(temp_df)
    
    dfc = pd.concat(df_list, ignore_index=True)

    # 2. Basic Cleaning (Regex)
    # Clean Company Name
    for char in BAD_CHARS:
        dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
    # 3. RAG Exclusion Logic
    rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
    mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
    dfc = dfc[~mask_rag_overlap]

    # 4. Column Selection & Renaming
    cols_to_drop = ['Company Name','Client - Current Cost (Base Currency)', 
                    'Client - Total Value (Base Currency)', 'LP Analyst - Sector', 
                    'LP Analyst - Industry Group']
    dfc.drop(columns=[c for c in cols_to_drop if c in dfc.columns], inplace=True)

    # --- UPDATED RENAME MAP TO HANDLE RAG FILE VARIATIONS ---
    rename_map = {
        'LP Analyst Identifier':'LPA Num',
        'Company Short Name':'Company Name',
        
        # Standardize Cost
        'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
        
        # Standardize Value
        'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
        
        # Standardize Distributions (Added RAG variant)
        'Client - Realized Value (Base Currency)': "Distributions EUR",
        'Client - Realized (Base Currency)': "Distributions EUR", 
        
        # Standardize Multiple (Added RAG variant)
        'Client - Multiple (Base Currency)': "Multiple",
        'Current Multiple (Base Currency)': "Multiple",
        
        # Standardize Status
        'Company Status': "Status",
        # Note: If column is already named 'Status' (like in RAG), it passes through fine.
        
        'LP Analyst - Industry': "LP Analyst - Industry",
        'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
    }
    dfc.rename(columns=rename_map, inplace=True)
    
    # Ensure numeric types
    num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
    for col in num_cols:
        # Check if column exists (handling cases where a file might be missing it entirely)
        if col in dfc.columns:
            dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)
        else:
            dfc[col] = 0.0

    # 5. Metadata Mapping
    name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
    fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
    tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

    dfc['Company Name'] = dfc['Company Name'].replace(name_map)
    dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
    dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
    dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
    dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

    # # 6. Merge URLs
    # if not metadata['urls'].empty:
    #     urls_df = metadata['urls'].copy()
    #     urls_df.rename(columns={'Organization URL': 'URL', 'LPA Num': 'LPA Num'}, inplace=True)
    #     for char in URL_CHARS:
    #          urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
    #     dfc = dfc.merge(urls_df, on='LPA Num', how='left')

    # 6. Merge URLs
    if not metadata['urls'].empty:
        urls_df = metadata['urls'].copy()
        
        # RENAME FIX: Handle both CSV style ('Organization URL') and DB style ('url')
        urls_df.rename(columns={
            'Organization URL': 'URL', 
            'url': 'URL',
            'lpa_num': 'LPA Num',
            'LPA Num': 'LPA Num'
        }, inplace=True)
        
        # Clean the URLs
        for char in URL_CHARS:
             urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
        
        # Merge
        dfc = dfc.merge(urls_df, on='LPA Num', how='left')

    # 7. Mode Specific Logic (Rollup)
    if mode == 'rollup':
        agg_rules = {
            "Fund Name": lambda x: ', '.join(set(x.dropna())),
            "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
            "Cost in Isomer's Share EUR": 'sum',
            "Valuation of Isomer's Share EUR": 'sum',
            "Distributions EUR": 'sum',
            "Company Name": 'first',
            "Initial Investment Date": 'first',
            "Status": 'first', 
            "Country": 'first',
            "Technology Tag": 'first',
            "Business Model": 'first',
            "URL": 'first',
            "Description": 'first',
            "Long Description": 'first',
            "SDGs": 'first',
            "Female Founders": 'first'
        }
        other_cols = [c for c in dfc.columns if c not in agg_rules and c != 'LPA Num']
        for c in other_cols:
            agg_rules[c] = 'first'

        dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

    # 8. Final Calculations & Dates
    dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
    dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

    # Date Handling
    if pd.api.types.is_numeric_dtype(dfc['Initial Investment Date']):
        dfc['Initial Investment Date'] = pd.to_datetime(
            dfc['Initial Investment Date'], 
            unit='D', 
            origin='1899-12-30'
        )
    else:
        dfc['Initial Investment Date'] = pd.to_datetime(
            dfc['Initial Investment Date'], 
            errors='coerce'
        )

    dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
    dfc['Invest Quarter'] = "Q" + dfc['Initial Investment Date'].dt.quarter.astype(str)

    # 9. Status Logic
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

# # Constants for cleaning
# BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
#              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
#              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
#              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# BUSINESS_MODEL_MAP = {
#     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# }
# REGION_MAP = {"MENA": "Europe"}

# def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
#     """
#     Main cleaning function.
#     files_dict: {'IC I': df1, 'IC II': df2, ...}
#     metadata: {'urls': df, 'names': df, 'tags': df, 'funds': df}
#     mode: 'duplicates' (keep individual entries) or 'rollup' (merge duplicates)
#     """

#     # ... (Step 1: Label and Concatenate) ...
#     df_list = []
#     for fund_name, df in files_dict.items():
#         temp_df = df.copy()
#         temp_df['Isomer Fund'] = fund_name
#         df_list.append(temp_df)
    
#     dfc = pd.concat(df_list, ignore_index=True)

#     # 2. Basic Cleaning (Regex)
#     # Clean Company Name
#     for char in BAD_CHARS:
#         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
    
#     # 3. RAG Exclusion Logic
#     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']
#     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
#     dfc = dfc[~mask_rag_overlap]

#     # 4. Column Selection & Renaming
#     cols_to_drop = ['Company Name','Client - Current Cost (Base Currency)', 
#                     'Client - Total Value (Base Currency)', 'LP Analyst - Sector', 
#                     'LP Analyst - Industry Group']
#     dfc.drop(columns=[c for c in cols_to_drop if c in dfc.columns], inplace=True)

#     rename_map = {
#         'LP Analyst Identifier':'LPA Num',
#         'Company Short Name':'Company Name',
#         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
#         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
#         'Client - Realized Value (Base Currency)':"Distributions EUR",
#         'Client - Multiple (Base Currency)':"Multiple",
#         'Company Status':"Status",
#         'LP Analyst - Industry': "LP Analyst - Industry",
#         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
#     }
#     dfc.rename(columns=rename_map, inplace=True)
    
#     # Ensure numeric types
#     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
#     for col in num_cols:
#         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

#     # 5. Metadata Mapping
#     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
#     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
#     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

#     dfc['Company Name'] = dfc['Company Name'].replace(name_map)
#     dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
#     dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
#     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
#     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

#     # 6. Merge URLs
#     if not metadata['urls'].empty:
#         urls_df = metadata['urls'].copy()
#         urls_df.rename(columns={'Organization URL': 'URL', 'LPA Num': 'LPA Num'}, inplace=True)
#         for char in URL_CHARS:
#              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
#         dfc = dfc.merge(urls_df, on='LPA Num', how='left')

#     # 7. Mode Specific Logic (Rollup)
#     if mode == 'rollup':
#         agg_rules = {
#             "Fund Name": lambda x: ', '.join(set(x.dropna())),
#             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
#             "Cost in Isomer's Share EUR": 'sum',
#             "Valuation of Isomer's Share EUR": 'sum',
#             "Distributions EUR": 'sum',
#             "Company Name": 'first',
#             "Initial Investment Date": 'first',
#             "Status": 'first', 
#             "Country": 'first',
#             "Technology Tag": 'first',
#             "Business Model": 'first',
#             "URL": 'first',
#             # Qualitative Fields
#             "Description": 'first',
#             "Long Description": 'first',
#             "SDGs": 'first',
#             "Female Founders": 'first'
#         }
#         # Handle dynamic columns
#         other_cols = [c for c in dfc.columns if c not in agg_rules and c != 'LPA Num']
#         for c in other_cols:
#             agg_rules[c] = 'first'

#         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

#     # 8. Final Calculations & Dates
#     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
#     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

#     # --- UPDATED DATE HANDLING FOR EXCEL SERIALS ---
#     # Check if the column contains numeric types (Excel Serials like 41754)
#     if pd.api.types.is_numeric_dtype(dfc['Initial Investment Date']):
#         # Convert Excel Serial Number to DateTime
#         dfc['Initial Investment Date'] = pd.to_datetime(
#             dfc['Initial Investment Date'], 
#             unit='D', 
#             origin='1899-12-30'
#         )
#     else:
#         # Standard conversion for Strings/DateObjects
#         dfc['Initial Investment Date'] = pd.to_datetime(
#             dfc['Initial Investment Date'], 
#             errors='coerce'
#         )
#     # -----------------------------------------------

#     dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
#     dfc['Invest Quarter'] = "Q" + dfc['Initial Investment Date'].dt.quarter.astype(str)

#     # 9. Status Logic
#     mask_private = dfc['Status'] == "Private"
    
#     mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#     dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
    
#     mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#     dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
    
#     mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
#     dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

#     return dfc

# import pandas as pd
# import numpy as np
# import re

# # Constants for cleaning
# BAD_CHARS = [' Ltd.', ' Ltd', ' Limited', ' AB', ' UG', ' S.A.S.', ' AG', ' Oy',
#              ' SA', ' Gmbh', ' Inc.', ' Pte.', ', Inc.', ' Aps', ' Inc', ' B.V.', ' GmbH',  ' ApS',
#              ' OY',  ' UG (Haftungsbeschrankt)', ' Co√∂peratief', '  S.A.', ' (haftungsbeschr√§nkt)', 
#              ' UG (haftungsbeschränkt)', ' UG (haftungsbeschr√§nkt)',  ' C.V.']

# URL_CHARS = ['www1.', 'www.', 'https://www.', 'https://', 'http://www.', 'http://', '/', 'en-GB', "https://uk.", 'password']

# BUSINESS_MODEL_MAP = {
#     "Fintech ": "B2C", "C2B ": "B2B", "b2b": "B2B", "B2b": "B2B"
# }
# REGION_MAP = {"MENA": "Europe"}

# def clean_portfolio_data(files_dict, metadata, mode="duplicates"):
#     """
#     Main cleaning function.
#     files_dict: {'IC I': df1, 'IC II': df2, ...}
#     metadata: {'urls': df, 'names': df, 'tags': df, 'funds': df}
#     mode: 'duplicates' (keep individual entries) or 'rollup' (merge duplicates)
#     """

#     # ... (Step 1: Label and Concatenate) ...
#     df_list = []
#     for fund_name, df in files_dict.items():
#         temp_df = df.copy()
#         temp_df['Isomer Fund'] = fund_name
#         df_list.append(temp_df)
    
#     dfc = pd.concat(df_list, ignore_index=True)

#     # 2. Basic Cleaning (Regex)
#     # Clean Company Name
#     for char in BAD_CHARS:
#         dfc['Company Short Name'] = dfc['Company Short Name'].astype(str).str.replace(char, "", regex=False)
#     # Drop Isomer II/III from RAG if they exist (Based on your notebook logic)
#     # dfc = dfc[~((dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(['Isomer II', 'Isomer III'])))]
#     rag_exclusions = ['Isomer II', 'Isomer III', 'Isomer Capital Secondaries']

#     # Normalize comparison to ensure we catch variations (optional safety step)
#     # But strictly using your provided list:
#     mask_rag_overlap = (dfc['Isomer Fund'] == 'RAG') & (dfc['Fund Name'].isin(rag_exclusions))
#     dfc = dfc[~mask_rag_overlap]

#     # 3. Column Selection & Renaming
#     cols_to_drop = ['Company Name','Client - Current Cost (Base Currency)', 
#                     'Client - Total Value (Base Currency)', 'LP Analyst - Sector', 
#                     'LP Analyst - Industry Group']
#     # Only drop if they exist
#     dfc.drop(columns=[c for c in cols_to_drop if c in dfc.columns], inplace=True)

#     rename_map = {
#         'LP Analyst Identifier':'LPA Num',
#         'Company Short Name':'Company Name',
#         'Client - Total Cost (Base Currency)': "Cost in Isomer's Share EUR",
#         'Client - Current Value (Base Currency)': "Valuation of Isomer's Share EUR",
#         'Client - Realized Value (Base Currency)':"Distributions EUR",
#         'Client - Multiple (Base Currency)':"Multiple",
#         'Company Status':"Status",
#         'LP Analyst - Industry': "LP Analyst - Industry",
#         'LP Analyst - Industry (Detailed)': "LP Analyst - Sub Industry"
#     }
#     dfc.rename(columns=rename_map, inplace=True)
    
#     # Ensure numeric types
#     num_cols = ["Cost in Isomer's Share EUR", "Valuation of Isomer's Share EUR", "Distributions EUR"]
#     for col in num_cols:
#         dfc[col] = pd.to_numeric(dfc[col], errors='coerce').fillna(0)

#     # 4. Metadata Mapping (Using DB data instead of CSV dicts)
#     # Convert DB dataframes to Dicts for mapping
#     name_map = dict(zip(metadata['names']['original_name'], metadata['names']['new_name']))
#     fund_map = dict(zip(metadata['funds']['original_fund'], metadata['funds']['cleaned_fund']))
#     tag_map = dict(zip(metadata['tags']['original_tag'], metadata['tags']['cleaned_tag']))

#     dfc['Company Name'] = dfc['Company Name'].replace(name_map)
#     dfc['Fund Name'] = dfc['Fund Name'].replace(fund_map)
#     dfc['Technology Tag'] = dfc['Technology Tag'].replace(tag_map)
#     dfc['Business Model'] = dfc['Business Model'].replace(BUSINESS_MODEL_MAP)
#     dfc['Region Group'] = dfc['Region Group'].replace(REGION_MAP)

#     # 5. Merge URLs
#     if not metadata['urls'].empty:
#         # Clean URLs in metadata first
#         urls_df = metadata['urls'].copy()
#         urls_df.rename(columns={'Organization URL': 'URL', 'LPA Num': 'LPA Num'}, inplace=True)
#         # Apply regex cleaning to URLs if needed
#         for char in URL_CHARS:
#              urls_df['URL'] = urls_df['URL'].astype(str).str.replace(char, "", regex=False)
             
#         dfc = dfc.merge(urls_df, on='LPA Num', how='left')

#     # 6. Mode Specific Logic
#     if mode == 'rollup':
#         # Summing logic for 'Rolled Up' view
#         group_cols = ['LPA Num'] # Group by Identifier 
        
#         # Aggregation rules
#         agg_rules = {
#             "Fund Name": lambda x: ', '.join(set(x.dropna())),
#             "Isomer Fund": lambda x: ', '.join(set(x.dropna())),
#             "Cost in Isomer's Share EUR": 'sum',
#             "Valuation of Isomer's Share EUR": 'sum',
#             "Distributions EUR": 'sum',
#             # Keep first for static fields
#             "Company Name": 'first',
#             "Initial Investment Date": 'first',
#             "Status": 'first', 
#             "Country": 'first',
#             "Technology Tag": 'first',
#             "Business Model": 'first',
#             "URL": 'first'
#         }
#         # Handle columns that might not exist or need simple 'first'
#         other_cols = [c for c in dfc.columns if c not in agg_rules and c != 'LPA Num']
#         for c in other_cols:
#             agg_rules[c] = 'first'

#         dfc = dfc.groupby('LPA Num', as_index=False).agg(agg_rules)

#     # 7. Final Calculations
#     dfc['Multiple'] = (dfc["Valuation of Isomer's Share EUR"] + dfc["Distributions EUR"]) / dfc["Cost in Isomer's Share EUR"]
#     dfc['Multiple'] = dfc['Multiple'].fillna(0).replace([np.inf, -np.inf], 0).round(1)

#     # Calculate Dates
#     dfc['Initial Investment Date'] = pd.to_datetime(dfc['Initial Investment Date'])
#     dfc['Invest Year'] = dfc['Initial Investment Date'].dt.year
#     dfc['Invest Quarter'] = "Q" + dfc['Initial Investment Date'].dt.quarter.astype(str)

#     # 8. Status Logic
#     # (Replicating the logic: if Private but has value/dist/multiple, change status)
#     mask_private = dfc['Status'] == "Private"
    
#     # Exited
#     mask_exited = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#     dfc.loc[mask_private & mask_exited, 'Status'] = "Exited"
    
#     # Partial Exit
#     mask_partial = (dfc["Valuation of Isomer's Share EUR"] > 0) & (dfc['Multiple'] > 0) & (dfc['Distributions EUR'] > 0)
#     dfc.loc[mask_private & mask_partial, 'Status'] = "Partial Exit"
    
#     # Write Off
#     mask_writeoff = (dfc["Valuation of Isomer's Share EUR"] == 0) & (dfc['Multiple'] == 0)
#     dfc.loc[mask_private & mask_writeoff, 'Status'] = "Write Off"

#     return dfc