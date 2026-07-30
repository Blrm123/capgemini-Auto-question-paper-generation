# backend/integrations/sync_tracker.py
import json
import os

def load_sync_state(state_path: str) -> dict:
    if os.path.exists(state_path):
        with open(state_path) as f:
            return json.load(f)
    return {}

def filter_new_or_updated(files: list[dict], sync_state: dict) -> list[dict]:
    return [f for f in files if sync_state.get(f["id"]) != f.get("modifiedTime")]

def save_sync_state(files: list[dict], state_path: str):
    with open(state_path, "w") as f:
        json.dump({f["id"]: f.get("modifiedTime") for f in files}, f, indent=2)