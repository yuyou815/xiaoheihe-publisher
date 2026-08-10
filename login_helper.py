# -*- coding: utf-8 -*-
"""
小黑盒登录引导：打开首页 -> 点击右上角『登录』 -> 弹出二维码 -> 等待用户扫码。
检测到登录成功后，保持浏览器打开（登录态保存在调试 profile，供发布复用）。

用法: python login_helper.py
"""
import asyncio
import sys

from playwright.async_api import async_playwright

from config import EDGE, PROFILE


async def main():
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

        # 1. 打开首页
        await page.goto("https://xiaoheihe.cn", timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)
        print(f"[首页] title={await page.title()!r}")

        # 2. 找右上角『登录』按钮并点击（优先匹配 header/顶部区域，fallback 全局）
        login_btn = None
        for sel in ("text=登录", "text=Log in", "text=登录/注册"):
            try:
                el = await page.query_selector(sel)
                if el:
                    login_btn = el
                    break
            except Exception:
                continue
        if login_btn:
            try:
                await login_btn.click(timeout=5000)
                print("[点击] 已点击『登录』按钮")
            except Exception as e:
                print(f"[点击失败] {e}")
        else:
            print("[提示] 未找到『登录』按钮，请在浏览器中手动点击右上角登录。")

        # 3. 等待二维码弹出（模态框 / 新页面）
        await page.wait_for_timeout(6000)
        qr = await page.evaluate(
            "() => Array.from(document.querySelectorAll('img, canvas')).map(e => e.tagName + ':' + (e.alt||e.className||'').toString().slice(0,40)).slice(0,10)"
        )
        print(f"[二维码区域] {qr}")
        print("=" * 50)
        print("  请在浏览器弹出的窗口中用小黑盒 App 扫码登录")
        print("  脚本每 5 秒检测一次登录状态，成功后自动继续")
        print("=" * 50)

        # 4. 轮询等待登录：以会话类 cookie 增加为准（按钮消失不可靠，弹窗会遮挡）
        async def session_count():
            cookies = await ctx.cookies()
            heihe = [c for c in cookies if "xiaoheihe" in c.get("domain", "")]
            return len([c for c in heihe if any(
                k in c["name"].lower() for k in ("session", "token", "auth", "sid", "uid"))])

        s0 = await session_count()
        print(f"[登录前] 会话类 cookie: {s0} 个")

        logged_in = False
        for i in range(120):  # 最多 10 分钟
            await page.wait_for_timeout(5000)
            s = await session_count()
            if s > s0:
                logged_in = True
                print(f"[OK] 检测到登录成功 (会话 cookie {s0}->{s})")
                break
            if i % 12 == 0:
                print(f"  ...等待扫码中 ({i * 5}s)")

        if logged_in:
            # 不刷新页面（避免干扰），直接确认登录态已保存
            print("[完成] 登录态已保存到调试 profile，可运行 python publish_to_xiaoheihe.py 发布文章")
            print("       浏览器保持打开 30 分钟，期间可手动操作。")
            await asyncio.sleep(1800)
        else:
            print("[超时] 10 分钟内未检测到登录，脚本结束。")
        await ctx.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
