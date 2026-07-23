# PS3-Rich-Presence-for-Discord
Discord Rich Presence script for PS3 consoles on HFW&HEN or CFW.

Display what game you are playing on PS3 via your PC!

## Display Example
<table>
	<tr>
		<th></th>
		<th>AppName (original style)</th>
		<th>GameName (new style)</th>
	</tr>
	<tr>
		<td>XMB</td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/xmb.png?raw=true"> </td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/xmb2025.png?raw=true"></td>
	</tr>
	<tr>
		<td>PS3</td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/ps3.png?raw=true"> </td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/ps32025.png?raw=true"></td>
	</tr>
	<tr>
		<td>SGDB</td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/sgdb.png?raw=true"> </td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/sgdb2025.png?raw=true"></td>
	</tr>
	<tr>
		<td>PS1/2</td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/retro.png?raw=true"> </td>
		<td> <img src="https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/blob/main/img/retro2025.png?raw=true"></td>
	</tr>
</table>


## Usage

### Requirements
* PS3 with either HFW&HEN, or CFW installed
* PS3 with [webmanMOD](https://github.com/aldostools/webMAN-MOD/releases) installed 
* PS3 and PC on the same network/internet connection
* Discord installed and open on the PC running the script
* Administrator permissions on the PC
* A Python 3.9 interpreter installed on the PC if you do not wish to use the executable file

### Windows

#### GUI Version (Graphical Interface)
* **Standalone Executable** *(Recommended, no Python required)*:  
  [Download PS3RPD_GUI.exe v2.1.0](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD_GUI.exe)
* **Python Source Files** *(Requires Python 3)*:  
  [Download PS3RPD-GUI-v2.1.0-Python.zip](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD-GUI-v2.1.0-Python.zip)  
  Extract the ZIP archive and run `python start.py` or `python PS3RPD_GUI.py`.

#### CLI Version (Terminal / Command Line)
* **Standalone Executable** *(No Python required)*:  
  [Download PS3RPD.exe v2.1.0](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD.exe)
* **Standalone Python File**:  
  [Download PS3RPD.py v2.1.0](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD.py)  
  Run directly with `python PS3RPD.py`.

#### Installing as a Windows service (optional)
Download [NSSM](https://nssm.cc/release/nssm-2.24.zip) and run `nssm install <service name ie. ps3rpd>` to install PS3RPD as a Windows service.  
WARNING: PS3RPD.exe must be in a location that won't change ie. `C:\ps3rpd\PS3RPD.exe`

> [!NOTE]
> Executable files may be flagged by antivirus software due to `pyinstaller` bundling. You can inspect the source code or run directly via Python.

### Linux 

#### GUI Version (Graphical Interface)
* **Python Source Files**:  
  [Download PS3RPD-GUI-v2.1.0-Python.zip](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD-GUI-v2.1.0-Python.zip)  
  Extract the archive and run `./start.py` or `python3 PS3RPD_GUI.py`.
* Or clone directly via Git:
  ```bash
  git clone https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord ~/ps3-rich-presence
  cd ~/ps3-rich-presence && ./start.py
  ```

#### CLI Version (Terminal / Command Line)
* **Standalone Python File**:  
  [Download PS3RPD.py v2.1.0](https://github.com/TheAndromedaCat/PS3-Rich-Presence-for-Discord/releases/download/2.1.0/PS3RPD.py)  
  Run directly with `python3 PS3RPD.py`.

#### Installing as a systemd service (optional)
<details>
  <summary>If you would like the script to start on device boot, after the first run, run the following commands in your terminal:</summary>
<br>
	
```bash
# Creates the user service folder if it doesn't exist yet, and the user systemd env folder
mkdir -p ~/.config/systemd/user ~/.config/environment.d/
# Include local binaries in your systemd user environment
# (we need this so systemd can find the 'uv' executable)
bash -c 'echo "
# Adds ~/.local/bin to PATH so systemd services can find user-installed binaries
PATH=${HOME}/.local/bin:
" >> ~/.config/environment.d/90-path.conf'

# Creates a systemd .service file in the user service folder that runs the script
bash -c 'echo "
[Unit]
Description=Enables Discord Rich Presence for PS3
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 $HOME/ps3-rich-presence/start.py
Restart=on-failure
StandardOutput=journal
StandardError=journal
WorkingDirectory=$HOME/ps3-rich-presence

[Install]
WantedBy=default.target
" > ~/.config/systemd/user/ps3rpd.service'
# Reloads the systemd service to recognize the new service
systemctl --user daemon-reload
# Enables the service and starts it
systemctl --user enable --now ps3rpd
# Make it clear that something happened
echo "Finished adding user service for ps3rpd."
echo "You can check the status of the service with `systemctl --user status ps3rpd`"
```

In order to check the health of the service, you can run `systemctl --user status ps3rpd`<br>
For more depth logs you can use `journalctl --user -xeu ps3rpd`
</details>

## Limitations
* __A PC must be used to display presence, there is no way to install and use this script solely on the PS3__
* The script relies on webmanMOD, and a major change to it will break this script, please message me about updated versions of webman so that i can test the script with them
* PSX and PS2 game name depends on the name of the file
* PSX and PS2 game detection will **not** work on PSN .pkg versions because webman cannot show those games as mounted/playing.
* PS2 ISO game detection can be inconsistent, varying on degree of consistency by the value of "Refresh time."
* Using Windows 7 is only possible with up to PS3RPD version 1.7.2
	- If you want to use a .exe, [here](https://www.mediafire.com/file/ezzlcemhkmnmyn2/PS3RPD.exe/file) is a version that may or may not fully function (very little bug testing has been done)

## Contact Me
Contact me via Discord: `TheAndromedaCat`.

## Credits
Original script created by [@zorua98741](https://github.com/zorua98741).

## Additional Information

### Cover Images (SteamGridDB & GameTDB)
This script automatically fetches high-quality game cover images using a multi-tiered fallback system:
1. **SteamGridDB**: If a SteamGridDB API key is provided, the script searches by game name for static 1:1 square cover grids (`1024x1024` or `512x512`), falling back to other static dimensions if needed.
2. **GameTDB**: If no SteamGridDB API key is provided (or if SteamGridDB has no grid for the game), the script automatically falls back to [GameTDB](https://www.gametdb.com/) using the PS3 title ID.
3. **Discord Developer Application**: Final fallback to default asset names matching the lowercase title ID (`abcd12345`).

Consider supporting [SteamGridDB](https://www.steamgriddb.com/) and [GameTDB](https://www.gametdb.com/) if you use these services!

### External config file
PS3RPD makes use of an external config file (`ps3rpdconfig.txt`) to persistently store settings:
* `ip`: Your PS3's IP address (where the script will find your PS3 on the network)
* `client_id`: Discord developer application ID
* `wait_seconds`: Refresh interval (default: 35 seconds, minimum: 15 seconds)
* `show_temp`: Whether to display PS3 temperatures
* `retro_covers`: Whether to fetch covers for PS2 & PS1 games
* `show_elapsed`: Whether to display time elapsed
* `steamgriddb_api_key`: Your SteamGridDB API key (optional; leave blank to use GameTDB fallback)
* `autostart`: Automatically start PS3RPD on Windows startup
* `start_minimized`: Launch application minimized
* `use_tray`: Minimize to System Tray (Notification Area) instead of taskbar

### Using your own images
If you'd like to control what images are used for each game, you must create a Discord Developer Application over at the [Discord Developer Portal](https://discord.com/developers/applications).

Once created, copy the application ID from the Developer Portal and paste it into the external `ps3rpdconfig.json`, replacing the value of `client_id`.

You are now able to upload your own assets in the Developer Portal under `Rich Presence > Art Assets`. Note that the name of the asset uploaded must be the lowercase title ID provided in the script's output. (e.g. `abcd12345`)

Support the original creator (@zorua98741) at the ko-fi link below!
## [![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/N4N87V7K5) [![pypresence](https://img.shields.io/badge/using-pypresence-00bb88.svg?style=for-the-badge&logo=discord&logoWidth=20)](https://github.com/qwertyquerty/pypresence)
