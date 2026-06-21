# Creamsicle: OS Buddy

[![CI](https://github.com/YOUR_USERNAME/creamsicle-os-buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/creamsicle-os-buddy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Creamsicle: OS Buddy** is a free Windows app that makes setting up an Orange Pi single-board computer simple and painless — even if you've never done it before.

Instead of downloading images manually, burning them with a separate tool, and then fiddling with config files on the SD card, Creamsicle does it all in one place: pick your board, pick your OS, set your Wi-Fi and username, and click Flash. That's it.

> **What's an Orange Pi?** Orange Pi boards are small, affordable computers (think a credit card with a processor on it) that run Linux. People use them as home servers, media centers, retro gaming machines, and all sorts of DIY projects.

---

## What Creamsicle Does For You

- **Finds the latest OS for your board automatically** — no hunting around download pages
- **Lets you set up Wi-Fi, username, and password before you even boot** — so your Pi connects to your network on its very first start
- **Can enable SSH out of the box** — connect to your Pi remotely from another computer, no monitor required
- **Installs apps at first boot** — Firefox, VS Code, Kiwix, and more, already waiting for you
- **Protects your PC** — won't let you accidentally overwrite your main hard drive

---

## What You'll Need

- A Windows 10 or Windows 11 PC
- Python 3.8 or newer ([download here](https://www.python.org/downloads/) — check "Add Python to PATH" during install)
- A microSD card or USB drive (8 GB or larger) and a card reader
- An Orange Pi board (see the [supported boards](#supported-boards) list below)

---

## Installation

Open a Command Prompt or PowerShell window, navigate to the Creamsicle folder, and run:

```
pip install -r requirements.txt
```

This downloads the few Python libraries the app needs. You only have to do this once.

---

## How to Use It

### 1. Launch the app

```
python run.py
```

A browser window will open automatically. You'll also see a **Windows security prompt** asking for Administrator access — this is required so the app can write to your SD card. Click **Yes**.

### 2. Choose your board

Pick your Orange Pi model from the dropdown list.

### 3. Choose your operating system

Creamsicle fetches the latest available OS images for your board directly from the Armbian project. You'll see options like:

- **Minimal / CLI** — a bare-bones Linux system, good for servers and projects where you don't need a desktop
- **Desktop (XFCE)** — a full graphical desktop, great for everyday use
- **Desktop (Gnome / KDE)** — alternative desktop environments

If you already have an image file (`.img`, `.img.xz`, or `.iso`) saved on your computer, choose **Custom Image** instead and upload it.

### 4. Configure your settings (optional but recommended)

Click **Configure Settings** to open the setup panel. You can set:

**General tab**
- **Username** — the name you'll log in with (e.g. `pi`)
- **Password** — your login password
- **Hostname** — the name your Pi will show up as on your network (e.g. `orangepi`)

**WiFi tab**
- **Network name (SSID)** — the name of your home Wi-Fi network
- **Password** — your Wi-Fi password

**SSH tab**
- **Enable SSH** — tick this box if you want to connect to your Pi remotely from another computer (see [Connecting Without a Monitor](#connecting-without-a-monitor) below)
- **SSH Key** — an advanced option for passwordless login; you can skip this for now

**Preload Apps tab**
- Tick any apps you'd like pre-installed when your Pi boots for the first time (see [Preloadable Apps](#preloadable-apps) below)

### 5. Select your SD card or USB drive

Click the storage selector and choose your SD card or USB drive from the list. Creamsicle only shows removable drives and will never show your main PC hard drive.

> **Double-check before you continue.** Flashing will erase everything on the selected drive.

### 6. Flash!

Click **Flash** and watch the progress bar. The app will:
1. Download the OS image (this can take a few minutes depending on your connection)
2. Decompress it
3. Apply your settings
4. Write it to your SD card

When it says **Success**, safely eject the card, pop it into your Orange Pi, and power it on.

---

## Connecting Without a Monitor

If you ticked **Enable SSH** in the settings, you can control your Pi entirely from another computer — no TV or keyboard needed. This is called running "headless."

After your Pi finishes booting (give it 1–2 minutes on first boot):

1. Open **PowerShell** or **Command Prompt** on your PC
2. Type:
   ```
   ssh username@hostname.local
   ```
   For example, if you set your username to `pi` and hostname to `orangepi`:
   ```
   ssh pi@orangepi.local
   ```
3. Enter your password when asked

**Can't connect with `.local`?** Log into your home router (usually at `192.168.1.1` or `192.168.0.1` in a browser) and look for a "Connected Devices" or "DHCP Clients" list. Find your Pi's hostname and use its IP address instead:
```
ssh pi@192.168.1.42
```

---

## Preloadable Apps

These apps get installed automatically on first boot (your Pi needs internet access):

| App | What it's for |
| :--- | :--- |
| **Firefox** | Web browser |
| **VS Code** | Code editor, great for programming projects on the Pi |
| **Kiwix** | Offline encyclopedia — browse Wikipedia without internet |
| **GoldenDict** | Offline dictionary |
| **GNOME Sudoku** | Sudoku puzzle game |
| **Stardew Valley** | Sets up ARM64 dependencies and a launcher for Stardew Valley (you'll need your own copy of the game files) |

> **No internet on first boot?** If your Pi couldn't download the apps automatically, SSH in once your network is working and run:
> ```
> sudo bash /boot/setup_orangepi.sh
> ```

---

## Supported Boards

| Board ID | Name |
| :--- | :--- |
| `orangepizero3` | Orange Pi Zero 3 |
| `orangepi5` | Orange Pi 5 |
| `orangepi5-plus` | Orange Pi 5 Plus |
| `orangepizero2` | Orange Pi Zero 2 |
| `orangepi3-lts` | Orange Pi 3 LTS |
| `orangepi4-lts` | Orange Pi 4 LTS |
| `orangepi4pro` | Orange Pi 4 Pro |
| `orangepione` | Orange Pi One |
| `orangepizero` | Orange Pi Zero |
| `orangepipc2` | Orange Pi PC 2 |

Don't see your board? See [CONTRIBUTING.md](CONTRIBUTING.md) for how to request or add support for a new one.

---

## Troubleshooting

**The app asks for Administrator access — is that normal?**
Yes. Writing to a physical drive (like your SD card) requires Administrator privileges on Windows. The app cannot work without it.

**My SD card or USB drive isn't showing up in the list**
- Make sure Windows has detected it — check that it appears in File Explorer first
- Try a different USB port or card reader
- Click the **Refresh** button in the storage selector

**Flashing failed with a "drive locked" or "write denied" error**
- Close any File Explorer windows that are showing the SD card's contents
- Make sure the physical write-protect switch on your SD card adapter (a small sliding tab on the side) is in the unlocked position
- Eject and re-insert the card, then try again

**My Pi booted but I can't find it on the network**
- Give it a full 2 minutes — first boot takes longer than usual
- Make sure the Pi is connected to power properly (Orange Pi boards need a stable 5V power supply)
- Double-check that you entered the correct Wi-Fi network name and password before flashing

**The `.local` address doesn't work**
Some home routers don't support `.local` addresses. Use your router's admin page to find the Pi's IP address and connect directly with `ssh username@ip-address`.

---

## Contributing

We'd love your help! See [CONTRIBUTING.md](CONTRIBUTING.md) for how to report bugs, request new boards, or submit code changes. All skill levels welcome.

---

## License

MIT License — see [LICENSE](LICENSE) for details. Free to use, modify, and share.

---

<details>
<summary>For Developers — Architecture & API Reference</summary>

### How It Works

Creamsicle runs a local Python Flask web server (`app.py`) that your browser connects to. The `flasher.py` module handles all the low-level work: querying Windows for attached drives via PowerShell, parsing Armbian's download pages, decompressing `.xz` images, patching the FAT32 boot partition with configuration files, erasing drive partitions with `diskpart`, and writing the image byte-for-byte to the physical drive via the Win32 API.

### Project Structure

| File | Role |
| :--- | :--- |
| [run.py](run.py) | Entry point — requests UAC elevation, opens browser, starts Flask |
| [app.py](app.py) | Flask server — API routes, upload handling, flash thread orchestration |
| [flasher.py](flasher.py) | Core engine — disk detection, image parsing, decompression, customization, writing |
| [templates/index.html](templates/index.html) | Dashboard UI |
| [static/css/styles.css](static/css/styles.css) | Dark-mode glassmorphic styles |
| [static/js/main.js](static/js/main.js) | Frontend logic — modals, polling, progress updates |

### API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | GET | Dashboard UI |
| `/api/boards` | GET | List of supported Orange Pi models |
| `/api/disks` | GET | Detected removable drives (system drive excluded) |
| `/api/images/<board_id>` | GET | Available OS images from Armbian for the given board |
| `/api/github_keys` | GET | Fetch public SSH keys from `github.com/<username>.keys` |
| `/api/check_upload` | POST | Check if an uploaded file already exists in temp storage |
| `/api/upload` | POST | Upload a local image file |
| `/api/status` | GET | Current flash state, progress percentage, and message |
| `/api/cancel` | POST | Cancel an in-progress download or decompression |
| `/api/flash` | POST | Start the full download → decompress → customize → write pipeline |

### Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

</details>
