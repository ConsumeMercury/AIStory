"""
Restore world data from backup_saves/ and strip audit fixture pollution.

  python scripts/restore_world_backup.py
  python scripts/restore_world_backup.py --archive-events
"""

import argparse
import copy
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BACKUP_ROOT = os.path.join(ROOT, "backup_saves")

RESTORE_FILES = (
    ("characters/npcs.json", "characters/npcs.json"),
    ("characters/relationships.json", "characters/relationships.json"),
    ("characters/npc_memories.json", "characters/npc_memories.json"),
    ("characters/monsters.json", "characters/monsters.json"),
    ("world/areas.json", "world/areas.json"),
    ("world/institutions.json", "world/institutions.json"),
    ("world/world_state.json", "world/world_state.json"),
)


def restore_world_backup(*, archive_events=False):
    from storage import load
    from scripts.simulation_audit import _cleanup_audit_fixtures

    if not os.path.isdir(BACKUP_ROOT):
        raise RuntimeError(f"Missing backup directory: {BACKUP_ROOT}")

    restored = []
    for rel_src, rel_dst in RESTORE_FILES:
        src = os.path.join(BACKUP_ROOT, rel_src.replace("/", os.sep))
        dst = os.path.join(ROOT, rel_dst.replace("/", os.sep))
        if not os.path.isfile(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rel_dst)

    player = load("player/player.json", {})
    npcs = load("characters/npcs.json", {})
    _cleanup_audit_fixtures(npcs, player)

    if archive_events:
        from simulation.event_archiver import maybe_archive_events

        maybe_archive_events(force=True)

    return restored


def main():
    parser = argparse.ArgumentParser(description="Restore world files from backup_saves/")
    parser.add_argument(
        "--archive-events",
        action="store_true",
        help="Archive cold events after restore (trim hot event log)",
    )
    args = parser.parse_args()
    restored = restore_world_backup(archive_events=args.archive_events)
    print("Restored:")
    for path in restored:
        print(f"  {path}")
    if args.archive_events:
        print("Archived cold events from hot log.")


if __name__ == "__main__":
    main()
