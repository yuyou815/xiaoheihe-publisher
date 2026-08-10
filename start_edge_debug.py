# -*- coding: utf-8 -*-
"""以调试模式启动 Edge（CDP 端口 9222），支持指定 user-data-dir 并轮询端口。"""
import socket
import subprocess
import sys
import time

from config import EDGE, CDP_PORT

PORT = CDP_PORT
USER_DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else None


def port_open(port, timeout=2):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    # 仅清理使用调试 profile（edge_auto）的 Edge，不影响用户日常 Edge
    ps = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
         "Where-Object { $_.CommandLine -match 'edge_auto' } | "
         "ForEach-Object { $_.ProcessId }"],
        capture_output=True, text=True, timeout=20,
    )
    pids = [int(x.strip()) for x in ps.stdout.split() if x.strip().isdigit()]
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    time.sleep(2)

    cmd = [EDGE, f"--remote-debugging-port={PORT}"]
    if USER_DATA_DIR:
        cmd.append(f"--user-data-dir={USER_DATA_DIR}")

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    proc = subprocess.Popen(
        cmd,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Edge 已启动 (PID {proc.pid}) user-data-dir={USER_DATA_DIR}，等待 CDP 端口 {PORT} ...")

    for i in range(20):
        time.sleep(1)
        if port_open(PORT):
            print(f"[OK] 端口 {PORT} 已就绪（{i + 1} 秒）")
            return 0
    print(f"[失败] 端口 {PORT} 在 20 秒内未就绪")
    return 1


if __name__ == "__main__":
    sys.exit(main())
