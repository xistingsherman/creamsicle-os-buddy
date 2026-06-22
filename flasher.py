import os
import re
import glob
import json
import lzma
import shutil
import subprocess
import platform
import urllib3
import requests
from FATtools import Volume, partutils
from FATtools.FAT import FATDirentry

# Monkey-patch FATDirentry.IsLabel to fix the LFN bug in FATtools
def patched_IsLabel(self, mark=0):
    if mark:
        self._buf[-21] |= 0x08
    return self._buf[-21] & 0x08

FATDirentry.IsLabel = patched_IsLabel

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_SYSTEM = platform.system()  # 'Windows', 'Linux', or 'Darwin'

if _SYSTEM == 'Windows':
    import ctypes
    import msvcrt

# Popular Orange Pi Boards supported
BOARDS = {
    "orangepizero3": "Orange Pi Zero 3",
    "orangepi5": "Orange Pi 5",
    "orangepi5-plus": "Orange Pi 5 Plus",
    "orangepizero2": "Orange Pi Zero 2",
    "orangepi3-lts": "Orange Pi 3 LTS",
    "orangepi4-lts": "Orange Pi 4 LTS",
    "orangepi4pro": "Orange Pi 4 Pro",
    "orangepione": "Orange Pi One",
    "orangepizero": "Orange Pi Zero",
    "orangepipc2": "Orange Pi PC 2"
}


# ---------------------------------------------------------------------------
# Disk listing
# ---------------------------------------------------------------------------

def list_disks():
    if _SYSTEM == 'Windows':
        return _list_disks_windows()
    elif _SYSTEM == 'Linux':
        return _list_disks_linux()
    elif _SYSTEM == 'Darwin':
        return _list_disks_macos()
    return []


def _list_disks_windows():
    """List physical disks on Windows using PowerShell."""
    try:
        cmd_c = ["powershell", "-Command",
                 "Get-Partition -DriveLetter C | Get-Disk | Select-Object -ExpandProperty Number"]
        res_c = subprocess.run(cmd_c, capture_output=True, text=True, check=True)
        boot_disk_num = int(res_c.stdout.strip())
    except Exception:
        boot_disk_num = -1

    try:
        cmd_disks = ["powershell", "-Command",
                     "Get-Disk | Select-Object Number, FriendlyName, Size, BusType | ConvertTo-Json"]
        res_disks = subprocess.run(cmd_disks, capture_output=True, text=True, check=True)

        if not res_disks.stdout.strip():
            return []

        disks_data = json.loads(res_disks.stdout)
        if isinstance(disks_data, dict):
            disks_data = [disks_data]

        formatted_disks = []
        for d in disks_data:
            num = d.get("Number")
            name = d.get("FriendlyName", "Unknown Drive")
            size_bytes = d.get("Size", 0)
            bus = d.get("BusType", "Unknown")
            size_gb = round(size_bytes / (1024**3), 2)
            is_system = (num == boot_disk_num)
            is_removable = bus.lower() in ("usb", "sd", "scsi") and not is_system
            formatted_disks.append({
                "number": num,
                "device": f"\\\\.\\PhysicalDrive{num}",
                "display_name": f"PhysicalDrive{num}",
                "name": name,
                "size_gb": size_gb,
                "bus_type": bus,
                "is_system": is_system,
                "is_removable": is_removable
            })
        formatted_disks.reverse()
        return formatted_disks
    except Exception as e:
        print("Error listing disks (Windows):", e)
        return []


