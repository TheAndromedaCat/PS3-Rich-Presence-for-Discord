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

# Import core PS3RPD backend logic
from PS3RPD import PrepWork, GatherDetails, default_config, headers


def generate_tray_icon(icon_path: Path, color_rgba: tuple):
    """
    Loads base icon.ico, draws a colored status dot with a dark border
    in the bottom-right corner, and returns the PIL Image for pystray.
    """
    if icon_path.is_file():
        base_img = Image.open(icon_path).convert("RGBA")
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


class PS3RPD_GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PS3 Rich Presence for Discord")
        self.geometry("640x540")
        self.minsize(580, 480)

        # Set window icon for top bar and Windows taskbar
        self.icon_path = Path("icon.ico")
        if self.icon_path.is_file():
            try:
                self.iconbitmap(str(self.icon_path))
                pil_icon = Image.open(self.icon_path)
                self.tk_app_icon = ImageTk.PhotoImage(pil_icon)
                self.iconphoto(True, self.tk_app_icon)
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

        # Handle window close (X button exits app completely)
        self.protocol("WM_DELETE_WINDOW", self.exit_app_completely)

        # Handle window minimize (_ button sends to tray if enabled)
        self.bind("<Unmap>", self.on_window_unmap)

        # Start RPC worker thread
        self.start_rpc_worker()

        # System tray setup
        if HAS_TRAY and self.prepWork.config.get("use_tray", False):
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
        # Configure styles
        style = ttk.Style(self)
        style.theme_use("clam")

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

        self.lbl_cover_source = ttk.Label(
            right_frame,
            text="Source: Discord Developer Application",
            font=("Segoe UI", 8, "italic"),
            foreground="#555555",
        )
        self.lbl_cover_source.pack(pady=2)

        # Action Controls Card
        control_frame = ttk.Frame(self.tab_dashboard)
        control_frame.pack(fill="x", padx=10, pady=8)

        self.btn_toggle_rpc = ttk.Button(control_frame, text="Pause Presence", command=self.toggle_rpc_pause)
        self.btn_toggle_rpc.pack(side="left", padx=5)

        self.btn_reconnect = ttk.Button(control_frame, text="Reconnect Discord", command=self.reconnect_rpc)
        self.btn_reconnect.pack(side="left", padx=5)

    def build_settings_tab(self):
        # Canvas & Scrollbar for smooth settings view
        canvas = tk.Canvas(self.tab_settings, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_settings, orient="vertical", command=canvas.yview)
        scroll_content = ttk.Frame(canvas)

        scroll_content.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

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
        ttk.Checkbutton(sys_frame, text="Use System Tray Icon (Minimizes to Notification Area)", variable=self.var_use_tray).pack(anchor="w", pady=2)

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
                from socket import socket, AF_INET, SOCK_DGRAM
                import re, networkscan

                tempSock = socket(AF_INET, SOCK_DGRAM)
                tempSock.connect(("8.8.8.8", 80))
                hostNetwork = tempSock.getsockname()[0]
                tempSock.close()

                hostNetwork = re.search(r"^(.*)\.", hostNetwork).group(0) + "0/24"
                my_scan = networkscan.Networkscan(hostNetwork)
                my_scan.run()

                for host in my_scan.list_of_hosts_found:
                    if self.prepWork.test_for_webman(host):
                        found_ip = host
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
            try:
                if img_ref and (img_ref.startswith("http://") or img_ref.startswith("https://")):
                    res = requests.get(img_ref, headers=headers, timeout=8)
                    if res.status_code == 200:
                        from io import BytesIO
                        from PIL import Image, ImageTk

                        pil_img = Image.open(BytesIO(res.content)).convert("RGBA")
                        pil_img = pil_img.resize((128, 128), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(pil_img)

                        def _apply():
                            self.cover_photo = photo
                            self.lbl_cover_img.config(image=self.cover_photo)

                        self.after(0, _apply)
                        return

                # Local image fallback
                local_paths = [
                    Path(f"img/{img_ref}.png"),
                    Path("img/xmb.png"),
                    Path("icon.ico"),
                ]
                for p in local_paths:
                    if p.is_file():
                        from PIL import Image, ImageTk

                        pil_img = Image.open(p).convert("RGBA")
                        pil_img = pil_img.resize((128, 128), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(pil_img)

                        def _apply_local():
                            self.cover_photo = photo
                            self.lbl_cover_img.config(image=self.cover_photo)

                        self.after(0, _apply_local)
                        return
            except Exception as e:
                print(f"Image preview loader error: {e}")

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

    def on_window_unmap(self, event):
        if event.widget == self and self.state() == "iconic":
            if self.prepWork.config.get("use_tray", True) and HAS_TRAY:
                self.withdraw()

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
