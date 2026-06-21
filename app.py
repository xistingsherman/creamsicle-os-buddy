import os
import time
import threading
import requests
import shutil
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, render_template, request, send_from_directory
import flasher

app = Flask(__name__, static_folder="static", template_folder="templates")

# Caches and workspaces
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(WORKSPACE_DIR, "cache")
TEMP_DIR = os.path.join(WORKSPACE_DIR, "temp")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Global flashing state
flash_state = {
    "status": "idle",       # idle, downloading, decompressing, cleaning, writing, success, error
    "progress": 0,          # 0 to 100
    "message": "",          # Detail string
    "cancel_requested": False
}

flash_lock = threading.Lock()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/boards")
def get_boards():
    return jsonify({"boards": [{"id": k, "name": v} for k, v in flasher.BOARDS.items()]})

@app.route("/api/disks")
def get_disks():
    return jsonify({"disks": flasher.list_disks()})

@app.route("/api/images/<board_id>")
def get_images(board_id):
    if board_id not in flasher.BOARDS:
        return jsonify({"error": "Invalid board"}), 400
    return jsonify({"images": flasher.fetch_board_images(board_id)})

@app.route("/api/github_keys")
def get_github_keys():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400
    try:
        r = requests.get(f"https://github.com/{username}.keys", timeout=5)
        if r.status_code == 200:
            return jsonify({"keys": r.text})
        else:
            return jsonify({"error": f"Failed to fetch keys (HTTP {r.status_code})"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

ALLOWED_EXTENSIONS = {'.img', '.xz', '.iso'}

@app.route("/api/check_upload", methods=["POST"])
def check_upload():
    data = request.json or {}
    filename = data.get("filename", "")
    file_size = data.get("size", 0)

    if not filename:
        return jsonify({"exists": False})

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"exists": False})

    safe_name = secure_filename(filename)
    save_path = os.path.join(TEMP_DIR, safe_name)

    if os.path.exists(save_path) and os.path.getsize(save_path) == file_size:
        return jsonify({"exists": True, "path": save_path, "filename": safe_name})

    return jsonify({"exists": False})

@app.route("/api/upload", methods=["POST"])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Invalid file type '{ext}'. Allowed: .img, .xz, .iso"}), 400

    filename = secure_filename(f.filename)
    save_path = os.path.join(TEMP_DIR, filename)
    f.save(save_path)

    return jsonify({"path": save_path, "filename": filename})

@app.route("/api/status")
def get_status():
    with flash_lock:
        return jsonify(flash_state)

@app.route("/api/cancel", methods=["POST"])
def cancel_flash():
    with flash_lock:
        if flash_state["status"] in ("downloading", "decompressing"):
            flash_state["cancel_requested"] = True
            flash_state["status"] = "idle"
            flash_state["message"] = "Operation cancelled by user."
            return jsonify({"status": "cancelled"})
        return jsonify({"error": "Cannot cancel at this stage"}), 400

