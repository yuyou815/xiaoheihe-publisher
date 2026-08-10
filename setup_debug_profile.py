# -*- coding: utf-8 -*-
"""
把用户默认 Edge profile 的登录态（Local State + Network/Cookies）
复制到调试专用 profile，然后以调试模式启动 Edge（CDP 端口 9222）。

原理：Chromium 系浏览器未指定 --user-data-dir 时会禁用 remote debugging，
因此必须用独立 user-data-dir。Cookie 加密密钥位于 Local State（DPAPI，
基于当前 Windows 用户），复制后同一用户下仍可解密，登录态无需重新登录。
"""
import os
import shutil
import socket
import subprocess
import sys
import time

from config import EDGE, PROFILE, CDP_PORT

PORT = CDP_PORT
DST = PROFILE  # 调试专用 profile


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


def copy_login_state():
    src = os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge", "User Data")
    if not os.path.isdir(src):
        print(f"[错误] 未找到默认 profile: {src}")
        return False

    os.makedirs(DST, exist_ok=True)
    # Cookie 位于 profile 子目录（Default）下的 Network 目录
    os.makedirs(os.path.join(DST, "Default", "Network"), exist_ok=True)

    pairs = [
        (os.path.join(src, "Local State"), os.path.join(DST, "Local State")),
        (os.path.join(src, "Default", "Network", "Cookies"), os.path.join(DST, "Default", "Network", "Cookies")),
        (os.path.join(src, "Default", "Network", "Cookies-journal"), os.path.join(DST, "Default", "Network", "Cookies-journal")),
    ]
    for s, d in pairs:
        if os.path.exists(s):
            shutil.copy2(s, d)
            print(f"[复制] {s} -> {d}")
        else:
            print(f"[跳过] 不存在: {s}")
    return True


def kill_edge_debug_profile():
    """仅结束使用调试 profile（edge_auto）的 Edge 进程，不影响用户日常 Edge。"""
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
    if pids:
        print(f"[清理] 已结束调试 profile 的 Edge 进程: {pids}")


def check_default_edge_locked():
    """检测用户日常 Edge 是否在运行（复制其登录态前需要其关闭）。"""
    ps = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\").Count"],
        capture_output=True, text=True, timeout=20,
    )
    n = ps.stdout.strip()
    if n.isdigit() and int(n) > 0:
        print("[提示] 检测到你的 Edge 正在运行。")
        print("       复制默认 profile 登录态需要 Edge 已退出（文件被占用）。")
        print("       请手动关闭 Edge 后重新运行本脚本。")
        return True
    return False


def main():
    # 1. 仅清理调试 profile 的 Edge；复制用户默认 profile 前提示用户手动关闭 Edge
    kill_edge_debug_profile()
    time.sleep(1)
    if check_default_edge_locked():
        return 1

    # 2. 复制登录态到调试 profile
    if not copy_login_state():
        return 1

    # 3. 调试模式启动
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    cmd = [EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={DST}"]
    proc = subprocess.Popen(
        cmd,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Edge 已启动 (PID {proc.pid})，调试 profile: {DST}")

    # 4. 轮询等待端口
    for i in range(20):
        time.sleep(1)
        if port_open(PORT):
            print(f"[OK] CDP 端口 {PORT} 已就绪（{i + 1} 秒）")
            return 0
    print(f"[失败] 端口 {PORT} 在 20 秒内未就绪")
    return 1


if __name__ == "__main__":
    sys.exit(main())
