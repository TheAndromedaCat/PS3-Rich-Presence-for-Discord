#!/usr/bin/env python3
# ^ This is a shebang that essentially tells Linux devices what to run this script with
# The line is ignored unless directly executed in the shell (`./PS3RPD.py`)
import os
import shutil
import subprocess
import sys


def ask_install_uv():
    print("uv package manager is not installed.")
    is_windows = sys.platform == "win32" or os.name == "nt"
    if is_windows:
        print("uv can be installed automatically via pip, or dependencies can be installed directly.")
    else:
        print("uv can be installed via curl with the following command:")
        print("curl -LsSf https://astral.sh/uv/install.sh | sh")

    choice = input("Would you like to install dependencies / uv now? [Y/n]: ").strip().lower()
    if choice in ("", "y", "yes"):
        if is_windows:
            try:
                print("Installing uv via pip...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "uv"])
                print("uv installed successfully.")
                return True
            except Exception as e:
                print(f"Failed to install uv via pip: {e}")
                print("Installing required packages directly via pip...")
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "bs4", "networkscan", "pypresence", "requests"]
                    )
                    print("Dependencies installed successfully.")
                    return "pip_direct"
                except Exception as e2:
                    print(f"Direct dependency installation failed: {e2}")
                    input("\nPress Enter to exit...")
                    sys.exit(1)
        else:
            if shutil.which("curl") is None:
                print("`curl` not found, cannot run command")
                print("Please install curl before running again")
                input("\nPress Enter to exit...")
                sys.exit(1)
            try:
                subprocess.check_call(
                    ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]
                )
                print("uv installed successfully.")
                print("Please reload your shell (`exec $SHELL`) and run the script again.")
                sys.exit(0)
            except Exception as e:
                print(f"Installation failed: {e}")
                input("\nPress Enter to exit...")
                sys.exit(1)
    else:
        print("uv is required to run the script with dependencies. Exiting.")
        input("\nPress Enter to exit...")
        sys.exit(1)


def run_with_uv():
    uv_cmd = shutil.which("uv") or shutil.which("uv.exe") or "uv"
    args = [uv_cmd, "run", "--script", "./PS3RPD.py"]
    try:
        subprocess.check_call(args)
    except Exception as e:
        print(f"Failed to run script with uv: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)


def run_directly():
    try:
        subprocess.check_call([sys.executable, "./PS3RPD.py"])
    except Exception as e:
        print(f"Failed to run script directly: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)


def main():
    try:
        if shutil.which("uv") is None and shutil.which("uv.exe") is None:
            res = ask_install_uv()
            if res == "pip_direct":
                run_directly()
            else:
                run_with_uv()
        else:
            run_with_uv()
    except Exception as e:
        print(f"An error occurred: {e}")
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