def _list_disks_linux():
    """List block devices on Linux using lsblk."""
    try:
        result = subprocess.run(
            ['lsblk', '-J', '-b', '-o', 'NAME,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS'],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
    except Exception as e:
        print("Error listing disks (Linux):", e)
        return []

    # Find which device names contain the root filesystem
    system_names = set()
    def _find_root(devices):
        for dev in devices:
            mounts = dev.get('mountpoints') or []
            if '/' in mounts:
                system_names.add(dev['name'])
            _find_root(dev.get('children') or [])
    _find_root(data.get('blockdevices', []))

    bus_map = {
        'usb': 'USB', 'mmc': 'SD', 'sata': 'SATA',
        'nvme': 'NVMe', 'ata': 'ATA', 'scsi': 'SCSI'
    }

    formatted = []
    for dev in data.get('blockdevices', []):
        if dev.get('type') != 'disk':
            continue
        name = dev.get('name', '')
        device = f'/dev/{name}'
        size_bytes = int(dev.get('size') or 0)
        size_gb = round(size_bytes / (1024**3), 2)
        tran = (dev.get('tran') or '').lower()
        model = (dev.get('model') or name).strip()
        is_removable = bool(dev.get('rm')) or tran in ('usb', 'mmc')
        is_system = name in system_names
        bus_type = bus_map.get(tran, tran.upper() if tran else 'Unknown')
        formatted.append({
            "number": None,
            "device": device,
            "display_name": device,
            "name": model,
            "size_gb": size_gb,
            "bus_type": bus_type,
            "is_system": is_system,
            "is_removable": is_removable and not is_system
        })

    return list(reversed(formatted))


def _list_disks_macos():
    """List disks on macOS using diskutil."""
    import plistlib

    # Identify the boot disk (e.g. /dev/disk0)
    boot_disk = ''
    try:
        r = subprocess.run(['diskutil', 'info', '-plist', '/'], capture_output=True, check=True)
        info = plistlib.loads(r.stdout)
        boot_node = info.get('DeviceNode', '')
        boot_disk = re.sub(r's\d+$', '', boot_node)  # strip partition suffix
    except Exception:
        pass

    try:
        r = subprocess.run(['diskutil', 'list', '-plist'], capture_output=True, check=True)
        plist = plistlib.loads(r.stdout)
    except Exception as e:
        print("Error listing disks (macOS):", e)
        return []

    formatted = []
    for disk in plist.get('AllDisksAndPartitions', []):
        dev_id = disk.get('DeviceIdentifier', '')
        if not dev_id:
            continue
        device = f'/dev/{dev_id}'
        try:
            r2 = subprocess.run(['diskutil', 'info', '-plist', device], capture_output=True, check=True)
            info = plistlib.loads(r2.stdout)
        except Exception:
            continue

        size_bytes = info.get('TotalSize', 0)
        size_gb = round(size_bytes / (1024**3), 2)
        name = (info.get('MediaName') or info.get('IORegistryEntryName') or dev_id).strip()
        bus = info.get('BusProtocol', 'Unknown')
        is_internal = info.get('Internal', True)
        is_ejectable = info.get('Ejectable', False)
        is_removable = is_ejectable or not is_internal
        is_system = (device == boot_disk)

        formatted.append({
            "number": None,
            "device": device,
            "display_name": device,
            "name": name,
            "size_gb": size_gb,
            "bus_type": bus,
            "is_system": is_system,
            "is_removable": is_removable and not is_system
        })

    return formatted


# ---------------------------------------------------------------------------
# Image fetching
# ---------------------------------------------------------------------------

def fetch_board_images(board_id):
    """Fetch recent image distributions for a specific Orange Pi board from Armbian archives."""
    url = f"https://dl.armbian.com/{board_id}/archive/"
    images = []

    try:
        r = requests.get(url, verify=False, timeout=10)
        if r.status_code == 200:
            links = re.findall(r'href="([^"]+)"', r.text)
            for link in links:
                if link.endswith('.img.xz') and not link.endswith('.asc') and not link.endswith('.sha'):
                    filename = link.lstrip('./')

                    distro = "Unknown"
                    if "bookworm" in filename.lower():
                        distro = "Debian Bookworm"
                    elif "trixie" in filename.lower():
                        distro = "Debian Trixie"
                    elif "noble" in filename.lower():
                        distro = "Ubuntu Noble"
                    elif "jammy" in filename.lower():
                        distro = "Ubuntu Jammy"
                    elif "bullseye" in filename.lower():
                        distro = "Debian Bullseye"
                    elif "resolute" in filename.lower():
                        distro = "Ubuntu Resolute"

                    variant = "CLI / Server"
                    if "desktop" in filename.lower():
                        if "xfce" in filename.lower():
                            variant = "Desktop (XFCE)"
                        elif "gnome" in filename.lower():
                            variant = "Desktop (Gnome)"
                        elif "kde" in filename.lower():
                            variant = "Desktop (KDE Plasma)"
                        elif "cinnamon" in filename.lower():
                            variant = "Desktop (Cinnamon)"
                        else:
                            variant = "Desktop"
                    elif "minimal" in filename.lower():
                        variant = "Minimal / CLI"
                    elif "xfce" in filename.lower():
                        variant = "Desktop (XFCE)"

                    kernel = "Default Kernel"
                    kernel_match = re.search(r'_current_([\d\.]+)', filename)
                    if not kernel_match:
                        kernel_match = re.search(r'_vendor_([\d\.]+)', filename)
                    if not kernel_match:
                        kernel_match = re.search(r'_edge_([\d\.]+)', filename)
                    if kernel_match:
                        kernel = f"Kernel {kernel_match.group(1)}"

                    download_url = f"https://dl.armbian.com/{board_id}/archive/{filename}"
                    images.append({
                        "filename": filename,
                        "distro": distro,
                        "variant": variant,
                        "kernel": kernel,
                        "download_url": download_url
                    })
    except Exception as e:
        print(f"Error fetching images for {board_id}:", e)

    return images


# ---------------------------------------------------------------------------
# Decompression
# ---------------------------------------------------------------------------

def decompress_xz(xz_path, img_path, progress_callback=None):
    """Decompress a .xz file to a .img file with progress updates."""
    compressed_size = os.path.getsize(xz_path)
    bytes_read = 0

    with open(xz_path, 'rb') as f_in:
        decompressor = lzma.LZMADecompressor()
        with open(img_path, 'wb') as f_out:
            while True:
                chunk = f_in.read(1024 * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                decompressed_chunk = decompressor.decompress(chunk)
                if decompressed_chunk:
                    f_out.write(decompressed_chunk)

                if progress_callback:
                    progress = int((bytes_read / compressed_size) * 100)
                    progress_callback("decompressing", progress)

            try:
                unused = decompressor.flush()
                if unused:
                    f_out.write(unused)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Setup script builders
# ---------------------------------------------------------------------------

def _build_user_script(username, password):
    """Build Step 1 script: create the new user."""
    lines = [
        "#!/bin/bash",
        "# Creamsicle: OS Buddy - Step 1 of 2: User Setup",
        "# Run as root on your Orange Pi: sudo bash setup_user.sh",
        "set -e",
        "",
    ]

    if username and password:
        lines.extend([
            f"echo '[+] Creating user {username}...'",
            f"if ! id -u {username} >/dev/null 2>&1; then",
            f"    useradd -m -s /bin/bash -g sudo -G adm,dialout,cdrom,audio,dip,video,plugdev,netdev {username}",
            "fi",
            f"echo '{username}:{password}' | chpasswd",
            "rm -f /root/.not_logged_in_yet",
            "rm -f /root/.firstboot",
            "",
        ])

    lines.extend([
        "echo '[+] User setup complete.'",
        f"echo '[>] Log out and log back in as {username if username else 'your new user'}, then run: sudo bash setup_config.sh'",
    ])

    return "\n".join(lines)


def _build_config_script(hostname, username, wifi_ssid, wifi_password,
                         ssh_key=None, enable_ssh=False, preload_apps=None):
    """Build Step 2 script: apply all system configuration."""
    lines = [
        "#!/bin/bash",
        "# Creamsicle: OS Buddy - Step 2 of 2: System Configuration",
        "# Run as root after logging in as your new user: sudo bash setup_config.sh",
        "set -e",
        "",
    ]

    if hostname:
        lines.extend([
            f"echo '[+] Setting hostname to {hostname}...'",
            f"echo '{hostname}' > /etc/hostname",
            f"sed -i 's/127.0.1.1.*/127.0.1.1\\t{hostname}/g' /etc/hosts",
            f"hostname '{hostname}'",
            "",
        ])

    if username and ssh_key:
        lines.extend([
            f"echo '[+] Installing SSH keys for {username}...'",
            f"mkdir -p /home/{username}/.ssh",
            f"chmod 700 /home/{username}/.ssh",
            f"cat << 'SSHKEY_EOF' > /home/{username}/.ssh/authorized_keys",
            ssh_key,
            "SSHKEY_EOF",
            f"chmod 600 /home/{username}/.ssh/authorized_keys",
            f"chown -R {username}:{username} /home/{username}/.ssh",
            "",
        ])

    if enable_ssh:
        lines.extend([
            "echo '[+] Enabling SSH server...'",
            "systemctl enable ssh >/dev/null 2>&1",
            "systemctl start ssh >/dev/null 2>&1",
            "",
        ])

    if wifi_ssid:
        lines.extend([
            f"echo '[+] Configuring WiFi ({wifi_ssid})...'",
            "if command -v nmcli >/dev/null 2>&1; then",
            f"    nmcli device wifi connect '{wifi_ssid}' password '{wifi_password}' || true",
            "else",
            "    cat << 'WIFI_EOF' >> /etc/wpa_supplicant/wpa_supplicant.conf",
            "network={",
            f'    ssid="{wifi_ssid}"',
            f'    psk="{wifi_password}"',
            "}",
            "WIFI_EOF",
            "fi",
            "",
        ])

    if preload_apps:
        lines.extend([
            "echo '[+] Installing preloaded applications...'",
            "export DEBIAN_FRONTEND=noninteractive",
            "for i in {1..12}; do",
            "    apt-get update -y && break",
            "    echo '[-] Network update failed, retrying in 5s...'",
            "    sleep 5",
            "done",
            "",
        ])

        if "firefox" in preload_apps:
            lines.extend([
                "echo '[+] Installing Firefox...'",
                "apt-get install -y firefox || apt-get install -y firefox-esr",
                "",
            ])
        if "vscode" in preload_apps:
            lines.extend([
                "echo '[+] Installing VS Code...'",
                "apt-get install -y wget gpg apt-transport-https",
                "wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/packages.microsoft.gpg",
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list',
                "apt-get update -y",
                "apt-get install -y code",
                "",
            ])
        if "kiwix" in preload_apps:
            lines.extend([
                "echo '[+] Installing Kiwix...'",
                "apt-get install -y kiwix-desktop || apt-get install -y kiwix",
                "",
            ])
        if "dictionary" in preload_apps:
            lines.extend([
                "echo '[+] Installing GoldenDict...'",
                "apt-get install -y goldendict dictd dict dict-gcide dict-wn",
                "",
            ])
        if "sudoku" in preload_apps:
            lines.extend([
                "echo '[+] Installing GNOME Sudoku...'",
                "apt-get install -y gnome-sudoku",
                "",
            ])
        if "stardew" in preload_apps:
            user_home = f"/home/{username}" if username else "/home/pi"
            user_name = username if username else "pi"
            stardew_dir = f"{user_home}/StardewValley"
            lines.extend([
                "echo '[+] Installing Stardew Valley ARM64 dependencies...'",
                "apt-get install -y mono-complete libopenal1 libsdl2-2.0-0 binutils",
                f"mkdir -p {stardew_dir}",
                f"cat << 'README_EOF' > {stardew_dir}/README_Stardew_Valley.txt",
                "STARDEW VALLEY ARM64 LINUX INSTRUCTIONS",
                "1. Copy your game files into this folder",
                "2. Run: sudo ./setup_stardew_arm64.sh",
                "3. Launch from the desktop shortcut",
                "README_EOF",
                f"cat << 'SETUP_EOF' > {stardew_dir}/setup_stardew_arm64.sh",
                "#!/bin/bash",
                "echo '[+] Configuring Stardew Valley for ARM64...'",
                "cd \"$(dirname \"$0\")\"",
                "mkdir -p lib64",
                "SETUP_EOF",
                f"chmod +x {stardew_dir}/setup_stardew_arm64.sh",
                f"mkdir -p {user_home}/Desktop",
                f"cat << 'LAUNCHER_EOF' > {user_home}/Desktop/StardewValley.desktop",
                "[Desktop Entry]",
                "Name=Stardew Valley",
                f"Exec=mono {stardew_dir}/StardewValley.exe",
                f"Path={stardew_dir}",
                "Icon=applications-games",
                "Terminal=false",
                "Type=Application",
                "LAUNCHER_EOF",
                f"chmod +x {user_home}/Desktop/StardewValley.desktop",
                f"chown -R {user_name}:{user_name} {stardew_dir} {user_home}/Desktop",
                "",
            ])

    lines.append("echo '[+] Configuration complete! Rebooting in 5 seconds...'")
    lines.append("sleep 5 && reboot")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Image customization
# ---------------------------------------------------------------------------

def customize_image(img_path, hostname, username, password, wifi_ssid, wifi_password,
                    ssh_key=None, enable_ssh=False, preload_apps=None):
    """Inject configuration files into the boot partition of the image."""
    user_script = _build_user_script(username, password)
    config_script = _build_config_script(
        hostname, username, wifi_ssid, wifi_password,
        ssh_key, enable_ssh, preload_apps
    )

    armbian_config_lines = [
        "# Headless auto-configuration injected by Creamsicle: OS Buddy",
        "FR_net_change_defaults=1",
        "FR_net_wifi_enabled=1" if wifi_ssid else "FR_net_wifi_enabled=0",
        f"FR_net_wifi_ssid='{wifi_ssid}'" if wifi_ssid else "FR_net_wifi_ssid=''",
        f"FR_net_wifi_key='{wifi_password}'" if wifi_ssid else "FR_net_wifi_key=''",
        "FR_net_wifi_countrycode='US'",
        "FR_general_delete_this_file_after_completion=1",
    ]
    armbian_config_content = "\n".join(armbian_config_lines)

    diag = []

    def log(msg):
        print(msg)
        diag.append(msg)

    log(f"Image: {img_path} ({os.path.getsize(img_path)} bytes)")

    def try_write_config(root_dir):
        for filename in ('armbian_first_run.txt', 'orangepi_first_run.txt'):
            f_handle = root_dir.create(filename)
            f_handle.write(armbian_config_content.encode('utf-8'))
            f_handle.close()

        f_user = root_dir.create("setup_user.sh")
        f_user.write(user_script.encode('utf-8'))
        f_user.close()

        f_config = root_dir.create("setup_config.sh")
        f_config.write(config_script.encode('utf-8'))
        f_config.close()

    def is_fat_volume(obj):
        return obj is not None and not isinstance(obj, str) and hasattr(obj, 'create')

    try:
        log("Strategy 1: auto-detect...")
        result = Volume.vopen(img_path, 'r+b')
        if is_fat_volume(result):
            try_write_config(result)
            Volume.vclose(result)
            log("SUCCESS via auto-detect.")
            return True, None, diag
        else:
            log(f"  Returned {type(result).__name__}: {repr(result)[:100]}")
            if not isinstance(result, str):
                try: Volume.vclose(result)
                except Exception: pass
    except Exception as e:
        log(f"  Failed: {e}")

    for i in range(4):
        try:
            log(f"Strategy 2: partition{i}...")
            part = Volume.vopen(img_path, 'r+b', f'partition{i}')
            if isinstance(part, str):
                log(f"  Error: {part}")
                continue
            if hasattr(part, 'open') and not is_fat_volume(part):
                try:
                    vol = part.open()
                    if is_fat_volume(vol):
                        try_write_config(vol)
                        Volume.vclose(vol)
                        log(f"SUCCESS via partition{i}.")
                        return True, None, diag
                    else:
                        log(f"  Filesystem not FAT: {type(vol).__name__}")
                        try: Volume.vclose(part)
                        except Exception: pass
                except Exception as e2:
                    log(f"  open() failed: {e2}")
                    try: Volume.vclose(part)
                    except Exception: pass
            elif is_fat_volume(part):
                try_write_config(part)
                Volume.vclose(part)
                log(f"SUCCESS via partition{i}.")
                return True, None, diag
            else:
                try: Volume.vclose(part)
                except Exception: pass
        except Exception as e:
            log(f"  Failed: {e}")

    try:
        log("Strategy 3: raw volume...")
        result = Volume.vopen(img_path, 'r+b', 'volume')
        if is_fat_volume(result):
            try_write_config(result)
            Volume.vclose(result)
            log("SUCCESS via raw volume.")
            return True, None, diag
        else:
            log(f"  Returned {type(result).__name__}: {repr(result)[:100]}")
            if not isinstance(result, str):
                try: Volume.vclose(result)
                except Exception: pass
    except Exception as e:
        log(f"  Failed: {e}")

    log("No FAT boot partition found. Saving setup scripts for post-boot SSH application.")
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
    os.makedirs(script_dir, exist_ok=True)

    user_script_path = os.path.join(script_dir, "setup_user.sh")
    with open(user_script_path, 'w', newline='\n') as f:
        f.write(user_script)
    log(f"User setup script saved to: {user_script_path}")

    config_script_path = os.path.join(script_dir, "setup_config.sh")
    with open(config_script_path, 'w', newline='\n') as f:
        f.write(config_script)
    log(f"Config script saved to: {config_script_path}")

    return False, [user_script_path, config_script_path], diag


# ---------------------------------------------------------------------------
# Flashing
# ---------------------------------------------------------------------------

def flash_to_drive(img_path, device, progress_callback=None):
    """Write the image file to a physical drive. Device is the platform-specific path."""
    if _SYSTEM == 'Windows':
        return _flash_windows(img_path, device, progress_callback)
    elif _SYSTEM == 'Linux':
        return _flash_linux(img_path, device, progress_callback)
    elif _SYSTEM == 'Darwin':
        return _flash_macos(img_path, device, progress_callback)
    else:
        if progress_callback:
            progress_callback("error", f"Unsupported operating system: {_SYSTEM}")
        return False


def _flash_windows(img_path, device, progress_callback=None):
    """Flash on Windows: diskpart clean + Win32 raw write."""
    try:
        disk_number = int(re.search(r'\d+$', device).group())
    except Exception:
        if progress_callback:
            progress_callback("error", f"Invalid device path: {device}")
        return False

    diskpart_script = f"select disk {disk_number}\nclean\n"
    script_path = os.path.join(os.environ.get("TEMP", "."), "diskpart_clean.txt")

    with open(script_path, "w") as f:
        f.write(diskpart_script)

    try:
        if progress_callback:
            progress_callback("cleaning", 0)
        subprocess.run(["diskpart", "/s", script_path], capture_output=True, check=True)
    except Exception as e:
        print("Diskpart clean failed:", e)
        if progress_callback:
            progress_callback("error", "Failed to clean disk partitions. Make sure no programs are using the SD card.")
        return False
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)

    try:
        img_size = os.path.getsize(img_path)
        bytes_written = 0

        if progress_callback:
            progress_callback("writing", 0)

        GENERIC_WRITE = 0x40000000
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        FILE_FLAG_WRITE_THROUGH = 0x80000000
        FILE_FLAG_NO_BUFFERING = 0x20000000

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            device,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_WRITE_THROUGH | FILE_FLAG_NO_BUFFERING,
            None
        )

        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        if handle == INVALID_HANDLE_VALUE:
            err = ctypes.GetLastError()
            if progress_callback:
                progress_callback("error", f"Cannot open {device} (Windows error {err}). Is the drive in use?")
            return False

        try:
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
            CHUNK_SIZE = 4 * 1024 * 1024

            with open(img_path, "rb") as f_in:
                while True:
                    chunk = f_in.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    remainder = len(chunk) % 512
                    if remainder != 0:
                        chunk += b'\x00' * (512 - remainder)
                    os.write(fd, chunk)
                    bytes_written += len(chunk)
                    if progress_callback:
                        progress = min(int((bytes_written / img_size) * 100), 100)
                        progress_callback("writing", progress)
        finally:
            os.close(fd)

        if progress_callback:
            progress_callback("success", 100)
        return True
    except Exception as e:
        print("Writing to drive failed:", e)
        if progress_callback:
            progress_callback("error", f"Write failed: {str(e)}")
        return False


