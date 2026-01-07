# import streamlit as st
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
# import io
# import os

# # Constants
# SCOPES = ['https://www.googleapis.com/auth/drive']
# SERVICE_ACCOUNT_INFO = st.secrets["gcp_service_account"] # We will set this next
# FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID" # Get this from the URL of your Drive folder
# DB_FILENAME = "isomer_central_repo.db"
# LOCAL_DB_PATH = f"data/{DB_FILENAME}"

import streamlit as st
# Wrap imports to avoid crashes if google libs aren't installed
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
except ImportError:
    pass
import io
import os

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive']
DB_FILENAME = "isomer_central_repo.db"
LOCAL_DB_PATH = f"data/{DB_FILENAME}"

def authenticate():
    # MOVED INSIDE: Only checks for secrets when this function is called
    if "gcp_service_account" not in st.secrets:
        return None
        
    service_account_info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def download_db_from_drive():
    # Check if we can authenticate first
    if "gcp_service_account" not in st.secrets:
        print("Skipping Drive download: No secrets found.")
        return False

    service = authenticate()
    if not service: return False
    
    FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID" # You'll set this later
    
    # ... (Rest of logic remains same, but safe now)
    return True

def upload_db_to_drive():
    # Check if we can authenticate first
    if "gcp_service_account" not in st.secrets:
        print("Skipping Drive upload: No secrets found.")
        return
        
    service = authenticate()
    if not service: return

    # ... (Rest of logic remains same)

def authenticate():
    creds = service_account.Credentials.from_service_account_info(
        SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def download_db_from_drive():
    """Checks out the DB from Drive to local temp storage"""
    service = authenticate()
    
    # Search for the file in the specific folder
    query = f"name = '{DB_FILENAME}' and '{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if not items:
        return False # File doesn't exist yet (first run)

    # Download existing file
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(LOCAL_DB_PATH, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return True

def upload_db_to_drive():
    """Checks in the DB from local storage to Drive (Overwrites)"""
    service = authenticate()
    
    # Search if file exists to update it, otherwise create new
    query = f"name = '{DB_FILENAME}' and '{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])

    media = MediaFileUpload(LOCAL_DB_PATH, mimetype='application/x-sqlite3', resumable=True)

    if items:
        # Update existing file
        file_id = items[0]['id']
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # Create new file
        file_metadata = {'name': DB_FILENAME, 'parents': [FOLDER_ID]}
        service.files().create(body=file_metadata, media_body=media).execute()