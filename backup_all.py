# -*- coding: utf-8 -*-
"""一键流水线：拉取说说/日志/留言板/相册 → 生成 Markdown → 下载照片

需要先运行 login_qr.py 拿到登录 Cookie。

用法:
    python backup_all.py
    python backup_all.py --cookies my_cookies.json --out backups
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ("拉取说说", ["fetch_shuoshuo.py"]),
    ("拉取日志", ["fetch_blog.py"]),
    ("拉取留言板和相册元数据", ["fetch_board_albums.py"]),
]


def run(cmd):
    print(f"\n>>> {' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))}")
    r = subprocess.run([sys.executable] + cmd, cwd=HERE)
    if r.returncode != 0:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--cookies", default="qzone_cookies.json")
    ap.add_argument("-o", "--out", default="backups", help="备份根目录")
    ap.add_argument("--skip-fetch", action="store_true", help="跳过拉取，只重新生成 Markdown 和下载")
    ap.add_argument("--no-photos", action="store_true", help="跳过照片下载（只留元数据和链接）")
    args = ap.parse_args()

    for label, scripts in STEPS:
        if not args.skip_fetch:
            print(f"\n===== {label} =====")
            if not run(scripts[0] + ["-c", args.cookies, "-o", args.out]):
                print(f"FAIL: {label} 失败，中止")
                return 1

    # 找到本次登录的 QQ 号目录
    import json
    jar = json.load(open(args.cookies, encoding="utf-8"))
    uin = jar["uin"].lstrip("o0")
    backup_dir = os.path.join(args.out, uin)

    print("\n===== 生成 Markdown =====")
    for m in ("make_shuoshuo_md.py", "make_blog_md.py", "make_board_albums_md.py"):
        if not run([m, backup_dir]):
            print(f"FAIL: {m} 失败")
            return 1

    if not args.no_photos and os.path.exists(os.path.join(backup_dir, "_photo_manifest.json")):
        print("\n===== 下载照片 =====")
        run(["download_photos.py", backup_dir])

    print(f"\n✅ 全部完成，输出目录: {os.path.abspath(backup_dir)}")
    print("提醒: 删除 Cookie 文件（" + args.cookies + "）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