def _flash_linux(img_path, device, progress_callback=None):
    """Flash on Linux: unmount partitions, then direct raw write."""
    if progress_callback:
        progress_callback("cleaning", 0)

    # Unmount all partitions of the device (e.g. /dev/sdb1, /dev/sdb2)
    for part in sorted(glob.glob(f'{device}*')):
        if part != device:
            subprocess.run(['umount', part], capture_output=True)

    try:
        img_size = os.path.getsize(img_path)
        bytes_written = 0
        CHUNK_SIZE = 4 * 1024 * 1024

        if progress_callback:
            progress_callback("writing", 0)

        with open(img_path, 'rb') as f_in, open(device, 'wb') as f_out:
            while True:
                chunk = f_in.read(CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)
                bytes_written += len(chunk)
                if progress_callback:
                    progress = min(int((bytes_written / img_size) * 100), 100)
                    progress_callback("writing", progress)
            f_out.flush()
            os.fsync(f_out.fileno())

        if progress_callback:
            progress_callback("success", 100)
        return True
    except PermissionError:
        if progress_callback:
            progress_callback("error", f"Permission denied writing to {device}. Try running with sudo.")
        return False
    except Exception as e:
        print("Writing to drive failed:", e)
        if progress_callback:
            progress_callback("error", f"Write failed: {str(e)}")
        return False


