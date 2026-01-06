import streamlit as st
from src.database import init_db

st.set_page_config(page_title="Isomer Data Tool", layout="wide")

def main():
    st.title("Isomer Capital Data Hub")
    
    # Initialize DB on app start
    init_db()

    st.markdown("""
    ### Welcome
    This tool automates the quarterly cleaning of portfolio data.
    
    **Get Started:**
    1. Go to **Run Cleaning** to upload spreadsheets and generate clean data.
    2. Go to **Manage Metadata** to add new company URLs or fix name mappings.
    """)

    st.info("Ensure you are connected to Box Drive so the database can be synced.")

if __name__ == "__main__":
    main()