# -*- coding: utf-8 -*-
"""拉取 QQ 空间留言板 + 相册元数据，存为 backups/<QQ号>/board_raw.json 和 albums_raw.json

两个坑（实测）:
  留言板 get_msgb: 数据在 data.commentList（不是 msgList），
                   且单次请求最多返回 6 条，start 必须按实际返回数推进
  相册:            fcg_list_album_v3 的相册 ID 字段叫 id（不是 albumId）；
                   照片列表接口 cgi_list_photo 的 topicId 传相册 id

用法:
    python fetch_board_albums.py
    python fetch_board_albums.py -c my_cookies.json -o backups
"""
import argparse
import json
import os
import random
import time

from common import DEFAULT_BACKUP_ROOT, DEFAULT_COOKIES, g_tk, load_cookies, make_session, output_dir, parse_jsonp


def photo_ts() -> str:
    """照片接口要求的伪随机时间戳参数"""
    return str(round(random.random(), 16)).split(".").pop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--cookies", default=DEFAULT_COOKIES)
    ap.add_argument("-o", "--out", default=DEFAULT_BACKUP_ROOT, help="备份根目录")
    args = ap.parse_args()

    jar = load_cookies(args.cookies)
    uin = jar["uin"].lstrip("o0")
    out_dir = output_dir(args.out, jar)
    gtk = g_tk(jar["p_skey"])
    s = make_session(jar, f"https://user.qzone.qq.com/{uin}/311")

    # ===== 留言板 =====
    board, total = [], 0
    start = 0
    while True:
        r = s.get("https://user.qzone.qq.com/proxy/domain/m.qzone.qq.com/cgi-bin/new/get_msgb", params={
            "uin": uin, "hostUin": uin, "start": start, "s": random.random(),
            "format": "jsonp", "num": 30, "inCharset": "utf-8", "outCharset": "utf-8",
            "g_tk": gtk, "callback": "_Callback"}, timeout=30)
        d = parse_jsonp(r.text)
        if d.get("code") != 0:
            print("留言板 code =", d.get("code"), d.get("message", ""))
            break
        data = d.get("data", {})
        total = data.get("total", 0)
        msgs = data.get("commentList", [])
        board.extend(msgs)
        print(f"留言板 {len(board)}/{total}")
        if not msgs or len(board) >= total:
            break
        start += len(msgs)  # 单次最多返回6条，按实际返回数推进
        time.sleep(1.0)
    path = os.path.join(out_dir, "board_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"uin": uin, "total": total, "commentList": board}, f, ensure_ascii=False, indent=1)
    print(f"留言板 DONE: {len(board)} 条 → {path}")

    # ===== 相册清单 =====
    albums, page_start = [], 0
    while True:
        r = s.get("https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3", params={
            "g_tk": gtk, "callback": "shine0_Callback", "t": photo_ts(),
            "hostUin": uin, "uin": uin, "appid": 4, "inCharset": "utf-8", "outCharset": "utf-8",
            "source": "qzone", "plat": "qzone", "format": "jsonp", "notice": 0, "filter": 1,
            "handset": 4, "needUserInfo": 1, "idcNum": 102, "mode": 2, "sortOrder": "2",
            "pageStart": page_start, "pageNum": 100, "callbackFun": "shine0",
            "_": int(time.time() * 1000),
        }, timeout=30)
        d = parse_jsonp(r.text)
        if d.get("code") != 0:
            print("相册清单 code =", d.get("code"), d.get("message", ""))
            break
        al = d.get("data", {}).get("albumList", [])
        albums.extend(al)
        if not al or len(albums) >= d.get("data", {}).get("total", len(albums)):
            break
        page_start += 100
        time.sleep(1.0)
    print(f"相册数: {len(albums)}")

    # ===== 各相册照片 =====
    all_photos = {}
    for i, a in enumerate(albums, 1):
        aid = str(a.get("id") or a.get("albumId"))
        pics, ps = [], 0
        while True:
            time.sleep(0.8)
            try:
                r = s.get("https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/cgi_list_photo", params={
                    "g_tk": gtk, "callback": "shine0_Callback", "t": photo_ts(), "mode": 0,
                    "idcNum": 102, "hostUin": uin, "topicId": aid, "noTopic": 0, "uin": uin,
                    "pageStart": ps, "pageNum": 100, "skipCmtCount": 0, "singleurl": 1,
                    "batchId": "", "notice": 0, "appid": 4, "inCharset": "utf-8",
                    "outCharset": "utf-8", "source": "qzone", "plat": "qzone",
                    "outstyle": "json", "format": "jsonp", "json_esc": 1,
                    "callbackFun": "shine0", "_": int(time.time() * 1000),
                }, timeout=30)
                d = parse_jsonp(r.text)
            except Exception as e:
                print(f"  相册[{i}] {aid} 异常: {e}，重试")
                time.sleep(8)
                continue
            if d.get("code") != 0:
                print(f"  相册[{i}] {aid} code={d.get('code')}")
                break
            pl = d.get("data", {}).get("photoList", [])
            pics.extend(pl)
            total_ph = d.get("data", {}).get("totalInAlbum", d.get("data", {}).get("total", 0))
            if not pl or len(pics) >= total_ph:
                break
            ps += 100
        all_photos[aid] = pics
        print(f"  [{i}/{len(albums)}] {a.get('name', '?')}：{len(pics)} 张")

    path = os.path.join(out_dir, "albums_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"uin": uin, "albums": albums, "photos": all_photos}, f, ensure_ascii=False, indent=1)
    total_photos = sum(len(v) for v in all_photos.values())
    print(f"DONE: {len(albums)} 个相册 / {total_photos} 张照片元数据 → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
