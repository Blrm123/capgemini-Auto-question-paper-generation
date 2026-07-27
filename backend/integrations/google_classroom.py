# backend/integrations/google_classroom.py
from googleapiclient.discovery import build

def list_courses(creds) -> list[dict]:
    service = build("classroom", "v1", credentials=creds)
    return service.courses().list(courseStates=["ACTIVE"]).execute().get("courses", [])

def list_material_drive_files(creds, course_id: str) -> list[dict]:
    service = build("classroom", "v1", credentials=creds)
    materials, page_token = [], None

    while True:
        resp = service.courses().courseWorkMaterials().list(
            courseId=course_id, pageToken=page_token
        ).execute()
        for m in resp.get("courseWorkMaterial", []):
            for att in m.get("materials", []):
                drive_file = att.get("driveFile", {}).get("driveFile")
                if drive_file:
                    materials.append(drive_file)  # has 'id', 'title'
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return materials