def _flash_macos(img_path, device, progress_callback=None):
    """Flash on macOS: unmount disk, then raw write via /dev/rdisk for speed."""
    if progress_callback:
        progress_callback("cleaning", 0)

    subprocess.run(['diskutil', 'unmountDisk', device], capture_output=True)

    # /dev/rdisk bypasses the buffer cache and is significantly faster on macOS
    raw_device = device.replace('/dev/disk', '/dev/rdisk')

    try:
        img_size = os.path.getsize(img_path)
        bytes_written = 0
        CHUNK_SIZE = 4 * 1024 * 1024

        if progress_callback:
            progress_callback("writing", 0)

        with open(img_path, 'rb') as f_in, open(raw_device, 'wb') as f_out:
            while True:
                chunk = f_in.read(CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)
                bytes_written += len(chunk)
                if progress_callback:
                    progress = min(int((bytes_written / img_size) * 100), 100)
                    progress_callback("writing", progress)
            f_out.flush()
            os.fsync(f_out.fileno())

        subprocess.run(['sync'], capture_output=True)

        if progress_callback:
            progress_callback("success", 100)
        return True
    except PermissionError:
        if progress_callback:
            progress_callback("error", f"Permission denied writing to {raw_device}. Try running with sudo.")
        return False
    except Exception as e:
        print("Writing to drive failed:", e)
        if progress_callback:
            progress_callback("error", f"Write failed: {str(e)}")
        return False
