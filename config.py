# -*- coding: utf-8 -*-
"""集中配置：路径与端口均可用环境变量覆盖，便于在不同机器上使用。

可用环境变量:
    XIAOHEIHE_EDGE      Edge 可执行文件路径
    XIAOHEIHE_PROFILE   调试专用 profile 目录（登录态存放处）
    XIAOHEIHE_CDP_URL   CDP 调试端口地址（原地更新模式用）
"""
import os
from pathlib import Path

# Edge 可执行文件路径
EDGE = os.environ.get(
    "XIAOHEIHE_EDGE",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)

# 调试专用 profile：复制了用户默认 profile 登录态（cookie）的独立目录
PROFILE = os.environ.get("XIAOHEIHE_PROFILE", r"C:\Users\Public\edge_auto")

# CDP 端口（--update 原地更新模式附加已打开浏览器用）
CDP_PORT = int(os.environ.get("XIAOHEIHE_CDP_PORT", "9222"))
CDP_URL = os.environ.get("XIAOHEIHE_CDP_URL", f"http://127.0.0.1:{CDP_PORT}")

# 文章源文件（第一行 # 为标题，其余为正文，支持 markdown 语法）
ARTICLE_FILE = Path(__file__).parent / "xiaoheihe_article.md"
