#!/usr/bin/env python3
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# Set AppUserModelID on Windows so taskbar uses icon.ico instead of Python default
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TheAndromedaCat.PS3RPD.GUI")
    except Exception:
        pass

# PIL & PyStray for System Tray support
try:
    from PIL import Image, ImageTk, ImageDraw
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# TKinterModernThemes for Azure / Sun-Valley / Park themes
try:
    import TKinterModernThemes as TKMT
    HAS_TKMT = True
except ImportError:
    HAS_TKMT = False

# Import core PS3RPD backend logic
from PS3RPD import PrepWork, GatherDetails, default_config, headers


def get_system_mode():
    """Detects whether Windows/OS is currently using Dark or Light mode."""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val == 1 else "dark"
        except Exception:
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\DWM",
                )
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return "light" if val == 1 else "dark"
            except Exception:
                pass
    return "dark"


_themes_loaded = False


_themes_loaded = False


def load_all_modern_themes(root):
    """Sources all TCL theme files from TKinterModernThemes into the Tkinter interpreter once."""
    global _themes_loaded
    if _themes_loaded or not HAS_TKMT:
        return
    for theme in ["azure", "sun-valley", "park"]:
        try:
            tcl_path = os.path.abspath(TKMT.__file__ + f"/../themes/{theme}/{theme}.tcl")
            if os.path.isfile(tcl_path):
                try:
                    root.tk.call("source", tcl_path)
                except tk.TclError:
                    pass
        except Exception as e:
            print(f"Error loading theme {theme}: {e}")
    _themes_loaded = True


THEME_PRESETS = {
    "azure-dark": {
        "ttk_theme": "azure-dark",
        "bg": "#333333",
        "fg": "#ffffff",
        "select_bg": "#007fff",
        "select_fg": "#ffffff",
        "field_bg": "#292929",
    },
    "azure-light": {
        "ttk_theme": "azure-light",
        "bg": "#ffffff",
        "fg": "#000000",
        "select_bg": "#007fff",
        "select_fg": "#ffffff",
        "field_bg": "#f5f5f5",
    },
    "sun-valley-dark": {
        "ttk_theme": "sun-valley-dark",
        "bg": "#1c1c1c",
        "fg": "#ffffff",
        "select_bg": "#60cdff",
        "select_fg": "#000000",
        "field_bg": "#2c2c2c",
    },
    "sun-valley-light": {
        "ttk_theme": "sun-valley-light",
        "bg": "#fafafa",
        "fg": "#000000",
        "select_bg": "#005fb8",
        "select_fg": "#ffffff",
        "field_bg": "#ffffff",
    },
    "park-dark": {
        "ttk_theme": "park-dark",
        "bg": "#313131",
        "fg": "#eeeeee",
        "select_bg": "#217346",
        "select_fg": "#ffffff",
        "field_bg": "#2b2b2b",
    },
    "park-light": {
        "ttk_theme": "park-light",
        "bg": "#ffffff",
        "fg": "#313131",
        "select_bg": "#107c41",
        "select_fg": "#ffffff",
        "field_bg": "#f0f0f0",
    },
}


