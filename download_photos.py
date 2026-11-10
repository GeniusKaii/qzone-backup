# -*- coding: utf-8 -*-
"""按清单批量下载相册照片（多线程、重试、按实际 Content-Type 校正扩展名）

清单 _photo_manifest.json 由 make_board_albums_md.py 生成。

用法:
    python download_photos.py backups/123456789
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
WORKERS = 6
EXT_MAP = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}


def fetch(item: dict) -> str:
    path = item["path"]
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return "skip"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = item["url"]
    if not url:
        return "nourl"
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image") and r.content:
                ct = r.headers.get("Content-Type", "").split(";")[0].strip()
                p = path
                want = EXT_MAP.get(ct, "jpg")
                if not p.lower().endswith(want):
                    p = os.path.splitext(path)[0] + "." + want
                with open(p, "wb") as f:
                    f.write(r.content)
                return "ok"
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "fail"


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python download_photos.py <备份目录>（含 _photo_manifest.json）")
        return 1
    backup_dir = sys.argv[1]
    manifest_path = os.path.join(backup_dir, "_photo_manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"清单共 {len(manifest)} 张")

    done = {"ok": 0, "skip": 0, "fail": 0, "nourl": 0}
    failed = []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fetch, it): it for it in manifest}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            done[res] += 1
            if res == "fail":
                failed.append(futs[fut])
            if i % 100 == 0 or i == len(manifest):
                print(f"  {i}/{len(manifest)}  ok={done['ok']} skip={done['skip']} fail={done['fail']}")

    # 失败重试一轮（单线程，间隔长些）
    if failed:
        print(f"对 {len(failed)} 张失败照片重试...")
        for it in failed:
            time.sleep(1.5)
            res = fetch(it)
            if res != "fail":
                done[res] += 1
                done["fail"] -= 1
            else:
                print("  最终失败:", it["path"])

    print(f"DONE: 成功 {done['ok']} 跳过 {done['skip']} 无URL {done['nourl']} 失败 {done['fail']}")
    return 0 if done["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