def background_flash_thread(params):
    global flash_state
    
    board_id = params.get("board_id")
    download_url = params.get("download_url")
    local_image_path = params.get("local_image_path")
    disk_number = int(params.get("disk_number"))
    
    hostname = params.get("hostname", "").strip()
    username = params.get("username", "").strip()
    password = params.get("password", "").strip()
    wifi_ssid = params.get("wifi_ssid", "").strip()
    wifi_password = params.get("wifi_password", "").strip()
    ssh_key = params.get("ssh_key", "").strip()
    enable_ssh = params.get("enable_ssh", False)
    preload_apps = params.get("preload_apps", [])
    
    # 1. Determine local source file (.xz or .img)
    source_file_path = ""
    is_temp_download = False
    
    if board_id == "custom":
        source_file_path = local_image_path
        if not os.path.exists(source_file_path):
            update_state("error", 0, "Selected local image file does not exist.")
            return
    else:
        # Download from URL
        filename = download_url.split("/")[-1]
        source_file_path = os.path.join(CACHE_DIR, filename)
        
        # Check if already cached
        if os.path.exists(source_file_path):
            print("Found image in cache.")
        else:
            is_temp_download = True
            update_state("downloading", 0, "Starting image download...")
            
            try:
                # Download file with progress updates
                r = requests.get(download_url, stream=True, verify=False)
                if r.status_code != 200:
                    update_state("error", 0, f"Download failed (HTTP {r.status_code})")
                    return
                    
                total_length = r.headers.get('content-length')
                dl_path = source_file_path + ".tmp"
                
                with open(dl_path, 'wb') as f:
                    if total_length is None:
                        f.write(r.content)
                    else:
                        total_length = int(total_length)
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if get_cancel_requested():
                                f.close()
                                if os.path.exists(dl_path):
                                    os.remove(dl_path)
                                return
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress = int((downloaded / total_length) * 100)
                                update_state("downloading", progress, f"Downloading: {progress}% ({round(downloaded/(1024**2), 1)} MB / {round(total_length/(1024**2), 1)} MB)")
                
                os.rename(dl_path, source_file_path)
            except Exception as e:
                update_state("error", 0, f"Download failed: {str(e)}")
                return

    # 2. Decompress if it's a .xz file
    uncompressed_img_path = ""
    
    if source_file_path.endswith('.xz'):
        uncompressed_filename = os.path.basename(source_file_path)[:-3] # Strip .xz
        uncompressed_img_path = os.path.join(TEMP_DIR, uncompressed_filename)
        
        update_state("decompressing", 0, "Decompressing image...")
        
        def decompress_progress(stage, progress):
            if get_cancel_requested():
                return
            update_state("decompressing", progress, f"Decompressing image: {progress}%")
            
        try:
            flasher.decompress_xz(source_file_path, uncompressed_img_path, decompress_progress)
            if get_cancel_requested():
                if os.path.exists(uncompressed_img_path):
                    os.remove(uncompressed_img_path)
                return
        except Exception as e:
            update_state("error", 0, f"Decompression failed: {str(e)}")
            return
    else:
        # It's a raw .img or .iso, make a copy in temp folder so we can customize it
        uncompressed_filename = os.path.basename(source_file_path)
        uncompressed_img_path = os.path.join(TEMP_DIR, "customized_" + uncompressed_filename)
        update_state("decompressing", 50, "Preparing image file...")
        try:
            shutil.copyfile(source_file_path, uncompressed_img_path)
        except Exception as e:
            update_state("error", 0, f"Failed to copy image file: {str(e)}")
            return

    # 3. Customize the boot partition settings
    has_customization = any([hostname, username, password, wifi_ssid, wifi_password, ssh_key, enable_ssh, preload_apps])

    setup_script_paths = None

    if has_customization:
        update_state("decompressing", 90, "Applying configuration settings...")
        customized, setup_script_paths, diag_messages = flasher.customize_image(
            uncompressed_img_path,
            hostname=hostname,
            username=username,
            password=password,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            ssh_key=ssh_key,
            enable_ssh=enable_ssh,
            preload_apps=preload_apps
        )

        if customized:
            print("Configuration injected into image boot partition.")
        else:
            print("No FAT partition found. Will flash image and provide post-boot setup script.")

    # 4. Flash to SD drive
    def flash_progress(stage, progress):
        if stage == "cleaning":
            update_state("cleaning", 0, "Formatting drive partitions...")
        elif stage == "writing":
            update_state("writing", progress, f"Writing image to drive: {progress}%")
        elif stage == "success":
            if setup_script_paths:
                update_state("success", 100,
                    f"SETUP_SCRIPTS:{'|'.join(setup_script_paths)}")
            else:
                update_state("success", 100, "Successfully flashed and configured!")
        elif stage == "error":
            update_state("error", 0, progress) # Progress contains error message

    try:
        flasher.flash_to_drive(uncompressed_img_path, disk_number, flash_progress)
    except Exception as e:
        update_state("error", 0, f"Flashing failed: {str(e)}")
    finally:
        # Clean up the uncompressed image in the temp folder to save space
        if os.path.exists(uncompressed_img_path):
            try:
                os.remove(uncompressed_img_path)
            except Exception:
                pass

def update_state(status, progress, message):
    with flash_lock:
        flash_state["status"] = status
        flash_state["progress"] = progress
        flash_state["message"] = message

def get_cancel_requested():
    with flash_lock:
        return flash_state["cancel_requested"]

@app.route("/api/flash", methods=["POST"])
def flash():
    global flash_state
    
    data = request.json
    try:
        disk_number = int(data.get("disk_number"))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid disk number"}), 400

    # Validate target disk safety on backend
    disks = flasher.list_disks()
    target_disk = next((d for d in disks if d["number"] == disk_number), None)
    if not target_disk:
        return jsonify({"error": "Target disk not found"}), 400
        
    is_protected = target_disk.get("is_system") or target_disk.get("bus_type", "").lower() == "sata" or not target_disk.get("is_removable")
    if is_protected:
        return jsonify({"error": "Selected drive is protected (system drive, internal SATA drive, or non-removable). Flashing blocked for safety."}), 400
    
    # Check if flash is already running
    with flash_lock:
        if flash_state["status"] not in ("idle", "success", "error"):
            return jsonify({"error": "Flashing is already in progress"}), 400
            
        # Reset state
        flash_state["status"] = "starting"
        flash_state["progress"] = 0
        flash_state["message"] = "Initializing flashing task..."
        flash_state["cancel_requested"] = False
        
    # Start thread
    t = threading.Thread(target=background_flash_thread, args=(data,))
    t.daemon = True
    t.start()
    
    return jsonify({"status": "started"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
