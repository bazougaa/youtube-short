import os
import shutil
import subprocess
import platform

def get_ffmpeg_path():
    # 1. Check if it's already in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
        
    # 2. Check common paths based on OS
    system = platform.system()
    possible_paths = []
    
    if system == "Windows":
        possible_paths = [
            os.path.join(os.getcwd(), "ffmpeg.exe"),
            os.path.join(os.path.dirname(os.getcwd()), "ffmpeg.exe"),
            r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
            r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
    else:
        # Linux / MacOS common paths
        possible_paths = [
            os.path.join(os.getcwd(), "ffmpeg"),
            os.path.join(os.path.dirname(os.getcwd()), "ffmpeg"),
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg", # Apple Silicon
            "/usr/lib/ffmpeg",
        ]
        
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    # 3. Last resort
    return "ffmpeg"

def get_ffprobe_path():
    # 1. Check if it's already in PATH
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return ffprobe_path
        
    # 2. Check common paths based on OS
    system = platform.system()
    possible_paths = []
    
    if system == "Windows":
        possible_paths = [
            os.path.join(os.getcwd(), "ffprobe.exe"),
            os.path.join(os.path.dirname(os.getcwd()), "ffprobe.exe"),
            r"C:\ProgramData\chocolatey\bin\ffprobe.exe",
            r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffprobe.exe",
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
        ]
    else:
        # Linux / MacOS common paths
        possible_paths = [
            os.path.join(os.getcwd(), "ffprobe"),
            os.path.join(os.path.dirname(os.getcwd()), "ffprobe"),
            "/usr/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/opt/homebrew/bin/ffprobe", # Apple Silicon
            "/usr/lib/ffprobe",
        ]
        
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    # 3. Last resort
    return "ffprobe"

FFMPEG_EXE = get_ffmpeg_path()
FFPROBE_EXE = get_ffprobe_path()

# Update environment PATH to include the directory of the found executables
# This helps libraries like whisper or yt-dlp find them automatically
def update_env_path():
    paths_to_add = []
    
    for exe in [FFMPEG_EXE, FFPROBE_EXE]:
        if os.path.isabs(exe):
            dir_path = os.path.dirname(exe)
            if dir_path not in os.environ["PATH"]:
                paths_to_add.append(dir_path)
    
    if paths_to_add:
        # Use appropriate path separator
        sep = ";" if platform.system() == "Windows" else ":"
        os.environ["PATH"] = sep.join(paths_to_add) + sep + os.environ["PATH"]

update_env_path()

def run_ffmpeg_command(command_args):
    """Run an ffmpeg command using the detected FFMPEG_EXE"""
    # If FFMPEG_EXE is just a command name and not an absolute path,
    # we don't want to wrap it in quotes if it's being used in a shell command string.
    # However, if it contains spaces (like in Program Files), it MUST be quoted.
    
    executable = FFMPEG_EXE
    if " " in executable and not executable.startswith('"'):
        executable = f'"{executable}"'
        
    if isinstance(command_args, list):
        # When passing a list, subprocess handles quoting automatically
        # We should use the unquoted path here
        cmd = [FFMPEG_EXE] + command_args
        return subprocess.call(cmd)
    else:
        # If it's a string, we assume it's the full command minus the 'ffmpeg' part
        # or it starts with 'ffmpeg' and we need to replace it
        if command_args.startswith("ffmpeg "):
            cmd = f'{executable}' + command_args[6:]
        else:
            cmd = f'{executable} {command_args}'
        return subprocess.call(cmd, shell=True)
