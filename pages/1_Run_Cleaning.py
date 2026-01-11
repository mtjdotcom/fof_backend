import streamlit as st
import pandas as pd
from src.cleaning import clean_portfolio_data
from src.database import load_metadata, save_quarterly_data, save_raw_data, get_engine

st.set_page_config(page_title="Run Cleaning", layout="wide")

st.title("Quarterly Data Cleaning")
st.markdown("Upload your raw Excel files below to clean them and prepare them for the database.")

# --- 1. File Upload Section ---
st.subheader("1. Upload Fund Files")
st.info("Upload the raw 'No Duplicates' or standard quarterly sheets from the data provider.")

col1, col2 = st.columns(2)
with col1:
    opps_file = st.file_uploader("Isomer Opportunities", type=['xlsx'], key='opps')
    ic1_file = st.file_uploader("Isomer Capital I (IC I)", type=['xlsx'], key='ic1')
    ic2_file = st.file_uploader("Isomer Capital II (IC II)", type=['xlsx'], key='ic2')

with col2:
    ic3_file = st.file_uploader("Isomer Capital III (IC III)", type=['xlsx'], key='ic3')
    sec_file = st.file_uploader("Isomer Secondaries I", type=['xlsx'], key='sec')
    rag_file = st.file_uploader("Isomer Capital RAG", type=['xlsx'], key='rag')

# --- 2. Configuration & Run ---
st.subheader("2. Processing Settings")
mode_key = 'duplicates' # Force Detail View for DB Ingestion (Rollup happens in analysis)
st.markdown(f"**Mode:** Detail View (Preserving all line items for database)")

with st.form("cleaning_form"):
    submitted = st.form_submit_button("Run Cleaning")

    if submitted:
        files_map = {}
        # Map files to their source names (Initial 'Isomer Fund' value)
        if ic1_file: files_map['Isomer Capital I'] = pd.read_excel(ic1_file, skiprows=[0])
        if ic2_file: files_map['Isomer Capital II'] = pd.read_excel(ic2_file, skiprows=[0])
        if ic3_file: files_map['Isomer Capital III'] = pd.read_excel(ic3_file, skiprows=[0])
        if opps_file: files_map['Isomer Opportunities'] = pd.read_excel(opps_file, skiprows=[0])
        if sec_file: files_map['Isomer Secondaries I'] = pd.read_excel(sec_file, skiprows=[0])
        if rag_file: files_map['RAG'] = pd.read_excel(rag_file, skiprows=[0])
        
        if not files_map:
            st.error("Please upload at least one file.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1. Save Raw Data (The Bronze Layer)
            status_text.text("Archiving raw data to database...")
            try:
                for source_label, raw_df in files_map.items():
                    save_raw_data(raw_df, source_label)
            except Exception as e:
                st.warning(f"Could not archive raw data (Cleaning will continue): {e}")

            # 2. Load Metadata (The Brain)
            status_text.text("Fetching Metadata from Database...")
            progress_bar.progress(20)
            
            meta = {
                'urls': load_metadata('meta_urls'),
                'names': load_metadata('meta_name_changes'),
                'tags': load_metadata('meta_tech_tags'),
                'funds': load_metadata('meta_fund_names'), # FIX: Point to name cleaner
                'master_funds': load_metadata('isomer_funds') # NEW: Isomer Fund Lookup
            }
            
            # 3. Clean Data
            status_text.text("Normalizing and mapping data...")
            progress_bar.progress(40)
            
            try:
                df_result = clean_portfolio_data(files_map, meta, mode=mode_key)
                
                # Store in session state for the preview section
                st.session_state['cleaned_data'] = df_result
                st.session_state['mode_key'] = mode_key
                
                progress_bar.progress(80)
                status_text.text("Saving clean data to database...")
                
                # 4. Save to Database
                save_quarterly_data(df_result)
                
                progress_bar.progress(100)
                status_text.text("✅ Done! Data saved.")
                st.success("Cleaning Complete! Data has been ingested into the Central Repo.")
                
            except Exception as e:
                st.error(f"An error occurred during cleaning: {e}")

# --- 3. Results Preview ---
if 'cleaned_data' in st.session_state:
    df_result = st.session_state['cleaned_data']
    mode_used = st.session_state['mode_key']
    
    st.divider()
    st.subheader(f"3. Results Preview")
    
    # Calculate sums for metrics
    total_cost = df_result["Cost in Isomer's Share EUR"].sum()
    total_value = df_result["Valuation of Isomer's Share EUR"].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Cost", f"€{total_cost:,.0f}")
    m2.metric("Total Value", f"€{total_value:,.0f}")
    m3.metric("Total Rows", len(df_result))
    
    st.dataframe(df_result.head(10), width='stretch')
    
    # Download Button
    csv = df_result.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Cleaned CSV",
        data=csv,
        file_name=f"isomer_cleaned_data_{mode_used}.csv",
        mime='text/csv',
    )

