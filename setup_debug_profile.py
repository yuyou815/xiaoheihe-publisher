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


def main():
    # 1. 关闭所有 Edge（锁文件问题 + 确保调试参数生效）
    subprocess.run(["taskkill", "/IM", "msedge.exe", "/F"], capture_output=True)
    time.sleep(2)

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
