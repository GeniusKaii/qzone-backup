# -*- coding: utf-8 -*-
"""公共工具：Cookie 加载、g_tk 计算、JSONP 解析、会话构造"""
import json
import os

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")

DEFAULT_COOKIES = "qzone_cookies.json"
DEFAULT_BACKUP_ROOT = "backups"


def load_cookies(path: str) -> dict:
    """加载 qr_login.py 保存的登录 Cookie JSON"""
    with open(path, encoding="utf-8") as f:
        jar = json.load(f)
    if "p_skey" not in jar:
        raise SystemExit(f"{path} 里没有 p_skey，登录态无效，请重新运行 login_qr.py")
    return jar


def g_tk(p_skey: str) -> int:
    """QQ 空间接口的 g_tk 校验值，由 p_skey 哈希得到"""
    h = 5381
    for ch in p_skey:
        h = h + (h << 5) + ord(ch)
        h &= 0x7FFFFFFF
    return h


def parse_jsonp(text: str):
    """把 JSONP 响应（func(...)）剥壳成 dict"""
    return json.loads(text[text.find("(") + 1:text.rfind(")")])


def make_session(jar: dict, referer: str) -> requests.Session:
    """带登录态的请求会话"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": referer,
        "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()),
    })
    return s


def output_dir(backup_root: str, jar: dict) -> str:
    """按 QQ 号创建并返回输出目录（uin 去掉 o0 前缀）"""
    uin = jar["uin"].lstrip("o0")
    out = os.path.join(backup_root, uin)
    os.makedirs(out, exist_ok=True)
    return out
