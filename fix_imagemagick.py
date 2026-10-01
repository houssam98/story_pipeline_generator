"""
fix_imagemagick.py
------------------
Run this ONCE after installing ImageMagick on Windows.
Automatically finds the ImageMagick binary and patches
MoviePy's config so TextClip (subtitles) works correctly.

Usage:
    python fix_imagemagick.py
"""

import os
import glob
import subprocess

# ---------------------------------------------------------------------------
# Step 1: Find ImageMagick magick.exe on this machine
# ---------------------------------------------------------------------------

COMMON_PATHS = [
    r"C:\Program Files\ImageMagick-*\magick.exe",
    r"C:\Program Files (x86)\ImageMagick-*\magick.exe",
    r"C:\ImageMagick*\magick.exe",
]

def find_imagemagick() -> str | None:
    # Try glob patterns first
    for pattern in COMMON_PATHS:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]

    # Try which/where command
    try:
        result = subprocess.run(
            ["where", "magick"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Step 2: Patch moviepy's config file
# ---------------------------------------------------------------------------

def patch_moviepy_config(magick_path: str) -> None:
    import moviepy
    moviepy_dir = os.path.dirname(moviepy.__file__)
    config_path = os.path.join(moviepy_dir, "config_defaults.py")

    if not os.path.exists(config_path):
        print(f"❌ Could not find MoviePy config at: {config_path}")
        return

    with open(config_path, "r") as f:
        content = f.read()

    # Normalize path for Python string (forward slashes, escaped)
    safe_path = magick_path.replace("\\", "/")

    # Replace the IMAGEMAGICK_BINARY line
    import re
    new_line = f'IMAGEMAGICK_BINARY = r"{magick_path}"'

    if "IMAGEMAGICK_BINARY" in content:
        # Use a lambda so the replacement string is never interpreted by re
        content = re.sub(
            r'IMAGEMAGICK_BINARY\s*=\s*.*',
            lambda _: new_line,
            content
        )
    else:
        content += f"\n{new_line}\n"

    with open(config_path, "w") as f:
        f.write(content)

    print(f"✅ Patched MoviePy config:")
    print(f"   {config_path}")
    print(f"   IMAGEMAGICK_BINARY = {magick_path}")


# ---------------------------------------------------------------------------
# Step 3: Verify it works
# ---------------------------------------------------------------------------

def verify() -> None:
    print("\n🧪 Testing TextClip render...")
    try:
        from moviepy.editor import TextClip
        clip = TextClip("TEST", fontsize=50, color="white", font="Arial")
        clip.close()
        print("✅ TextClip works! Subtitles are ready.")
    except Exception as e:
        print(f"❌ TextClip still failing: {e}")
        print("\n   Try restarting your terminal and running again.")
        print("   Or manually set the path in:")
        import moviepy
        print(f"   {os.path.join(os.path.dirname(moviepy.__file__), 'config_defaults.py')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🔍 Searching for ImageMagick...\n")

    magick = find_imagemagick()

    if not magick:
        print("❌ ImageMagick not found on this machine.")
        print("\n   Please install it from:")
        print("   https://imagemagick.org/script/download.php#windows")
        print("\n   During install, check:")
        print("   ✔ Add application directory to your system path")
        print("   ✔ Install legacy utilities (convert)")
    else:
        print(f"✅ Found ImageMagick at:\n   {magick}\n")
        patch_moviepy_config(magick)
        verify()
