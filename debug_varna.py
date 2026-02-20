"""
VARNA v1.6.1 - Standalone Debug Script
Run this to troubleshoot hardware or dependency issues.
"""

import sys
import os
import time
import subprocess
import json
from pathlib import Path

def print_header(text):
    print(f"\n{'='*60}")
    print(f" {text.center(58)} ")
    print(f"{'='*60}")

def check_dependencies():
    print_header("1. Checking Dependencies")
    deps = ["speech_recognition", "pyttsx3", "pyautogui", "psutil", "win32gui", "pythoncom", "difflib", "PIL", "pystray"]
    missing = []
    for d in deps:
        try:
            __import__(d)
            print(f"✅ {d:20} Installed")
        except ImportError:
            print(f"❌ {d:20} MISSING")
            missing.append(d)
    return missing

def check_mic():
    print_header("2. Checking Microphone")
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        if not mics:
            print("❌ No microphones found!")
            return False
        print(f"✅ {len(mics)} microphones found.")
        print(f"   Default: {mics[0]}")
        return True
    except Exception as e:
        print(f"❌ Mic Error: {e}")
        return False

def check_internet():
    print_header("3. Checking Internet (for Google STT)")
    import socket
    try:
        socket.create_connection(("www.google.com", 80), timeout=3)
        print("✅ Internet connection OK")
        return True
    except OSError:
        print("⚠️  No Internet - Google STT will likely fail.")
        return False

def check_app_index():
    print_header("4. Checking App Index (apps.json)")
    cache_path = Path("apps.json")
    if not cache_path.exists():
        print("⚠️  apps.json MISSING - Universal app control will be limited.")
        return False
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ Index found: {len(data)} apps indexed.")
            return True
    except Exception as e:
        print(f"❌ Index corrupted: {e}")
        return False

def check_window_mgr():
    print_header("5. Checking Window Tracking")
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        print(f"✅ Active window detection OK")
        print(f"   Foreground: '{title}'")
        return True
    except Exception as e:
        print(f"❌ Window detection failed: {e}")
        return False

def main():
    print_header("VARNA SYSTEM DIAGNOSTICS")
    print(f"Python: {sys.version.split(' ')[0]}")
    print(f"OS:     {sys.platform}")
    
    missing = check_dependencies()
    check_mic()
    check_internet()
    check_app_index()
    check_window_mgr()
    
    print_header("DIAGNOSTICS COMPLETE")
    if missing:
        print(f"Recommendation: pip install {' '.join(missing)}")
    else:
        print("Everything looks good! If issues persist, check varna.log.")

if __name__ == "__main__":
    main()
