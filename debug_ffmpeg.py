import shutil
import subprocess
import os
import platform

print(f"OS: {platform.system()}")
print(f"shutil.which('ffmpeg'): {shutil.which('ffmpeg')}")

try:
    out = subprocess.check_output('"ffmpeg" -version', shell=True, stderr=subprocess.STDOUT).decode()
    print(f"Success with quotes: {out.splitlines()[0]}")
except Exception as e:
    print(f"Error with quotes: {e}")

try:
    out = subprocess.check_output('ffmpeg -version', shell=True, stderr=subprocess.STDOUT).decode()
    print(f"Success without quotes: {out.splitlines()[0]}")
except Exception as e:
    print(f"Error without quotes: {e}")