# import streamlit as st
# import pandas as pd
# from io import BytesIO
# from src.cleaning import clean_portfolio_data
# from src.database import load_metadata, save_quarterly_data
# from src.database import save_quarterly_data, save_raw_data, get_engine

# st.set_page_config(page_title="Run Cleaning", layout="wide")

# st.title("Quarterly Data Cleaning")
# st.markdown("Upload your raw Excel files below to clean them and prepare them for the database.")

# # --- 1. File Upload Section ---
# with st.form("upload_form"):
#     st.subheader("1. Upload Fund Files")
#     st.info("Upload the raw 'No Duplicates' or standard quarterly sheets from the data provider.")
    
#     col1, col2 = st.columns(2)
    
#     with col1:
#         ic1_file = st.file_uploader("Isomer Capital I (IC I)", type=['xlsx'])
#         ic2_file = st.file_uploader("Isomer Capital II (IC II)", type=['xlsx'])
#         ic3_file = st.file_uploader("Isomer Capital III (IC III)", type=['xlsx'])
    
#     with col2:
#         rag_file = st.file_uploader("Isomer Capital RAG", type=['xlsx'])
#         opps_file = st.file_uploader("Isomer Opportunities", type=['xlsx'])
#         sec_file = st.file_uploader("Isomer Secondaries I", type=['xlsx'])

#     st.subheader("2. Processing Settings")
    
#     # This determines how the CSV download looks
#     cleaning_mode = st.radio(
#         "Select Output View (for CSV Download)", 
#         ["Rolled Up (Aggregated by Company)", "With Duplicates (Detail View)"],
#         index=0,
#         help="Rolled Up combines multiple fund holdings into one line per company. With Duplicates keeps every fund entry separate."
#     )
    
#     submitted = st.form_submit_button("Run Cleaning")

# # --- 2. Processing Logic ---
# if submitted:
#     # Check if at least one file was uploaded
#     files_uploaded = [f for f in [ic1_file, ic2_file, ic3_file, rag_file, opps_file, sec_file] if f is not None]
    
#     if not files_uploaded:
#         st.error("⚠️ Please upload at least one fund file to proceed.")
#     else:
#         # Load files into a dictionary map
#         files_map = {}
#         try:
#             # Note: Adjust 'skiprows' if your provider changes format. 
#             # Currently assuming row 0 is metadata and row 1 is headers.
#             if ic1_file: files_map['IC I'] = pd.read_excel(ic1_file, skiprows=[0])
#             if ic2_file: files_map['IC II'] = pd.read_excel(ic2_file, skiprows=[0])
#             if ic3_file: files_map['IC III'] = pd.read_excel(ic3_file, skiprows=[0])
#             if rag_file: files_map['RAG'] = pd.read_excel(rag_file, skiprows=[0])
#             if opps_file: files_map['Opportunities'] = pd.read_excel(opps_file, skiprows=[0])
#             if sec_file: files_map['Secondaries'] = pd.read_excel(sec_file, skiprows=[0])
            
#             # ... (inside the if submitted: block) ...
            
#             st.success(f"Successfully loaded {len(files_map)} files.")

