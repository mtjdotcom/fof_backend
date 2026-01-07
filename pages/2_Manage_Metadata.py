import streamlit as st
import pandas as pd
from src.database import load_metadata, get_engine
from sqlalchemy import text

st.set_page_config(page_title="Metadata Manager", layout="wide")

st.title("Metadata Management")
st.markdown("Use this tool to update the 'Brain' of your cleaner before processing new data.")

# --- 1. DEFINE TABS ONCE ---
tab1, tab2, tab3, tab4 = st.tabs([
    "1. Detect New Companies", 
    "2. Manage Name Mappings", 
    "3. View All Metadata", 
    "4. Fund Commitments"
])

# ---------------------------------------------------------------------
# TAB 1: NEW COMPANY DETECTOR
# ---------------------------------------------------------------------
with tab1:
    st.subheader("Auto-Detect Missing URLs")
    
    with st.expander("Upload Raw Files to Scan", expanded=True):
        raw_files = st.file_uploader(
            "Upload any/all fund files (IC I, II, III, RAG, etc.)", 
            type=['xlsx'], 
            accept_multiple_files=True
        )

    if raw_files:
        all_companies = []
        for uploaded_file in raw_files:
            try:
                # Read file (Assuming standard format with headers on row 1)
                df = pd.read_excel(uploaded_file, skiprows=[0])
                
                # We need LPA Num and Company Name to check against DB
                if 'LP Analyst Identifier' in df.columns and 'Company Short Name' in df.columns:
                    subset = df[['LP Analyst Identifier', 'Company Short Name']].dropna()
                    subset.columns = ['lpa_num', 'company_name']
                    all_companies.append(subset)
            except Exception as e:
                st.error(f"Could not read {uploaded_file.name}: {e}")

        if all_companies:
            current_quarter_df = pd.concat(all_companies).drop_duplicates(subset=['lpa_num'])
            existing_urls_df = load_metadata('meta_urls')
            
            merged = current_quarter_df.merge(
                existing_urls_df, 
                on='lpa_num', 
                how='left', 
                indicator=True
            )
            
            missing_companies = merged[merged['_merge'] == 'left_only'][['lpa_num', 'company_name']]

            if missing_companies.empty:
                st.success("✅ Good news! All companies in these files already have URLs in the database.")
            else:
                st.warning(f"⚠️ Found {len(missing_companies)} new companies without URLs.")
                st.info("Enter the URLs below. You can also fix the name if the Legal Name is messy.")

                missing_companies['url'] = ""
                missing_companies['common_name'] = missing_companies['company_name'] 
                
                missing_companies = missing_companies[['lpa_num', 'company_name', 'common_name', 'url']]

                edited_new_df = st.data_editor(
                    missing_companies,
                    column_config={
                        "lpa_num": st.column_config.NumberColumn("LPA #", disabled=True),
                        "company_name": st.column_config.TextColumn("Raw Legal Name", disabled=True),
                        "common_name": st.column_config.TextColumn("Clean Common Name", help="Edit this if you want to create a Name Mapping"),
                        "url": st.column_config.LinkColumn("Website URL (Required)", help="Enter the website (e.g. isomer.vc)")
                    },
                    hide_index=True,
                    num_rows="fixed",
                    width='stretch'
                )

                if st.button("Save New Metadata"):
                    to_save = edited_new_df[edited_new_df['url'] != ""].copy()
                    
                    if to_save.empty:
                        st.error("Please enter at least one URL before saving.")
                    else:
                        engine = get_engine()
                        with engine.connect() as conn:
                            # A. Save URLs
                            urls_payload = to_save[['lpa_num', 'url']]
                            urls_payload.to_sql('meta_urls', engine, if_exists='append', index=False)
                            
                            # B. Save Name Changes
                            name_changes = to_save[to_save['company_name'] != to_save['common_name']]
                            if not name_changes.empty:
                                name_payload = pd.DataFrame({
                                    'original_name': name_changes['company_name'],
                                    'new_name': name_changes['common_name']
                                })
                                name_payload.to_sql('meta_name_changes', engine, if_exists='append', index=False)
                        
                        st.success(f"Successfully added {len(urls_payload)} URLs and {len(name_changes)} Name Mappings!")
                        st.balloons()

# ---------------------------------------------------------------------
# TAB 2: NAME MAPPINGS
# ---------------------------------------------------------------------
with tab2:
    st.subheader("Legal Name → Common Name Mappings")
    
    name_df = load_metadata('meta_name_changes')
    
    # FIXED: Removed 'width=None'
    edited_names = st.data_editor(
        name_df,
        column_config={
            "original_name": "Original (Raw) Name",
            "new_name": "New (Clean) Name"
        },
        num_rows="dynamic", 
        width='stretch',
        key="name_editor"
    )

    if st.button("Update Name Mappings"):
        engine = get_engine()
        edited_names.to_sql('meta_name_changes', engine, if_exists='replace', index=False)
        st.success("Name mappings updated!")

# ---------------------------------------------------------------------
# TAB 3: VIEW ALL
# ---------------------------------------------------------------------
with tab3:
    st.subheader("Full Metadata Database")
    
    st.markdown("**All URLs**")
    urls_df = load_metadata('meta_urls')
    st.dataframe(urls_df, width='stretch')
    
    st.markdown("**All Tech Tags**")
    tags_df = load_metadata('meta_tech_tags')
    st.data_editor(tags_df, key="tags_editor", num_rows="dynamic", width='stretch')
    
    if st.button("Save Tech Tags"):
         engine = get_engine()
         st.session_state['tags_editor'].to_sql('meta_tech_tags', engine, if_exists='replace', index=False)
         st.success("Tags saved.")

# ---------------------------------------------------------------------
# TAB 4: MANAGE FUND COMMITMENTS
# ---------------------------------------------------------------------
with tab4:
    st.subheader("Isomer Fund Commitments")
    st.markdown("This is the master list of VC funds Isomer has invested in.")
    
    funds_df = load_metadata('isomer_funds')
    # FIX: Convert string text to DateTime objects so the Editor works
    if not funds_df.empty and 'isomer_ic_date' in funds_df.columns:
        funds_df['isomer_ic_date'] = pd.to_datetime(funds_df['isomer_ic_date'], errors='coerce')
    
    column_config = {
        "fund_name": st.column_config.TextColumn("Fund Name (Key)", help="Must match the 'Cleaned Fund Name' in your portfolio data"),
        "isomer_fund": st.column_config.SelectboxColumn("Isomer Fund", options=["Isomer Capital I", "Isomer Capital II", "Isomer Capital III", "Isomer Opportunities", "Isomer Secondaries I"]),
        "vintage_year": st.column_config.NumberColumn("Vintage", format="%d"),
        "isomer_commitment_eur": st.column_config.NumberColumn("Commitment (€)", format="€%.0f"),
        "isomer_ic_date": st.column_config.DateColumn("IC Date"),
        "lpac_seat": st.column_config.CheckboxColumn("LPAC Seat")
    }
    
    edited_funds = st.data_editor(
        funds_df,
        column_config=column_config,
        width='stretch',
        num_rows="dynamic",
        key="funds_editor"
    )
    
    if st.button("Save Fund Commitments"):
        engine = get_engine()
        edited_funds.to_sql('isomer_funds', engine, if_exists='replace', index=False)
        st.success("✅ Fund Commitments updated successfully!")