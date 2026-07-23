"""
Build script for PS3 Rich Presence for Discord.
Compiles PyInstaller binaries and packages all release assets into dist/
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"


def run_cmd(cmd):
    print(f"\n==> Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=ROOT)
    if res.returncode != 0:
        print(f"Error: Command failed with exit code {res.returncode}")
        sys.exit(res.returncode)


def main():
    print("==================================================")
    print("   PS3 Rich Presence for Discord - Build Script   ")
    print("==================================================")

    # Stop running instances if any
    if sys.platform == "win32":
        subprocess.run("taskkill /F /IM PS3RPD.exe /IM PS3RPD_GUI.exe 2>NUL", shell=True)

    DIST.mkdir(exist_ok=True)

    # 1. Build PS3RPD_GUI.exe
    print("\n[1/4] Compiling dist/PS3RPD_GUI.exe...")
    run_cmd(
        'pyinstaller --windowed --onefile --icon=icon.ico --add-data "icon.ico;." '
        "--collect-all TKinterModernThemes --name=PS3RPD_GUI --noconfirm PS3RPD_GUI.py"
    )

    # 2. Build PS3RPD.exe
    print("\n[2/4] Compiling dist/PS3RPD.exe...")
    run_cmd('pyinstaller --onefile --icon=icon.ico --add-data "icon.ico;." --name=PS3RPD --noconfirm PS3RPD.py')

    # 3. Copy standalone PS3RPD.py to dist/
    print("\n[3/4] Copying PS3RPD.py -> dist/PS3RPD.py...")
    shutil.copy2(ROOT / "PS3RPD.py", DIST / "PS3RPD.py")

    # 4. Package Python source ZIP archive
    print("\n[4/4] Packaging dist/PS3RPD-GUI-v2.1.0-Python.zip...")
    zip_path = DIST / "PS3RPD-GUI-v2.1.0-Python.zip"
    files_to_zip = ["PS3RPD_GUI.py", "PS3RPD.py", "start.py", "icon.ico", "README.md"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files_to_zip:
            fp = ROOT / fname
            if fp.is_file():
                zf.write(fp, fname)
                print(f"  + Added {fname}")

    print("\n==================================================")
    print(f"SUCCESS: All release assets ready in {DIST}")
    print("==================================================")


if __name__ == "__main__":
    main()