#             # 1. Save Raw Data (The Bronze Layer)
#             with st.spinner("Archiving raw data to database..."):
#                  try:
#                      for source_label, raw_df in files_map.items():
#                          save_raw_data(raw_df, source_label)
#                  except Exception as e:
#                      st.warning(f"Could not archive raw data (Cleaning will continue): {e}")

#             # 2. Load Metadata (The Brain)
#             with st.spinner("Fetching Metadata from Database..."):
#                 # YOU WERE LIKELY MISSING THIS LINE 'meta = {'
#                 meta = {
#                     'urls': load_metadata('meta_urls'),
#                     'names': load_metadata('meta_name_changes'),
#                     'tags': load_metadata('meta_tech_tags'),
#                     'funds': load_metadata('isomer_funds')
#                 }
            
#             # 3. Clean Data
#             # Run Cleaning
#             with st.spinner("Cleaning and normalizing data..."):
#                 # Determine mode string for the function
#                 mode_key = 'rollup' if "Rolled Up" in cleaning_mode else 'duplicates'
                
#                 # Perform the cleaning
#                 cleaned_df = clean_portfolio_data(files_map, meta, mode=mode_key)
                
#                 # Store results in session state so they persist after button click
#                 st.session_state['cleaned_data'] = cleaned_df
#                 st.session_state['files_map'] = files_map # Keep raw files for re-cleaning if needed
#                 st.session_state['meta_cache'] = meta
#                 st.session_state['mode_key'] = mode_key
                
#         except Exception as e:
#             st.error(f"An error occurred during processing: {e}")

# # --- 3. Results & Actions Section ---
# if 'cleaned_data' in st.session_state:
#     df_result = st.session_state['cleaned_data']
#     mode_used = st.session_state['mode_key']
    
#     st.divider()
#     st.subheader(f"3. Results Preview ({mode_used.title()} Mode)")
    
#     # Show key metrics
#     # FIX: Calculate sums first to avoid backslash errors in f-strings
#     total_cost = df_result["Cost in Isomer's Share EUR"].sum()
#     total_value = df_result["Valuation of Isomer's Share EUR"].sum()

#     m1, m2, m3 = st.columns(3)
#     m1.metric("Total Cost", f"€{total_cost:,.0f}")
#     m2.metric("Total Value", f"€{total_value:,.0f}")
#     m3.metric("Total Rows", len(df_result))
    
#     # Data Preview
#     st.dataframe(df_result.head(10), width='stretch')
    
#     col_download, col_db = st.columns([1, 2])
    
#     # ... (Rest of the file remains the same)

#     # --- B. Database Save Section ---
#     with col_db:
#         st.write("### Save to Central Repository")
#         st.caption("This pushes data to the main SQLite database for long-term tracking.")
        
#         with st.form("db_save_form"):
#             quarter_label = st.text_input("Reporting Quarter Label (Required)", placeholder="e.g., Q3 2024")
            
#             save_submitted = st.form_submit_button("Save to Database")
            
#             if save_submitted:
#                 if not quarter_label:
#                     st.error("Please enter a Quarter Label (e.g., 'Q3 2024') before saving.")
#                 else:
#                     try:
#                         with st.spinner("Saving to Central Repository..."):
#                             # CRITICAL: Always save in 'duplicates' (granular) mode
#                             # If the user cleaned in 'rollup' mode, we re-run cleaning in 'duplicates' mode first.
#                             if mode_used == 'rollup':
#                                 st.info("Re-generating granular data for database storage...")
#                                 df_to_save = clean_portfolio_data(
#                                     st.session_state['files_map'], 
#                                     st.session_state['meta_cache'], 
#                                     mode='duplicates'
#                                 )
#                             else:
#                                 df_to_save = df_result

#                             # Execute Save
#                             save_quarterly_data(df_to_save, quarter_label)
#                             st.success(f"✅ Success! Data for **{quarter_label}** has been added to the database.")
                            
#                     except ValueError as e:
#                         # Handles the "Data for Q3 2024 already exists" error
#                         st.error(f"❌ Error: {e}")
#                     except Exception as e:
#                         st.error(f"❌ An unexpected database error occurred: {e}")