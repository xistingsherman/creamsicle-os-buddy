import sys
import os
import ctypes
import subprocess
import time
import webbrowser
import threading

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def open_browser():
    # Wait a bit for the Flask server to start
    time.sleep(1.5)
    print("Opening browser to http://127.0.0.1:5000...")
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    # 1. Elevate script to administrator so we can lock, format, and flash physical drives
    if not is_admin():
        print("UAC Elevation: Requesting administrator privileges...")
        script = os.path.abspath(sys.argv[0])
        # Re-run this script using python with administrator privileges
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
        sys.exit(0)
        
    print("[+] Running with Administrator privileges.")
    
    # 2. Add current folder to path so app.py imports work correctly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # 3. Import app after sys.path is updated
    import app
    
    # 4. Launch web browser in a background thread (avoid duplicate windows opening when Flask reloads in debug mode)
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        t = threading.Thread(target=open_browser)
        t.daemon = True
        t.start()
    
    # 5. Start Flask server
    print("Starting Creamsicle: OS Buddy server on http://127.0.0.1:5000...")
    app.app.run(host="127.0.0.1", port=5000, debug=True)
