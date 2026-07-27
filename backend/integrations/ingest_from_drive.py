# backend/integrations/ingest_from_drive.py
import os
from backend.integrations.google_auth import load_credentials
from backend.integrations.google_drive import list_pdfs_in_folder, download_file
from backend.integrations.sync_tracker import load_sync_state, filter_new_or_updated, save_sync_state

STAGING_DIR = "data/staged_uploads"
SYNC_STATE_PATH = "data/drive_sync_state.json"

def ingest_drive_folder(folder_id: str, token_path: str) -> list[str]:
    creds = load_credentials(token_path)
    if creds is None:
        raise RuntimeError("Not authenticated. Call /auth/login first.")

    all_files = list_pdfs_in_folder(creds, folder_id)
    sync_state = load_sync_state(SYNC_STATE_PATH)
    to_fetch = filter_new_or_updated(all_files, sync_state)

    os.makedirs(STAGING_DIR, exist_ok=True)
    downloaded_paths = []
    for f in to_fetch:
        dest = os.path.join(STAGING_DIR, f["name"])
        download_file(creds, f["id"], dest)
        downloaded_paths.append(dest)

    save_sync_state(all_files, SYNC_STATE_PATH)
    return downloaded_paths  # hand this list straight to loader.py