# -*- coding: utf-8 -*-
"""
小黑盒自动发布流程（复用已登录的调试 profile）：
    首页 -> 发布内容 -> 发布文章 -> 填充标题/正文(markdown) -> 停在『发布』按钮前由用户确认。

用法:
    python publish_to_xiaoheihe.py             # 完整流程（浏览器未开时用，启动带调试端口）
    python publish_to_xiaoheihe.py --update    # 原地更新：附加到已打开的浏览器，在当前编辑器
                                               # 标签页重填标题/正文（不重开浏览器、不新建草稿）
"""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from config import EDGE, PROFILE, ARTICLE_FILE, CDP_URL


def parse_md(path: Path):
    """第一行 # 为标题；其余正文保留 markdown 语法（##、-、**）。"""
    if not path.exists():
        print(f"[错误] 未找到文章文件: {path}")
        print("       请先创建（第一行以 # 开头为标题，其余为正文）")
        raise SystemExit(1)
    text = path.read_text(encoding="utf-8").strip()
    lines = text.splitlines()
    title = ""
    while lines and lines[0].startswith("#"):
        title = (title + " " + lines.pop(0)).strip().lstrip("#").strip()
    body = "\n".join(lines).strip()
    return title, body


async def click_text(page, text, timeout=5000):
    el = await page.query_selector(f"text={text}")
    if not el:
        print(f"[未找到] {text}")
        return False
    try:
        await el.click(timeout=timeout)
        return True
    except Exception as e:
        print(f"[点击失败] {text}: {e}")
        return False


async def fill_editor(page, title, body):
    """在当前页面定位标题框/正文框并覆盖填充。返回 (ok_title, ok_body)。"""
    editables = await page.query_selector_all("[contenteditable]")
    if len(editables) < 2:
        print(f"[错误] 未找到标题/正文输入框（当前 {len(editables)} 个）")
        return False, False
    title_box, body_box = editables[0], editables[1]

    await title_box.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.type(title, delay=10)
    print("[标题] 已填入")

    await body_box.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.type(body, delay=3)
    print("[正文] 已填入（markdown 源文本）")
    return True, True


async def run_update(p, title, body):
    """--update 模式：附加到已打开的浏览器，在当前编辑器标签页原地重填。"""
    try:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
    except Exception as e:
        print(f"[错误] 无法附加到已打开的浏览器: {e}")
        print("       确认浏览器是用调试模式启动的（--remote-debugging-port=9222）")
        return

    ctx = browser.contexts[0] if browser.contexts else None
    if not ctx:
        print("[错误] 未找到浏览器上下文")
        return

    # 找当前编辑器标签页（URL 含 /creator/editor/），优先最后一个
    editors = [pg for pg in ctx.pages if "/creator/editor/" in pg.url]
    if not editors:
        print(f"[错误] 未找到编辑器标签页。当前标签页: {[pg.url for pg in ctx.pages]}")
        return
    page = editors[-1]
    print(f"[编辑器] {page.url}")
    await page.bring_to_front()
    await page.wait_for_timeout(1500)

    ok_t, ok_b = await fill_editor(page, title, body)
    print("=" * 50)
    print(f"[结果] 标题: {'[OK]' if ok_t else '[FAIL]'}  正文: {'[OK]' if ok_b else '[FAIL]'}")
    print("[提示] 内容已原地更新，请在浏览器中检查后手动点击『发布』。")
    print("=" * 50)
    # 保持附加连接，直到用户手动发布（30 分钟）
    await asyncio.sleep(1800)


async def run_launch(p, title, body):
    """完整流程：启动浏览器（带调试端口）-> 发布内容 -> 发布文章 -> 填充。"""
    print("[启动] 启动系统 Edge（调试 profile，带 CDP 端口）...")
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=PROFILE,
        executable_path=EDGE,
        headless=False,
        viewport=None,
        args=["--start-maximized", "--remote-debugging-port=9222"],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    # 1. 首页 -> 发布内容
    await page.goto("https://xiaoheihe.cn", timeout=30000, wait_until="domcontentloaded")
    await page.wait_for_timeout(8000)
    if not await click_text(page, "发布内容"):
        print("[错误] 未找到『发布内容』按钮，可能未登录。请先运行 python login_helper.py")
        await ctx.close()
        return
    await page.wait_for_timeout(8000)
    print(f"[编辑器] {page.url}")

    # 2. 确保是『发布文章』模式
    await click_text(page, "发布文章")
    await page.wait_for_timeout(3000)

    # 3-5. 填充
    await fill_editor(page, title, body)

    # 6. 停在『发布』按钮前，由用户确认
    await page.wait_for_timeout(1500)
    has_publish = await page.query_selector("button:has-text('发布')")
    print("=" * 50)
    print(f"[结果] 标题+正文已填入。发布按钮: {'存在' if has_publish else '未找到（请手动查找）'}")
    print("[提示] 请在浏览器中检查内容（如 markdown 未渲染，可点击编辑器内『Markdown』按钮切换）")
    print("[提示] 确认无误后，手动点击『发布』按钮完成发布。")
    print("[提示] 完成后关闭此脚本（Ctrl+C）。")
    print("=" * 50)
    # 保持浏览器与脚本存活，等用户手动发布
    await asyncio.sleep(3600)
    await ctx.close()


async def main():
    args = sys.argv[1:]
    title, body = parse_md(ARTICLE_FILE)
    print(f"[文章] 标题: {title}")
    print(f"[文章] 正文长度: {len(body)}")

    async with async_playwright() as p:
        if "--update" in args:
            await run_update(p, title, body)
        else:
            await run_launch(p, title, body)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[结束] 脚本已停止。")
