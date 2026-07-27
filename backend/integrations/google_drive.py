# backend/integrations/google_drive.py
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

def list_pdfs_in_folder(creds, folder_id: str) -> list[dict]:
    service = build("drive", "v3", credentials=creds)
    query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    files, page_token = [], None

    while True:
        resp = service.files().list(
            q=query, spaces="drive",
            fields="nextPageToken, files(id, name, modifiedTime, size)",
            pageToken=page_token,
        ).execute()
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files

def download_file(creds, file_id: str, dest_path: str) -> str:
    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.close()
    return dest_path