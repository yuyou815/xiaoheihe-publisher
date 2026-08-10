# -*- coding: utf-8 -*-
"""将项目文件打包为 zip（排除 .git/.reasonix/__pycache__）。"""
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
OUT = ROOT / "xiaoheihe-publisher.zip"
EXCLUDE_DIRS = {".git", ".reasonix", "__pycache__"}

FILES = [
    "LICENSE",
    "README.md",
    "config.py",
    "login_helper.py",
    "publish_server.py",
    "publish_to_xiaoheihe.py",
    "setup_debug_profile.py",
    "start_edge_debug.py",
]


def main():
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            p = ROOT / name
            if p.exists():
                zf.write(p, arcname=name)
                print(f"[打包] {name}")
            else:
                print(f"[跳过] {name} 不存在")
    print(f"[完成] {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
