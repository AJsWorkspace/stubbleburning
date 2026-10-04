import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from googleapiclient.http import MediaIoBaseDownload
import io

# =========================================================
# GOOGLE DRIVE CONFIGURATION
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

BASE_DIR = os.path.dirname(__file__)

SERVICE_ACCOUNT_FILE = os.path.join(
    BASE_DIR,
    "stubbleburning-api-dbbb45eb2716.json"
)

# =========================================================
# AUTHENTICATE GOOGLE DRIVE
# =========================================================

def authenticate_drive():

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )

    drive_service = build(
        "drive",
        "v3",
        credentials=credentials
    )

    print("✓ Google Drive authenticated successfully.")

    return drive_service

# =========================================================
# Metadata CSV
# =========================================================
METADATA_FILENAME = "metadata.csv"

columns = [
    "AOI",
    "Season",
    "Year",
    "Date",
    "Tile_ID",
    "Image_ID",
    "Avg_Cloud_Pct",
    "AOI_Coverage_Pct",
    "System_Footprint"
]

def load_metadata():

    drive_service = authenticate_drive()

    # Search for metadata.csv
    results = drive_service.files().list(
        q=f"name='{METADATA_FILENAME}' and trashed=false",
        fields="files(id, name)"
    ).execute()

    files = results.get("files", [])

    if not files:

        print("metadata.csv not found.")

        metadata_df = pd.DataFrame(columns=columns)

        return metadata_df

    file_id = files[0]["id"]

    request = drive_service.files().get_media(fileId=file_id)

    file_stream = io.BytesIO()

    downloader = MediaIoBaseDownload(file_stream, request)

    done = False

    while not done:
        _, done = downloader.next_chunk()

    file_stream.seek(0)

    metadata_df = pd.read_csv(file_stream)

    print(f"Loaded {len(metadata_df)} existing records.")

    return metadata_df

if __name__ == "__main__":

    metadata_df = load_metadata()

    #print(metadata_df.head())