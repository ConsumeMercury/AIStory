"""
Named save slots — copy managed game files to saves/<slot>/.
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone

from storage import BASE_DIR, MANAGED_PATHS, load, save, full_path

SAVES_DIR = "saves"
SLOT_INDEX = "saves/index.json"
_SLOT_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def _slot_dir(slot_id):
    if not _SLOT_RE.match(slot_id or ""):
        raise ValueError("Slot id must be 1-32 chars: letters, numbers, _ or -")
    return os.path.join(BASE_DIR, SAVES_DIR, slot_id)


def list_slots():
    index = load(SLOT_INDEX, {})
    slots = []
    root = full_path(SAVES_DIR)
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            if name == "index.json" or not os.path.isdir(os.path.join(root, name)):
                continue
            meta = index.get(name, {})
            slots.append({
                "id": name,
                "label": meta.get("label", name),
                "updated_at": meta.get("updated_at"),
                "character": meta.get("character"),
            })
    return slots


def save_slot(slot_id, label=None):
    slot_id = slot_id.strip()
    dest = _slot_dir(slot_id)
    os.makedirs(dest, exist_ok=True)
    character = None
    for rel in MANAGED_PATHS:
        src = full_path(rel)
        if not os.path.exists(src):
            continue
        sub = os.path.join(dest, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        shutil.copy2(src, sub)
        if rel == "player/player.json" and character is None:
            player = load(rel, {})
            character = player.get("name")

    index = load(SLOT_INDEX, {})
    index[slot_id] = {
        "label": label or slot_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "character": character,
    }
    save(SLOT_INDEX, index)
    return index[slot_id]


def load_slot(slot_id):
    slot_id = slot_id.strip()
    src_root = _slot_dir(slot_id)
    if not os.path.isdir(src_root):
        raise FileNotFoundError(f"Save slot not found: {slot_id}")

    for rel in MANAGED_PATHS:
        src = os.path.join(src_root, rel.replace("/", os.sep))
        if os.path.isfile(src):
            dest = full_path(rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
    return load(SLOT_INDEX, {}).get(slot_id, {"id": slot_id})


def delete_slot(slot_id):
    slot_id = slot_id.strip()
    path = _slot_dir(slot_id)
    if os.path.isdir(path):
        shutil.rmtree(path)
    index = load(SLOT_INDEX, {})
    index.pop(slot_id, None)
    save(SLOT_INDEX, index)
