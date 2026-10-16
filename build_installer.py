import os
import shutil
import subprocess
import sys


INNO_DEFAULT_PATHS = [
    r"E:\Program Files\Inno Setup 7\ISCC.exe",
    r"E:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    r"C:\Program Files\Inno Setup 7\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def _find_iscc():
    # 先看 PATH
    from_path = shutil.which("ISCC.exe")
    if from_path:
        return from_path
    # 再看常见安装目录
    for p in INNO_DEFAULT_PATHS:
        if os.path.exists(p):
            return p
    return None


def build_exe():
    print("[1/2] Building exe with PyInstaller...")
    subprocess.check_call([sys.executable, "build_exe.py"])


def build_installer():
    print("[2/2] Building installer with Inno Setup...")
    iscc = _find_iscc()
    if not iscc:
        raise RuntimeError(
            "找不到 Inno Setup 编译器 ISCC.exe，请先安装 Inno Setup 6。"
        )
    subprocess.check_call([iscc, "installer.iss"])
    print("\nDone! Installer output: dist\\DesktopTimezoneClock-Setup.exe")


if __name__ == "__main__":
    build_exe()
    build_installer()
