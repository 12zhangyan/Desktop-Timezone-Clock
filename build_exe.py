import os
import subprocess
import sys

def build():
    # 确保安装了 pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 打包指令
    # --noconsole: 不显示控制台窗口
    # --onefile: 打包成单一 exe
    # --name: 指定文件名
    # --add-data: 包含必要的文件 (Windows 下格式为 "src;dest")
    
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=DesktopTimezoneClock",
        "--clean",
        "--collect-all=tzdata",
        # 核心：包含 CustomTkinter 的资源文件 (json/txt)
        f"--add-data={ctk_path};customtkinter/",
        "main.py"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    print("\nBuild completed! The executable is in the 'dist' folder.")

if __name__ == "__main__":
    build()
