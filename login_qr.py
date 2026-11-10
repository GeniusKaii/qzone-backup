# -*- coding: utf-8 -*-
"""打开独立调试浏览器，等待用户扫码登录 QQ 空间，把登录 Cookie 保存到本地。

为什么要独立实例而不是读已装浏览器的 Cookie：
新版 Edge/Chrome 的 Cookie 采用 App-Bound 加密（v20），密钥绑定浏览器自身进程，
本地 DPAPI 解不开；在默认配置目录上开远程调试端口也被新版安全策略禁止。
因此用最小代价的方案：启动一个带调试端口的干净实例，人工扫码登录一次，
经 Chrome DevTools Protocol 的 Storage.getCookies 拿到登录态。

用法:
    python login_qr.py                      # Cookie 存到 qzone_cookies.json
    python login_qr.py -o my_cookies.json
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time

import requests
import websocket

from common import DEFAULT_COOKIES

DEBUG_PORT = 9222
TIMEOUT = 300  # 扫码等待，秒


def find_browser() -> str:
    """找一个可用的 Chromium 系浏览器可执行文件"""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise SystemExit("未找到 Edge/Chrome，请自行修改 find_browser() 加上你的浏览器路径")


def main() -> int:
    ap = argparse.ArgumentParser(description="扫码登录 QQ 空间并保存 Cookie")
    ap.add_argument("-o", "--out", default=DEFAULT_COOKIES, help="Cookie 保存路径")
    args = ap.parse_args()

    # 独立的临时浏览器配置目录，用完即删
    profile_dir = tempfile.mkdtemp(prefix="qzone_login_")
    browser = find_browser()
    print(f"浏览器: {browser}")
    print("即将弹出登录窗口，请用手机 QQ 扫码登录（最多等 5 分钟）...")

    proc = subprocess.Popen([
        browser,
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--no-first-run",
        "--disable-extensions",
        "--window-size=1000,820",
        "https://i.qq.com/",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ver = None
        for _ in range(30):
            time.sleep(1)
            try:
                ver = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=2).json()
                break
            except Exception:
                continue
        if not ver:
            print("FAIL: 调试端口未启动（端口被占用？可改 DEBUG_PORT）")
            return 1

        ws = websocket.create_connection(ver["webSocketDebuggerUrl"], timeout=30)
        start = time.time()
        got = None
        while time.time() - start < TIMEOUT:
            time.sleep(4)
            try:
                ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == 1:
                        break
                cookies = msg["result"]["cookies"]
                names = {c["name"] for c in cookies if "qq.com" in c["domain"]}
                if "p_skey" in names:
                    got = cookies
                    break
                if {"p_uin", "skey"} & names:
                    print("  部分登录态:", sorted(names), "- 继续等待...")
            except Exception as e:
                print("  轮询异常，重试:", e)
        if not got:
            print("FAIL: 超时未拿到 p_skey")
            return 1

        # 域名越长越具体，靠后覆盖，拿到最完整的 Cookie 集
        jar = {}
        for c in sorted(got, key=lambda x: len(x["domain"]), reverse=True):
            if "qq.com" in c["domain"]:
                jar[c["name"]] = c["value"]
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(jar, f)
        uin = jar.get("uin", jar.get("p_uin", "?"))
        print(f"SUCCESS: 拿到 {len(jar)} 个 Cookie，已保存到 {args.out}")
        print(f"登录账号 uin: {uin}")
        print("⚠️ 该文件即登录凭证，用完请删除，勿提交到任何仓库")
        return 0
    finally:
        proc.terminate()
        shutil.rmtree(profile_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
