# -*- coding: utf-8 -*-
"""
小黑盒发布服务管理器：通过 Windows 任务计划程序启动独立进程，
不受对话/终端生命周期影响，日志写入 server.log。

用法:
    python manage_server.py start [--new]   启动服务（--new 新建草稿，默认打开草稿箱草稿）
    python manage_server.py stop            停止服务（连同调试 profile 的 Edge，不影响日常 Edge）
    python manage_server.py status          查看服务状态与最近日志
"""
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
LOG = ROOT / "server.log"
ERR = ROOT / "server_err.log"
BAT = ROOT / "start_server.bat"
TASK_NAME = "XiaoheihePubServer"
PROFILE_TAG = "edge_auto"  # 调试 profile 标识，用于精确定位 Edge 进程


def run(cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def find_server():
    """查找运行中的 publish_server 进程 PID。"""
    ps = run(["powershell", "-NoProfile", "-Command",
              "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
              "Where-Object { $_.CommandLine -match 'publish_server' } | "
              "ForEach-Object { $_.ProcessId }"])
    return [int(x.strip()) for x in ps.stdout.split() if x.strip().isdigit()]


def kill_edge_debug_profile():
    """仅结束使用调试 profile 的 Edge 进程，绝不触碰用户日常 Edge。"""
    ps = run(["powershell", "-NoProfile", "-Command",
              "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
              f"Where-Object {{ $_.CommandLine -match '{PROFILE_TAG}' }} | "
              "ForEach-Object { $_.ProcessId }"])
    pids = [int(x.strip()) for x in ps.stdout.split() if x.strip().isdigit()]
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    if pids:
        print(f"[清理] 已结束调试 profile 的 Edge 进程: {pids}")


def write_bat(new=False):
    args = " --new" if new else ""
    content = (
        "@echo off\r\n"
        f'cd /d "{ROOT}"\r\n'
        f'python -u publish_server.py{args} > "{LOG}" 2> "{ERR}"\r\n'
    )
    BAT.write_text(content, encoding="gbk", errors="replace")
    print(f"[准备] 已生成启动脚本 {BAT}")


def start(new=False):
    if find_server():
        print("[提示] 服务已在运行，先 stop 再 start")
        return 1
    write_bat(new)
    # 注册一次性任务并立即运行（系统级启动，脱离终端生命周期）
    tr = f"cmd /c {BAT}"
    r1 = run(["schtasks", "/Create", "/TN", TASK_NAME,
              "/TR", tr, "/SC", "ONCE", "/ST", "00:00", "/F"])
    r2 = run(["schtasks", "/Run", "/TN", TASK_NAME])
    if r1.returncode != 0 or r2.returncode != 0:
        print(f"[启动失败] Create: {r1.stdout} {r1.stderr}\nRun: {r2.stdout} {r2.stderr}")
        return 1
    print("[启动] 服务已通过任务计划程序启动（独立进程）")
    time.sleep(3)
    print(f"[日志] {LOG}")
    return 0


def stop():
    run(["schtasks", "/End", "/TN", TASK_NAME])
    time.sleep(1)
    pids = find_server()
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print(f"[停止] 已结束服务进程 PID {pid}")
    if not pids:
        print("[停止] 服务进程已结束")
    time.sleep(1)
    # 仅关闭调试 profile 的 Edge，不影响用户日常 Edge
    kill_edge_debug_profile()
    return 0


def status():
    pids = find_server()
    print(f"[状态] 服务进程: {pids if pids else '未运行'}")
    if LOG.exists():
        text = LOG.read_text(encoding="utf-8", errors="replace")
        print("--- server.log 末尾 ---")
        print("\n".join(text.splitlines()[-14:]))
    if ERR.exists() and ERR.stat().st_size:
        print("--- server_err.log 末尾 ---")
        print(ERR.read_text(encoding="utf-8", errors="replace").splitlines()[-5:])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        sys.exit(start("--new" in sys.argv[2:]))
    elif cmd == "stop":
        sys.exit(stop())
    else:
        status()
