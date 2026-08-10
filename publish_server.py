# -*- coding: utf-8 -*-
"""
小黑盒发布常驻服务：
    1. 启动系统 Edge（调试 profile），进入小黑盒文章编辑器并填充当前文章内容
    2. 常驻运行：监听 xiaoheihe_article.md 文件变化，变化时在【当前编辑器标签页】
       原地重填标题/正文 —— 不重开浏览器、不新建草稿
    3. 用户确认后在浏览器手动点『发布』；完成后 Ctrl+C / 停任务收尾

用法:
    python -u publish_server.py
"""
import asyncio
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from config import EDGE, PROFILE, ARTICLE_FILE


def parse_md(path: Path):
    """第一行 # 为标题；其余正文保留 markdown 语法（##、-、**、> 引用）。"""
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


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


async def remove_mask(page):
    """移除可能拦截点击的遮罩层（如 #t_mask / .t-mask）。"""
    await page.evaluate("""
        () => {
            document.querySelectorAll('#t_mask, .t-mask, [class*="mask"]').forEach(e => e.remove());
        }
    """)


async def click_text(page, text, timeout=5000):
    await remove_mask(page)
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
    await remove_mask(page)
    editables = await page.query_selector_all("[contenteditable]")
    if len(editables) < 2:
        print(f"[错误] 未找到标题/正文输入框（当前 {len(editables)} 个）url={page.url}")
        return False, False
    title_box, body_box = editables[0], editables[1]

    # 用 insert_text 一次性插入（避免逐字符输入在含英文点号文本上重复插入）
    await title_box.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.insert_text(title)
    await body_box.click()
    await page.keyboard.press("Control+a")
    await page.keyboard.insert_text(body)
    return True, True


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", action="store_true",
                    help="新建草稿（默认打开草稿箱最新草稿）")
    args = ap.parse_args()

    title0, body0 = parse_md(ARTICLE_FILE)
    h0 = file_hash(ARTICLE_FILE)
    print(f"[文章] 标题: {title0}")
    print(f"[文章] 正文长度: {len(body0)}")

    async with async_playwright() as p:
        print("[启动] 启动系统 Edge（调试 profile）...")
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            executable_path=EDGE,
            headless=False,
            viewport=None,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # 进入编辑器：--new 时新建草稿；否则优先打开草稿箱中已保存的草稿
        await page.goto("https://xiaoheihe.cn", timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)
        if not await click_text(page, "发布内容"):
            print("[错误] 未找到『发布内容』按钮，可能未登录。请先运行 python login_helper.py")
            await ctx.close()
            return
        await page.wait_for_timeout(6000)

        opened_draft = False
        if not args.new and await click_text(page, "草稿箱"):
            # 等待草稿列表渲染（article 条目出现）
            try:
                await page.wait_for_selector("article", timeout=12000)
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[草稿列表等待失败] {e}")
            # 点击第一个草稿条目（article 元素）
            draft_item = await page.query_selector("article")
            if draft_item:
                try:
                    await draft_item.click(timeout=6000)
                    opened_draft = True
                    print("[草稿箱] 已打开最新草稿")
                except Exception as e:
                    print(f"[草稿箱点击失败] {e}")
            else:
                print("[草稿箱] 未找到草稿条目")
            await page.wait_for_timeout(8000)

        if not opened_draft:
            await click_text(page, "发布文章")
            await page.wait_for_timeout(3000)
        print(f"[编辑器] {page.url}")

        ok_t, ok_b = await fill_editor(page, title0, body0)
        print("=" * 50)
        print(f"[初次填充] 标题: {'[OK]' if ok_t else '[FAIL]'}  正文: {'[OK]' if ok_b else '[FAIL]'}")
        print("[服务运行] 我修改文章文件后，这里会自动原地更新，浏览器不会重开")
        print("[提示] 请在浏览器中检查内容，确认无误后手动点击『发布』")
        print("=" * 50)

        # 常驻循环：监听文章文件变化 -> 原地重填
        while True:
            await asyncio.sleep(2)
            try:
                h = file_hash(ARTICLE_FILE)
            except OSError:
                continue
            if h != h0:
                h0 = h
                title, body = parse_md(ARTICLE_FILE)
                print(f"[检测] 文章文件已变化，原地重填... 标题={title}")
                # 确保停在编辑器标签页（如果用户切走，切回来）
                editor_pages = [pg for pg in ctx.pages if "/creator/editor/" in pg.url]
                target = editor_pages[-1] if editor_pages else page
                try:
                    await target.bring_to_front()
                    await target.wait_for_timeout(1000)
                    ok_t, ok_b = await fill_editor(target, title, body)
                    print(f"[重填] 标题: {'[OK]' if ok_t else '[FAIL]'}  正文: {'[OK]' if ok_b else '[FAIL]'}")
                except Exception as e:
                    print(f"[重填失败] {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[结束] 服务已停止。")