def apply_gui_theme(root, theme_name: str, mode_name: str):
    """
    Applies the specified TKinterModernThemes theme (azure, sun-valley, park)
    and color mode (auto, dark, light) to the given Tkinter root window.
    """
    if not HAS_TKMT:
        return

    load_all_modern_themes(root)

    theme_clean = theme_name.strip().lower()
    if theme_clean not in ("azure", "sun-valley", "park"):
        theme_clean = "azure"

    mode_clean = mode_name.strip().lower()
    if "auto" in mode_clean:
        mode_clean = get_system_mode()
    elif mode_clean not in ("dark", "light"):
        mode_clean = get_system_mode()

    target_key = f"{theme_clean}-{mode_clean}"
    preset = THEME_PRESETS.get(target_key, THEME_PRESETS["azure-dark"])

    try:
        style = ttk.Style(root)
        style.theme_use(preset["ttk_theme"])

        bg_color = preset["bg"]
        fg_color = preset["fg"]
        select_bg = preset["select_bg"]
        select_fg = preset["select_fg"]

        # Configure root TTK styles
        style.configure(".", background=bg_color, foreground=fg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color)
        style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
        style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

        try:
            root.tk.call(
                "tk_setPalette",
                "background", bg_color,
                "foreground", fg_color,
                "selectBackground", select_bg,
                "selectForeground", select_fg,
            )
        except Exception:
            pass

        root.option_add("*background", bg_color)
        root.option_add("*foreground", fg_color)

        try:
            root.config(bg=bg_color)
        except Exception:
            pass

        if hasattr(root, "settings_canvas") and root.settings_canvas:
            try:
                root.settings_canvas.config(bg=bg_color)
            except Exception:
                pass
    except Exception as e:
        print(f"Failed to apply theme {target_key}: {e}")


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller --onefile."""
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return Path(base_path) / relative_path


def generate_tray_icon(icon_path: Path, color_rgba: tuple):
    """
    Loads base icon.ico, draws a colored status dot with a dark border
    in the bottom-right corner, and returns the PIL Image for pystray.
    """
    target_path = icon_path if (icon_path and icon_path.is_file()) else get_resource_path("icon.ico")
    if target_path.is_file():
        base_img = Image.open(target_path).convert("RGBA")
    else:
        base_img = Image.new("RGBA", (64, 64), color=(0, 120, 215, 255))

    img = base_img.resize((64, 64), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img)

    # Dark border circle
    draw.ellipse([38, 38, 62, 62], fill=(20, 20, 20, 255))
    # Inner colored status dot
    draw.ellipse([40, 40, 60, 60], fill=color_rgba)

    return img


def set_windows_autostart(enable: bool):
    """Adds or removes PS3RPD from Windows Registry startup key."""
    if sys.platform == "win32":
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                if getattr(sys, "frozen", False):
                    app_path = sys.executable
                else:
                    app_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, "PS3RPD", 0, winreg.REG_SZ, f'"{app_path}" --minimized')
            else:
                try:
                    winreg.DeleteValue(key, "PS3RPD")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Registry autostart error: {e}")


DISCORD_ASSETS_CACHE = {}


def fetch_discord_assets(client_id):
    """Fetches and caches the Discord application asset map (name -> asset_id)."""
    global DISCORD_ASSETS_CACHE
    client_id_str = str(client_id).strip()
    if client_id_str in DISCORD_ASSETS_CACHE:
        return DISCORD_ASSETS_CACHE[client_id_str]

    asset_map = {}
    try:
        import requests
        url = f"https://discord.com/api/v9/oauth2/applications/{client_id_str}/assets"
        res = requests.get(url, headers={"User-Agent": "PS3RPD/1.9.7"}, timeout=6)
        if res.status_code == 200:
            for asset in res.json():
                asset_map[asset["name"].lower()] = asset["id"]
    except Exception as e:
        print(f"Discord assets API error: {e}")

    DISCORD_ASSETS_CACHE[client_id_str] = asset_map
    return asset_map


class PS3RPD_GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PS3 Rich Presence for Discord")
        self.geometry("640x560")
        self.minsize(580, 500)

        # Set window icon for top bar and OS taskbar
        self.icon_path = get_resource_path("icon.ico")
        if self.icon_path.is_file():
            try:
                if sys.platform == "win32":
                    abs_icon_str = str(self.icon_path.resolve())
                    try:
                        self.iconbitmap(default=abs_icon_str)
                        self.iconbitmap(abs_icon_str)
                    except Exception:
                        pass

                pil_icon = Image.open(self.icon_path)
                self.tk_app_icon = ImageTk.PhotoImage(pil_icon)
                self.iconphoto(False, self.tk_app_icon)
            except Exception as e:
                print(f"Window icon error: {e}")

        # Load configuration
        self.prepWork = PrepWork()
        self.load_config_silent()

        import PS3RPD
        PS3RPD.prepWork = self.prepWork

        self.gatherDetails = GatherDetails()
        self.rpc_running = False
        self.rpc_paused = False
        self.rpc_wake_event = threading.Event()
        self.worker_thread = None
        self.tray_icon = None

        # Live telemetry state
        self.status_state = "Offline"
        self.status_msg = "PS3 offline, please boot PS3 with webMAN MOD installed!"
        self.game_name = "None"
        self.title_id = "N/A"
        self.thermals = "N/A"
        self.image_val = ""
        self.image_source = "N/A"
        self.last_loaded_image = ""
        self.cover_photo = None
        self.elapsed_str = "00:00:00"
        self.start_timestamp = None

        # Build UI tabs
        self.create_widgets()

        # Apply Azure / Modern theme across all created widgets immediately on startup
        apply_gui_theme(
            self,
            self.prepWork.config.get("gui_theme", "azure"),
            self.prepWork.config.get("gui_mode", "auto"),
        )
        self.update_idletasks()

        # Handle window close (X button minimizes to tray if enabled, else exits)
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Start RPC worker thread
        self.start_rpc_worker()

        # System tray setup
        if HAS_TRAY:
            self.setup_tray_icon()

        # Check if started minimized
        if "--minimized" in sys.argv or self.prepWork.config.get("start_minimized", False):
            if self.prepWork.config.get("use_tray", False) and HAS_TRAY:
                self.withdraw()
            else:
                self.iconify()

        # Schedule live UI refresh loop
        self.after(1000, self.update_ui_loop)

    def load_config_silent(self):
        """Loads configuration from ps3rpdconfig.txt without CLI prompts."""
        if self.prepWork.config_path.is_file():
            try:
                with self.prepWork.config_path.open(mode="r") as f:
                    self.prepWork.config = json.load(f)
            except Exception:
                self.prepWork.config = default_config.copy()
        else:
            self.prepWork.config = default_config.copy()

        # Ensure default fields exist
        for key, val in default_config.items():
            if key not in self.prepWork.config:
                self.prepWork.config[key] = val
        if "use_tray" not in self.prepWork.config:
            self.prepWork.config["use_tray"] = True
        if "start_minimized" not in self.prepWork.config:
            self.prepWork.config["start_minimized"] = False
        if "autostart" not in self.prepWork.config:
            self.prepWork.config["autostart"] = False

        import PS3RPD
        PS3RPD.prepWork = self.prepWork

    def create_widgets(self):
        # Notebook tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_dashboard = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_dashboard, text="  Dashboard  ")
        self.notebook.add(self.tab_settings, text="  Settings  ")

        self.build_dashboard_tab()
        self.build_settings_tab()

    def build_dashboard_tab(self):
        # Main Header Card
        header_frame = ttk.LabelFrame(self.tab_dashboard, text=" System & Connection Status ", padding=12)
        header_frame.pack(fill="x", padx=10, pady=8)

        self.lbl_status_banner = tk.Label(
            header_frame,
            text=self.status_msg,
            font=("Segoe UI", 11, "bold"),
            bg="#d9534f",
            fg="white",
            padx=10,
            pady=8,
            wraplength=520,
            justify="center",
        )
        self.lbl_status_banner.pack(fill="x", pady=4)

        # Game Information Card
        info_frame = ttk.LabelFrame(self.tab_dashboard, text=" Currently Active ", padding=12)
        info_frame.pack(fill="both", expand=True, padx=10, pady=8)

        # Left Column: Telemetry Details
        grid = ttk.Frame(info_frame)
        grid.pack(side="left", fill="both", expand=True, pady=4)

        ttk.Label(grid, text="Game / App:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.lbl_game_name = ttk.Label(grid, text="N/A", font=("Segoe UI", 10))
        self.lbl_game_name.grid(row=0, column=1, sticky="w", padx=12, pady=4)

        ttk.Label(grid, text="Title ID:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.lbl_title_id = ttk.Label(grid, text="N/A", font=("Segoe UI", 10))
        self.lbl_title_id.grid(row=1, column=1, sticky="w", padx=12, pady=4)

        ttk.Label(grid, text="Thermals:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=4)
        self.lbl_thermals = ttk.Label(grid, text="N/A", font=("Segoe UI", 10))
        self.lbl_thermals.grid(row=2, column=1, sticky="w", padx=12, pady=4)

        ttk.Label(grid, text="Time Elapsed:", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=4)
        self.lbl_elapsed = ttk.Label(grid, text="00:00:00", font=("Segoe UI", 10))
        self.lbl_elapsed.grid(row=3, column=1, sticky="w", padx=12, pady=4)

        # Right Column: Cover Image & Source
        right_frame = ttk.Frame(info_frame)
        right_frame.pack(side="right", padx=15, pady=4, anchor="center")

        self.lbl_cover_img = ttk.Label(right_frame)
        self.lbl_cover_img.pack(pady=4)

        self.lbl_cover_source = ttk.Label(right_frame, text="Source: N/A", font=("Segoe UI", 8, "italic"))
        self.lbl_cover_source.pack(pady=2)

        # Initial cover image load
        self.load_cover_image("xmb")

        # Control Buttons Card
        btn_frame = ttk.Frame(self.tab_dashboard)
        btn_frame.pack(fill="x", padx=10, pady=8)

        self.btn_toggle_rpc = ttk.Button(btn_frame, text="Pause Presence", command=self.toggle_rpc_pause, style="Accent.TButton")
        self.btn_toggle_rpc.pack(side="left", padx=8, pady=4)

        self.btn_reconnect = ttk.Button(btn_frame, text="Reconnect Discord", command=self.reconnect_rpc)
        self.btn_reconnect.pack(side="left", padx=8, pady=4)



    def build_settings_tab(self):
        # Canvas & Scrollbar for smooth settings view
        current_bg = ttk.Style(self).lookup(".", "background") or self.cget("bg")
        self.settings_canvas = tk.Canvas(self.tab_settings, borderwidth=0, highlightthickness=0, bg=current_bg)
        scrollbar = ttk.Scrollbar(self.tab_settings, orient="vertical", command=self.settings_canvas.yview)
        scroll_content = ttk.Frame(self.settings_canvas)

        scroll_content.bind(
            "<Configure>", lambda e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all"))
        )
        self.settings_canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        self.settings_canvas.configure(yscrollcommand=scrollbar.set)

        self.settings_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        # GUI Theme & Appearance
        theme_frame = ttk.LabelFrame(scroll_content, text=" GUI Theme & Appearance ", padding=10)
        theme_frame.pack(fill="x", padx=10, pady=6)

        ttk.Label(theme_frame, text="Theme:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_gui_theme = tk.StringVar(value=str(self.prepWork.config.get("gui_theme", "azure")).lower())
        self.cbo_gui_theme = ttk.Combobox(
            theme_frame,
            textvariable=self.var_gui_theme,
            values=["azure", "sun-valley", "park"],
            state="readonly",
            width=16,
        )
        self.cbo_gui_theme.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(theme_frame, text="Color Mode:").grid(row=0, column=2, sticky="w", padx=(16, 0), pady=4)
        init_mode = str(self.prepWork.config.get("gui_mode", "auto")).lower()
        mode_map = {"auto": "Auto-Detect (System)", "dark": "Dark", "light": "Light"}
        self.var_gui_mode = tk.StringVar(value=mode_map.get(init_mode, "Auto-Detect (System)"))
        self.cbo_gui_mode = ttk.Combobox(
            theme_frame,
            textvariable=self.var_gui_mode,
            values=["Auto-Detect (System)", "Dark", "Light"],
            state="readonly",
            width=20,
        )
        self.cbo_gui_mode.grid(row=0, column=3, sticky="w", padx=8, pady=4)

        def _on_theme_change(event=None):
            mode_reverse_map = {"Auto-Detect (System)": "auto", "Dark": "dark", "Light": "light"}
            m = mode_reverse_map.get(self.var_gui_mode.get(), "auto")
            apply_gui_theme(self, self.var_gui_theme.get(), m)

        self.cbo_gui_theme.bind("<<ComboboxSelected>>", _on_theme_change)
        self.cbo_gui_mode.bind("<<ComboboxSelected>>", _on_theme_change)

        # Network Settings
        net_frame = ttk.LabelFrame(scroll_content, text=" Network Setup ", padding=10)
        net_frame.pack(fill="x", padx=10, pady=6)

        ttk.Label(net_frame, text="PS3 IP Address:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_ip = tk.StringVar(value=str(self.prepWork.config.get("ip", "")))
        self.ent_ip = ttk.Entry(net_frame, textvariable=self.var_ip, width=22)
        self.ent_ip.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self.btn_scan_ip = ttk.Button(net_frame, text="Auto-Detect IP", command=self.auto_scan_ip)
        self.btn_scan_ip.grid(row=0, column=2, sticky="w", padx=6, pady=4)

        # Discord Application Settings
        discord_frame = ttk.LabelFrame(scroll_content, text=" Discord Integration ", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=6)

        ttk.Label(discord_frame, text="Client ID:").grid(row=0, column=0, sticky="w", pady=4)
        self.var_client_id = tk.StringVar(value=str(self.prepWork.config.get("client_id", 780389261870235650)))
        self.ent_client_id = ttk.Entry(discord_frame, textvariable=self.var_client_id, width=28)
        self.ent_client_id.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(discord_frame, text="Refresh Interval (s):").grid(row=1, column=0, sticky="w", pady=4)
        self.var_wait_seconds = tk.StringVar(value=str(self.prepWork.config.get("wait_seconds", 35)))
        self.ent_wait_seconds = ttk.Entry(discord_frame, textvariable=self.var_wait_seconds, width=10)
        self.ent_wait_seconds.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        # Cover Image Provider Settings
        cover_frame = ttk.LabelFrame(scroll_content, text=" Cover Image Provider ", padding=10)
        cover_frame.pack(fill="x", padx=10, pady=6)

        self.var_use_sgdb = tk.BooleanVar(value=bool(self.prepWork.config.get("steamgriddb_api_key", "")))
        self.chk_use_sgdb = ttk.Checkbutton(
            cover_frame, text="Enable SteamGridDB (searches covers by Game Title)", variable=self.var_use_sgdb, command=self.toggle_sgdb_field
        )
        self.chk_use_sgdb.pack(anchor="w", pady=2)

        sgdb_sub = ttk.Frame(cover_frame)
        sgdb_sub.pack(fill="x", padx=18, pady=4)

        ttk.Label(sgdb_sub, text="SteamGridDB API Key:").grid(row=0, column=0, sticky="w", pady=2)
        self.var_sgdb_key = tk.StringVar(value=str(self.prepWork.config.get("steamgriddb_api_key", "")))
        self.ent_sgdb_key = ttk.Entry(sgdb_sub, textvariable=self.var_sgdb_key, width=36)
        self.ent_sgdb_key.grid(row=0, column=1, sticky="w", padx=8, pady=2)

        ttk.Label(cover_frame, text="* Fallback: If SteamGridDB is disabled or no grid is found, GameTDB is used automatically.", font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=2)

        # Display Toggles
        disp_frame = ttk.LabelFrame(scroll_content, text=" Display & Features ", padding=10)
        disp_frame.pack(fill="x", padx=10, pady=6)

        self.var_show_temp = tk.BooleanVar(value=bool(self.prepWork.config.get("show_temp", True)))
        ttk.Checkbutton(disp_frame, text="Show CPU & RSX Temperatures", variable=self.var_show_temp).pack(anchor="w", pady=2)

        self.var_retro_covers = tk.BooleanVar(value=bool(self.prepWork.config.get("retro_covers", False)))
        ttk.Checkbutton(disp_frame, text="Fetch Covers for PS1 & PS2 Games", variable=self.var_retro_covers).pack(anchor="w", pady=2)

        self.var_show_elapsed = tk.BooleanVar(value=bool(self.prepWork.config.get("show_elapsed", True)))
        ttk.Checkbutton(disp_frame, text="Show Time Elapsed", variable=self.var_show_elapsed).pack(anchor="w", pady=2)

        self.var_show_timer = tk.BooleanVar(value=bool(self.prepWork.config.get("show_timer", True)))
        ttk.Checkbutton(disp_frame, text="Show Timer", variable=self.var_show_timer).pack(anchor="w", pady=2)

        self.var_use_appname = tk.BooleanVar(value=bool(self.prepWork.config.get("use_appname", False)))
        ttk.Checkbutton(disp_frame, text="Use App / Game Name as Presence Title", variable=self.var_use_appname).pack(anchor="w", pady=2)

        self.var_prefer_dev_app = tk.BooleanVar(value=bool(self.prepWork.config.get("prefer_dev_app", False)))
        ttk.Checkbutton(disp_frame, text="Prefer Discord Developer App Assets Only", variable=self.var_prefer_dev_app).pack(anchor="w", pady=2)

        # System & Startup Options
        sys_frame = ttk.LabelFrame(scroll_content, text=" System & Tray Options ", padding=10)
        sys_frame.pack(fill="x", padx=10, pady=6)

        self.var_autostart = tk.BooleanVar(value=bool(self.prepWork.config.get("autostart", False)))
        ttk.Checkbutton(sys_frame, text="Start on Windows Startup", variable=self.var_autostart).pack(anchor="w", pady=2)

        self.var_start_minimized = tk.BooleanVar(value=bool(self.prepWork.config.get("start_minimized", False)))
        ttk.Checkbutton(sys_frame, text="Start Minimized", variable=self.var_start_minimized).pack(anchor="w", pady=2)

        self.var_use_tray = tk.BooleanVar(value=bool(self.prepWork.config.get("use_tray", True)))
        ttk.Checkbutton(sys_frame, text="Minimize to tray on close", variable=self.var_use_tray).pack(anchor="w", pady=2)

        # Save Button
        btn_save = ttk.Button(scroll_content, text=" Save & Apply Settings ", command=self.save_settings)
        btn_save.pack(pady=12)

        self.toggle_sgdb_field()

    def toggle_sgdb_field(self):
        if self.var_use_sgdb.get():
            self.ent_sgdb_key.config(state="normal")
        else:
            self.ent_sgdb_key.config(state="disabled")

    def auto_scan_ip(self):
        self.btn_scan_ip.config(state="disabled", text="Scanning...")

        def scan_thread():
            found_ip = None
            try:
                from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
                import re, concurrent.futures, requests

                tempSock = socket(AF_INET, SOCK_DGRAM)
                tempSock.connect(("8.8.8.8", 80))
                local_ip = tempSock.getsockname()[0]
                tempSock.close()

                subnet_prefix = re.search(r"^(.*)\.", local_ip).group(0)
                ips_to_scan = [f"{subnet_prefix}{i}" for i in range(1, 255)]

                def _check_target(ip_addr):
                    try:
                        s = socket(AF_INET, SOCK_STREAM)
                        s.settimeout(0.3)
                        res = s.connect_ex((ip_addr, 80))
                        s.close()
                        if res == 0:
                            r = requests.get(f"http://{ip_addr}/cpursx.ps3", headers={"User-Agent": "PS3RPD/1.9.7"}, timeout=0.8)
                            if r.status_code == 200 and ("RSX:" in r.text or "CPU:" in r.text or "PS3" in r.text):
                                return ip_addr
                    except Exception:
                        pass
                    return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    futures = [executor.submit(_check_target, ip) for ip in ips_to_scan]
                    for future in concurrent.futures.as_completed(futures):
                        found = future.result()
                        if found:
                            found_ip = found
                            break
            except Exception as e:
                print(f"Scan error: {e}")

            def on_done():
                self.btn_scan_ip.config(state="normal", text="Auto-Detect IP")
                if found_ip:
                    self.var_ip.set(found_ip)
                    messagebox.showinfo("Success", f"Found PS3 webMAN at IP: {found_ip}")
                else:
                    messagebox.showwarning("Not Found", "PS3 with webMAN MOD was not found on the local network.")

            self.after(0, on_done)

        threading.Thread(target=scan_thread, daemon=True).start()

    def save_settings(self):
        # Read GUI variables
        ip_val = self.var_ip.get().strip()
        client_id_val = self.var_client_id.get().strip()
        try:
            client_id_val = int(client_id_val)
        except ValueError:
            client_id_val = 780389261870235650

        try:
            wait_seconds_val = max(15, int(self.var_wait_seconds.get().strip()))
        except ValueError:
            wait_seconds_val = 35

        sgdb_key_val = self.var_sgdb_key.get().strip() if self.var_use_sgdb.get() else ""

        mode_reverse_map = {"Auto-Detect (System)": "auto", "Dark": "dark", "Light": "light"}
        gui_theme_val = self.var_gui_theme.get().lower()
        gui_mode_val = mode_reverse_map.get(self.var_gui_mode.get(), "auto")

        self.prepWork.config["ip"] = ip_val
        self.prepWork.config["client_id"] = client_id_val
        self.prepWork.config["wait_seconds"] = wait_seconds_val
        self.prepWork.config["steamgriddb_api_key"] = sgdb_key_val
        self.prepWork.config["show_temp"] = self.var_show_temp.get()
        self.prepWork.config["retro_covers"] = self.var_retro_covers.get()
        self.prepWork.config["show_elapsed"] = self.var_show_elapsed.get()
        self.prepWork.config["show_timer"] = self.var_show_timer.get()
        self.prepWork.config["use_appname"] = self.var_use_appname.get()
        self.prepWork.config["prefer_dev_app"] = self.var_prefer_dev_app.get()
        self.prepWork.config["autostart"] = self.var_autostart.get()
        self.prepWork.config["start_minimized"] = self.var_start_minimized.get()
        self.prepWork.config["use_tray"] = self.var_use_tray.get()
        self.prepWork.config["gui_theme"] = gui_theme_val
        self.prepWork.config["gui_mode"] = gui_mode_val

        apply_gui_theme(self, gui_theme_val, gui_mode_val)

        # Write to ps3rpdconfig.txt
        with self.prepWork.config_path.open(mode="w+") as f:
            json.dump(self.prepWork.config, f, indent=4)

        import PS3RPD
        PS3RPD.prepWork = self.prepWork

        # Reset cached title so game/image details re-evaluate with new settings
        self.gatherDetails.prevTitle = ""

        # Close existing RPC pipe to force re-connection with new client_id / config
        if self.prepWork.RPC:
            try:
                self.prepWork.RPC.clear()
                self.prepWork.RPC.close()
            except Exception:
                pass
            self.prepWork.RPC = None

        if not self.rpc_paused:
            self.prepWork.connect_to_discord()

        self.rpc_wake_event.set()

        # Update Windows autostart registry
        set_windows_autostart(self.prepWork.config["autostart"])

        # Update System Tray Icon status
        if HAS_TRAY:
            if self.prepWork.config["use_tray"] and not self.tray_icon:
                self.setup_tray_icon()
            elif not self.prepWork.config["use_tray"] and self.tray_icon:
                self.stop_tray_icon()

        messagebox.showinfo("Saved", "Settings saved successfully!")

    def start_rpc_worker(self):
        self.rpc_running = True
        self.worker_thread = threading.Thread(target=self.rpc_worker_loop, daemon=True)
        self.worker_thread.start()

    def rpc_worker_loop(self):
        closed_rpc = False

        while self.rpc_running:
            if self.rpc_paused:
                self.rpc_wake_event.wait(timeout=1.0)
                self.rpc_wake_event.clear()
                continue

            ip = self.prepWork.config.get("ip", "")
            if not ip:
                self.status_state = "Offline"
                self.status_msg = "Please set your PS3 IP Address in Settings."
                self.rpc_wake_event.wait(timeout=3.0)
                self.rpc_wake_event.clear()
                continue

            # Contact webMAN
            if not self.gatherDetails.get_html(ip):
                if self.gatherDetails.isRetroGame:
                    self.status_state = "Online"
                    self.status_msg = "PS2 Game Mounted. Keeping RPC active."
                    self.rpc_wake_event.wait(timeout=self.prepWork.config.get("wait_seconds", 35))
                    self.rpc_wake_event.clear()
                else:
                    self.status_state = "Offline"
                    self.status_msg = "PS3 offline, please boot PS3 with webMAN MOD installed!"
                    if not closed_rpc and self.prepWork.RPC:
                        try:
                            self.prepWork.RPC.clear()
                            self.prepWork.RPC.close()
                        except Exception:
                            pass
                        self.prepWork.RPC = None
                    closed_rpc = True
                    self.rpc_wake_event.wait(timeout=float(self.prepWork.config.get("hibernate_seconds", 600)))
                    self.rpc_wake_event.clear()
            else:
                self.status_state = "Online"
                self.status_msg = "PS3 Connected & Active"

                if closed_rpc or not self.prepWork.RPC:
                    connected = self.prepWork.connect_to_discord()
                    if connected:
                        self.start_timestamp = time.time()
                        closed_rpc = False

                if self.prepWork.config.get("show_temp", True):
                    self.gatherDetails.get_thermals()
                    if self.gatherDetails.thermalData:
                        self.gatherDetails.thermalData = self.gatherDetails.thermalData.replace("Â", "")

                self.gatherDetails.decide_game_type()
                if self.gatherDetails.name:
                    self.gatherDetails.name = self.gatherDetails.name.replace("Â", "")

                # Update live telemetry for UI
                self.game_name = self.gatherDetails.name or "XMB"
                self.title_id = self.gatherDetails.titleID or "N/A"
                self.thermals = self.gatherDetails.thermalData or "N/A"
                self.image_val = self.gatherDetails.image or "xmb"
                self.image_source = getattr(self.gatherDetails, "image_source", "Discord Developer Application")

                if not self.start_timestamp:
                    self.start_timestamp = time.time()

                # Send Discord Rich Presence update if RPC connected
                if self.prepWork.RPC:
                    timer_val = int(self.start_timestamp) if self.prepWork.config.get("show_timer", True) else None
                    details_str = self.gatherDetails.name or "XMB"
                    state_str = self.gatherDetails.thermalData or "PS3 Active"
                    large_img_str = self.gatherDetails.image or "xmb"
                    large_txt_str = self.gatherDetails.titleID or "PS3"

                    try:
                        if self.prepWork.config.get("use_appname", False):
                            self.prepWork.RPC.update(
                                details=details_str,
                                state=state_str,
                                large_image=large_img_str,
                                large_text=large_txt_str,
                                start=timer_val,
                            )
                        else:
                            self.prepWork.RPC.update(
                                name=details_str,
                                details=details_str,
                                state=state_str,
                                large_image=large_img_str,
                                large_text=large_txt_str,
                                start=timer_val,
                            )
                    except Exception as rpc_err:
                        print(f"RPC Update Exception: {rpc_err}")
                        try:
                            self.prepWork.RPC.close()
                        except Exception:
                            pass
                        self.prepWork.RPC = None
                        closed_rpc = True

                self.rpc_wake_event.wait(timeout=self.prepWork.config.get("wait_seconds", 35))
                self.rpc_wake_event.clear()

    def toggle_rpc_pause(self):
        self.rpc_paused = not self.rpc_paused
        if self.rpc_paused:
            self.btn_toggle_rpc.config(text="Resume Presence")
            if self.prepWork.RPC:
                try:
                    self.prepWork.RPC.clear()
                    self.prepWork.RPC.close()
                except Exception:
                    pass
                self.prepWork.RPC = None
        else:
            self.btn_toggle_rpc.config(text="Pause Presence")
            self.gatherDetails.prevTitle = ""
            if not self.prepWork.RPC:
                self.prepWork.connect_to_discord()
                self.start_timestamp = time.time()
        self.rpc_wake_event.set()

    def reconnect_rpc(self):
        self.btn_reconnect.config(state="disabled", text="Reconnecting...")
        self.is_reconnecting = True

        def reconnect_thread():
            if self.prepWork.RPC:
                try:
                    self.prepWork.RPC.clear()
                    self.prepWork.RPC.close()
                except Exception:
                    pass
                self.prepWork.RPC = None

            self.gatherDetails.prevTitle = ""
            self.prepWork.connect_to_discord()
            self.start_timestamp = time.time()

            def _on_done():
                self.is_reconnecting = False
                self.btn_reconnect.config(state="normal", text="Reconnect Discord")
                self.rpc_wake_event.set()

            self.after(0, _on_done)

        threading.Thread(target=reconnect_thread, daemon=True).start()

    def load_cover_image(self, img_ref):
        def _loader():
            pil_img = None
            try:
                if img_ref and (img_ref.startswith("http://") or img_ref.startswith("https://")):
                    import requests

                    res = requests.get(img_ref, headers=headers, timeout=8)
                    if res.status_code == 200:
                        from io import BytesIO

                        pil_img = Image.open(BytesIO(res.content)).convert("RGBA")

                # Case 2: Discord Developer Application asset key (e.g. "xmb", "npub30040", etc.)
                if not pil_img and img_ref:
                    import requests

                    client_id = self.prepWork.config.get("client_id", 780389261870235650)
                    asset_map = fetch_discord_assets(client_id)
                    key_clean = str(img_ref).strip().lower()

                    asset_id = asset_map.get(key_clean)
                    if not asset_id and "xmb" in asset_map:
                        asset_id = asset_map.get("xmb")

                    if asset_id:
                        asset_url = f"https://cdn.discordapp.com/app-assets/{client_id}/{asset_id}.png"
                        res = requests.get(asset_url, headers=headers, timeout=8)
                        if res.status_code == 200:
                            from io import BytesIO

                            pil_img = Image.open(BytesIO(res.content)).convert("RGBA")

                # Case 3: Local icon.ico fallback
                if not pil_img:
                    icon_file = get_resource_path("icon.ico")
                    if icon_file and icon_file.is_file():
                        pil_img = Image.open(icon_file).convert("RGBA")
            except Exception as e:
                print(f"Image preview loader error: {e}")

            if pil_img:
                try:
                    pil_img = pil_img.resize((128, 128), Image.Resampling.LANCZOS)
                except Exception:
                    pass

                def _apply_on_main(img_to_render):
                    try:
                        self.cover_photo = ImageTk.PhotoImage(img_to_render)
                        self.lbl_cover_img.config(image=self.cover_photo)
                    except Exception as err:
                        print(f"Error setting cover photo label: {err}")

                self.after(0, lambda: _apply_on_main(pil_img))

        threading.Thread(target=_loader, daemon=True).start()

    def update_ui_loop(self):
        # Update status banner
        if self.status_state == "Online":
            self.lbl_status_banner.config(text=self.status_msg, bg="#4cae4c")
        else:
            self.lbl_status_banner.config(text=self.status_msg, bg="#d9534f")

        # Update telemetry labels
        self.lbl_game_name.config(text=self.game_name)
        self.lbl_title_id.config(text=self.title_id)
        self.lbl_thermals.config(text=self.thermals)
        self.lbl_cover_source.config(text=f"Source: {self.image_source}")

        if self.image_val and self.image_val != self.last_loaded_image:
            self.last_loaded_image = self.image_val
            self.load_cover_image(self.image_val)

        if self.start_timestamp and self.status_state == "Online":
            elapsed = int(time.time() - self.start_timestamp)
            hrs, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            self.elapsed_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        else:
            self.elapsed_str = "00:00:00"
        self.lbl_elapsed.config(text=self.elapsed_str)

        # Update dynamic system tray status dot (Green=Connected, Red=Disconnected, Blue=Paused/Reconnecting)
        if self.rpc_paused or getattr(self, "is_reconnecting", False):
            dot_color = (33, 150, 243, 255)  # Blue dot
        elif self.status_state == "Online" and self.prepWork.RPC:
            dot_color = (76, 175, 80, 255)   # Green dot
        else:
            dot_color = (244, 67, 54, 255)   # Red dot

        if self.tray_icon and HAS_TRAY:
            if getattr(self, "last_tray_color", None) != dot_color:
                self.last_tray_color = dot_color
                try:
                    self.tray_icon.icon = generate_tray_icon(self.icon_path, dot_color)
                except Exception as e:
                    print(f"Tray icon status dot error: {e}")

        self.after(1000, self.update_ui_loop)

    def setup_tray_icon(self):
        if not HAS_TRAY or self.tray_icon:
            return

        def on_open_click(icon, item):
            self.after(0, self.restore_from_tray)

        def on_pause_click(icon, item):
            self.after(0, self.toggle_rpc_pause)

        def on_exit_click(icon, item):
            self.after(0, self.exit_app_completely)

        menu = pystray.Menu(
            pystray.MenuItem("Open PS3RPD", on_open_click, default=True),
            pystray.MenuItem("Pause / Resume Presence", on_pause_click),
            pystray.MenuItem("Exit", on_exit_click),
        )

        try:
            init_color = (244, 67, 54, 255)
            pil_img = generate_tray_icon(self.icon_path, init_color)
            self.last_tray_color = init_color
            self.tray_icon = pystray.Icon("PS3RPD", pil_img, "PS3 Rich Presence", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"Failed to initialize tray icon: {e}")

    def stop_tray_icon(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None

    def on_window_close(self):
        if HAS_TRAY and self.prepWork.config.get("use_tray", True):
            self.withdraw()
        else:
            self.exit_app_completely()

    def restore_from_tray(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

    def exit_app_completely(self):
        self.rpc_running = False
        if self.prepWork.RPC:
            try:
                self.prepWork.RPC.clear()
                self.prepWork.RPC.close()
            except Exception:
                pass
        self.stop_tray_icon()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = PS3RPD_GUI()
    app.mainloop()
