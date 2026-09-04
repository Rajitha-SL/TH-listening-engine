"""
Automated Build Script for Trailhead Market Listening Engine Desktop Executable
Packages GUI application into a standalone distribution folder & zip archive for Barbara Roos.
"""

import sys
import os
import time
import stat
import shutil
import zipfile
import subprocess


def _handle_remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def remove_dir_force(path):
    if not os.path.exists(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for file in files:
            p = os.path.join(root, file)
            try:
                os.chmod(p, stat.S_IWRITE)
                os.unlink(p)
            except Exception:
                pass
        for d in dirs:
            p = os.path.join(root, d)
            try:
                os.chmod(p, stat.S_IWRITE)
                os.rmdir(p)
            except Exception:
                pass
    if os.path.exists(path):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
        except Exception:
            pass
    if os.path.exists(path) and os.name == 'nt':
        try:
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", path], check=False)
        except Exception:
            pass


def build():
    print("=========================================================")
    print(" Building Trailhead Engine Desktop Standalone Executable")
    print("=========================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "dist")
    target_dir = os.path.join(dist_dir, "TrailheadEngine")
    zip_path = os.path.join(dist_dir, "TrailheadEngine_v1.0_Standalone.zip")

    # 0. Terminate running executable if open
    if os.name == 'nt':
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "TrailheadEngine.exe"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
        except Exception:
            pass

    # 1. Clean previous build artifacts
    for attempt in range(5):
        if os.path.exists(target_dir):
            print(f"Cleaning previous build target (attempt {attempt + 1}): {target_dir}")
            remove_dir_force(target_dir)
            time.sleep(0.5)
        else:
            break

    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception:
            pass

    # 2. Run PyInstaller on gui.spec
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "gui.spec"
    ]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=base_dir)

    if res.returncode != 0:
        print("[ERROR] Build failed during PyInstaller execution!")
        sys.exit(res.returncode)

    # 3. Ensure required directories exist inside distribution
    os.makedirs(os.path.join(target_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(target_dir, "memory"), exist_ok=True)

    # Copy memory history store default if present
    src_mem = os.path.join(base_dir, "memory", "history_store.json")
    dst_mem = os.path.join(target_dir, "memory", "history_store.json")
    if os.path.exists(src_mem) and not os.path.exists(dst_mem):
        shutil.copy2(src_mem, dst_mem)

    print("PyInstaller build succeeded!")
    print(f"Standalone application location: {target_dir}")

    # 4. Create ZIP distribution package for Barbara
    print(f"Packaging distribution ZIP archive to: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, dist_dir)
                zf.write(abs_path, rel_path)

    print(f"Build Complete! Distribution ready: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        secret_hits = [
            info.filename
            for info in zf.infolist()
            if os.path.basename(info.filename) in {".env", ".env.local"}
            or info.filename.endswith("/.env")
        ]
        if secret_hits:
            print("[ERROR] Distribution ZIP contains .env; refusing to ship an API key.")
            sys.exit(1)


if __name__ == "__main__":
    build()
