import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database import init_db, save_raw_data

def seed_raw_history():
    print("🗑️  Creating/Clearing Raw Data Table...")
    init_db()
    
    # 1. Load Isomer History
    print("📦 Processing Isomer History...")
    try:
        iso_df = pd.read_csv("data/historic_data.csv")
        # Add a quarter column if it's missing in the raw CSV (Optional)
        # iso_df['Reporting Quarter'] = 'Historic' 
        save_raw_data(iso_df, "Historic_Isomer_CSV")
        print(f"   ✅ Saved {len(iso_df)} rows.")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 2. Load RAG History
    print("📦 Processing RAG History...")
    try:
        rag_df = pd.read_csv("data/rag_historic_data.csv")
        save_raw_data(rag_df, "Historic_RAG_CSV")
        print(f"   ✅ Saved {len(rag_df)} rows.")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    seed_raw_history()