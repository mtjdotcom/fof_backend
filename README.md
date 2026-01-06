# Isomer Capital Data Hub

**Automated ELT Pipeline & Cleaning Tool for Venture Capital Portfolio Data.**

This Streamlit application automates the quarterly data cleaning process for Isomer Capital's funds. It ingests raw Excel spreadsheets from underlying managers, normalizes the data (handling currency, duplicates, and entity name changes), and stores granular line-item data into a central SQLite database (synced with Google Drive/Box).

## 🚀 Features

* **Quarterly Cleaning Engine**: Upload raw Excel files for multiple funds (IC I, II, III, RAG, Opps, Sec I).
* **Auto-Duplicate Handling**:
    * **Granular Mode**: Preserves individual fund entries for database integrity.
    * **Rolled-Up Mode**: Aggregates data by company for clean reporting and downloads.
* **Metadata Management**:
    * Auto-detects new portfolio companies from uploaded files.
    * Interface to map "Legal Names" to "Common Names".
    * Manage URLs, Technology Tags, and Fund Commitments.
* **Central Repository**: Stores a persistent history of all portfolio performance in a relational database.
* **Cloud Sync**: Automatically syncs the SQLite database file with Google Drive to prevent data loss in ephemeral environments.

---

## 📂 Project Structure

```text
isomer_cleaning_tool/
├── app.py                      # Main Application Entry Point
├── requirements.txt            # Python Dependencies
├── README.md                   # Documentation
├── pages/
│   ├── 1_Run_Cleaning.py       # Main Cleaning & Ingestion Workflow
│   └── 2_Manage_Metadata.py    # URL/Name/Fund Management Tool
├── src/
│   ├── __init__.py
│   ├── cleaning.py             # Core Pandas Logic (Transformation Layer)
│   ├── database.py             # Database Schema & Interaction Layer
│   └── drive_sync.py           # Google Drive Sync Utility
├── scripts/
│   └── ingest_history.py       # Script for one-time historical data loading
└── data/                       # Local storage for DB (ignored in git)
    └── isomer_central_repo.db