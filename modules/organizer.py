"""
organize_pipeline.py
--------------------
Organizes Python files from a source folder into the
roblox_rants_pipeline project structure.

Usage:
    python organize_pipeline.py

Source folder : C:\\Users\\ROG STRIX G15\\Downloads\\files
Target folder : C:\\Users\\ROG STRIX G15\\Downloads\\roblox_rants_pipeline
"""

import os
import shutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SOURCE_DIR = r"C:\Users\ROG STRIX G15\Downloads\files"
TARGET_DIR = r"C:\Users\ROG STRIX G15\Downloads\roblox_rants_pipeline"

# Maps each expected filename → its destination inside TARGET_DIR
FILE_MAP = {
    # Root-level files
    "main.py":            "",
    "config.json":        "",
    "requirements.txt":   "",
    ".env.example":       "",
    ".gitignore":         "",

    # modules/ package
    "__init__.py":        "modules",
    "script_generator.py":   "modules",
    "voiceover_generator.py":"modules",
    "gameplay_randomizer.py":"modules",
    "subtitle_generator.py": "modules",
    "video_assembler.py":    "modules",
    "output_logger.py":      "modules",
}

# Empty folders to create even if no files go there
EMPTY_FOLDERS = [
    "gameplay",
    "scripts",
    "audio",
    "exports",
    "logs",
    "modules",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_structure(target: str) -> None:
    """Create all required project folders."""
    for folder in EMPTY_FOLDERS:
        path = os.path.join(target, folder)
        os.makedirs(path, exist_ok=True)
    os.makedirs(target, exist_ok=True)
    print(f"✅ Folder structure created under:\n   {target}\n")


def collect_source_files(source: str) -> dict:
    """
    Walk the source directory and return a flat dict of
    filename → full_path for every .py and .json file found.
    """
    found = {}
    for root, _, files in os.walk(source):
        for fname in files:
            if fname.endswith((".py", ".json", ".txt", ".example", ".gitignore")):
                # If duplicate names exist, last one wins (warn user)
                if fname in found:
                    print(f"  ⚠️  Duplicate filename found: '{fname}' — using latest.")
                found[fname] = os.path.join(root, fname)
    return found


def organize(source: str, target: str) -> None:
    """Main organizer logic."""
    if not os.path.exists(source):
        print(f"❌ Source folder not found:\n   {source}")
        print("   Make sure the path exists and try again.")
        return

    print(f"📂 Source : {source}")
    print(f"📁 Target : {target}\n")

    # Step 1 — create folder structure
    create_structure(target)

    # Step 2 — scan source for available files
    available = collect_source_files(source)
    print(f"🔍 Found {len(available)} file(s) in source folder.\n")

    # Step 3 — copy each mapped file to its destination
    copied, skipped, missing = [], [], []

    for filename, subfolder in FILE_MAP.items():
        if filename not in available:
            missing.append(filename)
            continue

        src_path = available[filename]
        dest_folder = os.path.join(target, subfolder) if subfolder else target
        dest_path = os.path.join(dest_folder, filename)

        # Don't overwrite if already identical
        if os.path.exists(dest_path) and _same_content(src_path, dest_path):
            skipped.append(filename)
            continue

        shutil.copy2(src_path, dest_path)
        copied.append((filename, subfolder or "root"))

    # Step 4 — copy any extra .py files not in FILE_MAP to modules/ as a catch-all
    mapped_names = set(FILE_MAP.keys())
    extras = [
        (fname, path) for fname, path in available.items()
        if fname.endswith(".py") and fname not in mapped_names
    ]
    for fname, src_path in extras:
        dest_path = os.path.join(target, "modules", fname)
        shutil.copy2(src_path, dest_path)
        copied.append((fname, "modules (auto)"))

    # Step 5 — print summary
    _print_summary(copied, skipped, missing, target)


def _same_content(path_a: str, path_b: str) -> bool:
    """Return True if both files have identical content."""
    try:
        with open(path_a, "rb") as a, open(path_b, "rb") as b:
            return a.read() == b.read()
    except Exception:
        return False


def _print_summary(copied, skipped, missing, target) -> None:
    print("=" * 55)
    print("  ORGANIZATION COMPLETE")
    print("=" * 55)

    if copied:
        print(f"\n  ✅ Copied ({len(copied)}):")
        for fname, dest in copied:
            print(f"     {fname:35s} → /{dest}")

    if skipped:
        print(f"\n  ⏭️  Skipped — already up to date ({len(skipped)}):")
        for fname in skipped:
            print(f"     {fname}")

    if missing:
        print(f"\n  ⚠️  Not found in source ({len(missing)}):")
        for fname in missing:
            print(f"     {fname}")

    print(f"\n  📁 Output: {target}")
    print("=" * 55)

    # Print final tree
    print("\n  Project tree:")
    _print_tree(target)


def _print_tree(root: str, prefix: str = "  ") -> None:
    """Print a visual directory tree of the target folder."""
    entries = sorted(os.listdir(root))
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        full_path = os.path.join(root, entry)
        print(f"{prefix}{connector}{entry}")
        if os.path.isdir(full_path):
            extension = "    " if i == len(entries) - 1 else "│   "
            _print_tree(full_path, prefix + extension)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    organize(SOURCE_DIR, TARGET_DIR)