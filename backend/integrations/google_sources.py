"""Browse and import selected Google Drive and Classroom material files."""

import io
import re
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
    ),
}
SUPPORTED_MIMES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    **GOOGLE_EXPORTS,
}


def _drive(creds):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(". ") or "google_file"


def _file_payload(file: dict[str, Any]) -> dict[str, Any]:
    mime = file.get("mimeType", "")
    return {
        "id": file["id"], "name": file.get("name", "Untitled"),
        "mime_type": mime, "modified_time": file.get("modifiedTime"),
        "size": int(file.get("size", 0) or 0),
        "kind": "folder" if mime == FOLDER_MIME else "file",
        "supported": mime in SUPPORTED_MIMES,
    }


def list_drive_folder(creds, folder_id: str = "root") -> list[dict[str, Any]]:
    """List immediate children; the UI can expand folders on demand."""
    service = _drive(creds)
    items: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id,name,mimeType,modifiedTime,size),nextPageToken",
            orderBy="folder,name_natural", pageSize=100, pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        items.extend(_file_payload(item) for item in response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


def _list_supported_descendants(service, folder_id: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id,name,mimeType,modifiedTime,size),nextPageToken",
            orderBy="folder,name_natural", pageSize=100, pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        for item in response.get("files", []):
            if item.get("mimeType") == FOLDER_MIME:
                files.extend(_list_supported_descendants(service, item["id"]))
            elif item.get("mimeType") in SUPPORTED_MIMES:
                files.append(item)
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def resolve_selection(creds, file_ids: list[str], folder_ids: list[str]) -> list[dict[str, Any]]:
    """Resolve selected file and folder IDs to accessible, supported Drive files."""
    service = _drive(creds)
    selected: dict[str, dict[str, Any]] = {}
    for file_id in set(file_ids):
        item = service.files().get(
            fileId=file_id, fields="id,name,mimeType,modifiedTime,size", supportsAllDrives=True
        ).execute()
        if item.get("mimeType") in SUPPORTED_MIMES:
            selected[item["id"]] = item
    for folder_id in set(folder_ids):
        for item in _list_supported_descendants(service, folder_id):
            selected[item["id"]] = item
    return list(selected.values())


def download_selection(
    creds, file_ids: list[str], folder_ids: list[str], destination: Path, max_size_bytes: int
) -> list[Path]:
    """Download/export selected files after resolving permissions server-side."""
    service = _drive(creds)
    destination.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for item in resolve_selection(creds, file_ids, folder_ids):
        mime = item["mimeType"]
        # Drive does not always expose the size of Google-native documents.
        if item.get("size") and int(item["size"]) > max_size_bytes:
            raise ValueError(f"'{item['name']}' exceeds the configured upload limit.")
        suffix = SUPPORTED_MIMES[mime]
        path = destination / f"{item['id']}_{_safe_name(item['name'])}"
        if path.suffix.lower() != suffix:
            path = path.with_suffix(suffix)
        request = (
            service.files().export_media(fileId=item["id"], mimeType=GOOGLE_EXPORTS[mime][0])
            if mime in GOOGLE_EXPORTS else service.files().get_media(fileId=item["id"], supportsAllDrives=True)
        )
        with path.open("wb") as output:
            downloader = MediaIoBaseDownload(output, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        if path.stat().st_size > max_size_bytes:
            path.unlink(missing_ok=True)
            raise ValueError(f"'{item['name']}' exceeds the configured upload limit after export.")
        downloaded.append(path)
    return downloaded


def list_classroom_courses(creds) -> list[dict[str, Any]]:
    service = build("classroom", "v1", credentials=creds, cache_discovery=False)
    courses: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = service.courses().list(courseStates=["ACTIVE"], pageSize=100, pageToken=page_token).execute()
        courses.extend(
            {"id": course["id"], "name": course.get("name", "Untitled course"), "section": course.get("section")}
            for course in response.get("courses", [])
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            return courses


def _drive_attachments(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for item in items:
        for material in item.get("materials", []):
            drive_file = material.get("driveFile", {}).get("driveFile")
            if drive_file:
                attachments.append({"id": drive_file["id"], "name": drive_file.get("title", "Untitled"), "source": source})
    return attachments


def list_classroom_materials(creds, course_id: str) -> list[dict[str, Any]]:
    service = build("classroom", "v1", credentials=creds, cache_discovery=False)
    unique: dict[str, dict[str, Any]] = {}
    page_token = None
    while True:
        response = service.courses().courseWorkMaterials().list(
            courseId=course_id, pageSize=100, pageToken=page_token
        ).execute()
        for item in _drive_attachments(response.get("courseWorkMaterial", []), "course material"):
            unique[item["id"]] = item
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return list(unique.values())
