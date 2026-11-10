# -*- coding: utf-8 -*-
"""拉取 QQ 空间全部说说（含评论），存为 backups/<QQ号>/shuoshuo_raw.json

接口: taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6（JSONP）
注意: 返回结尾多一个分号（");"），必须用 rfind(")") 剥壳。

用法:
    python fetch_shuoshuo.py
    python fetch_shuoshuo.py -c my_cookies.json -o backups
"""
import argparse
import json
import os
import time

from common import DEFAULT_BACKUP_ROOT, DEFAULT_COOKIES, g_tk, load_cookies, make_session, output_dir

API = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"


def fetch_page(s, uin, gtk, pos, num=20):
    r = s.get(API, params={
        "uin": uin, "ftype": 0, "sort": 0, "pos": pos, "num": num,
        "replynum": 100, "g_tk": gtk, "callback": "_preloadCallback",
        "code_version": 1, "format": "jsonp", "need_private_comment": 1,
    }, timeout=30)
    text = r.text
    if text.startswith("_preloadCallback("):
        # 注意结尾是 ");"，用 rfind 而不是 [:-1]
        text = text[len("_preloadCallback("):text.rfind(")")]
    return json.loads(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--cookies", default=DEFAULT_COOKIES)
    ap.add_argument("-o", "--out", default=DEFAULT_BACKUP_ROOT, help="备份根目录")
    args = ap.parse_args()

    jar = load_cookies(args.cookies)
    uin = jar["uin"].lstrip("o0")
    out_dir = output_dir(args.out, jar)
    gtk = g_tk(jar["p_skey"])
    s = make_session(jar, f"https://user.qzone.qq.com/{uin}/mood")

    first = fetch_page(s, uin, gtk, 0)
    if first.get("code") != 0:
        print("FAIL: 接口返回 code =", first.get("code"), "| message:", first.get("message"))
        return 1
    total = first.get("total", 0)
    print(f"说说总数: {total}")

    all_msgs = list(first.get("msglist", []))
    pos = len(all_msgs)
    while pos < total:
        time.sleep(1.2)
        try:
            page = fetch_page(s, uin, gtk, pos)
        except Exception as e:
            print(f"  pos={pos} 请求异常: {e}，10秒后重试")
            time.sleep(10)
            continue
        if page.get("code") != 0:
            print(f"  pos={pos} code={page.get('code')} {page.get('message')}，10秒后重试")
            time.sleep(10)
            continue
        msgs = page.get("msglist", [])
        all_msgs.extend(msgs)
        print(f"  已拉取 {len(all_msgs)}/{total}")
        if not msgs:
            break
        pos += len(msgs)

    path = os.path.join(out_dir, "shuoshuo_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"uin": uin, "total": total, "fetched": len(all_msgs), "msglist": all_msgs},
                  f, ensure_ascii=False, indent=1)
    print(f"DONE: 共 {len(all_msgs)} 条说说（含评论）→ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
