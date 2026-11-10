# -*- coding: utf-8 -*-
"""生成留言板与相册 Markdown；相册引用本地图片相对路径，并输出下载清单 _photo_manifest.json

用法:
    python make_board_albums_md.py backups/123456789
"""
import json
import os
import re
import sys
import time


def sanitize(s, maxlen=60):
    s = re.sub(r'[\\/:*?"<>|\r\n]+', "_", (s or "").strip())
    return s[:maxlen] or "未命名"


def ts(unix):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(unix)))
    except Exception:
        return ""


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python make_board_albums_md.py <备份目录>（含 board_raw.json / albums_raw.json）")
        return 1
    backup_dir = sys.argv[1]

    # ============ 留言板 ============
    board_path = os.path.join(backup_dir, "board_raw.json")
    if os.path.exists(board_path):
        d = json.load(open(board_path, encoding="utf-8"))
        msgs = sorted(d["commentList"], key=lambda m: m.get("pubtime") or "")
        lines = [
            "# QQ空间留言板备份", "",
            f"- **账号**：{d['uin']}",
            f"- **备份时间**：{time.strftime('%Y-%m-%d %H:%M')}",
            f"- **留言总数**：{len(msgs)} 条（含好友回复 {sum(len(m.get('replyList') or []) for m in msgs)} 条）",
            "",
        ]
        for n, m in enumerate(msgs, 1):
            secret = " 🔒私密" if m.get("secret") in (1, "1") else ""
            lines += [
                f"## #{n:03d}　**{m.get('nickname') or m.get('uin')}**（{m.get('pubtime', '')}）{secret}", "",
                (m.get("ubbContent") or m.get("htmlContent") or "（无内容）").strip(), "",
            ]
            for r in m.get("replyList") or []:
                lines.append(f"- **{r.get('nick') or r.get('uin')}**（{ts(r.get('time'))}）：{(r.get('content') or '').strip()}")
            lines += ["---", ""]
        out = os.path.join(backup_dir, "留言备份")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "留言板.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"留言板 Markdown 完成：{len(msgs)} 条")

    # ============ 相册 ============
    albums_path = os.path.join(backup_dir, "albums_raw.json")
    if not os.path.exists(albums_path):
        print("未找到 albums_raw.json，跳过相册")
        return 0
    a = json.load(open(albums_path, encoding="utf-8"))
    albums = sorted(a["albums"], key=lambda x: int(x.get("createtime") or 0))

    alb_dir = os.path.join(backup_dir, "相册备份")
    dl_dir = os.path.join(alb_dir, "相册下载")
    os.makedirs(dl_dir, exist_ok=True)

    # 目录名去重
    dir_names, used = {}, set()
    for al in albums:
        nm = sanitize(al.get("name"))
        base_nm, k = nm, 2
        while nm in used:
            nm = f"{base_nm}_{k}"
            k += 1
        used.add(nm)
        dir_names[al["id"]] = nm

    index = [
        "# QQ空间相册备份", "",
        f"- **账号**：{a['uin']}",
        f"- **备份时间**：{time.strftime('%Y-%m-%d %H:%M')}",
        f"- **相册数**：{len(albums)} 个，照片 {sum(len(a['photos'].get(al['id'], [])) for al in albums)} 张"
        "（原图已下载到 相册下载/ 目录）", "",
        "| 相册 | 照片数 | 创建时间 | 文件 |", "|---|---|---|---|",
    ]
    manifest = []
    for al in albums:
        aid = al["id"]
        nm = dir_names[aid]
        index.append(f"| {al.get('name')} | {len(a['photos'].get(aid, []))} | {ts(al.get('createtime'))} "
                     f"| [相册_{nm}.md](相册_{nm}.md) |")

        fname = f"相册_{nm}.md"
        pics = a["photos"].get(aid, [])
        out = [f"# {al.get('name')}（{len(pics)} 张）", ""]
        if (al.get("desc") or "").strip():
            out += [al["desc"].strip(), ""]
        out += [f"创建：{ts(al.get('createtime'))} ｜ 最后上传：{ts(al.get('lastuploadtime'))}", ""]
        for i, p in enumerate(pics, 1):
            ext = "jpg"  # 下载器会按实际 Content-Type 校正扩展名
            local = os.path.join("相册下载", nm, f"{i:04d}_{sanitize(p.get('name'))}.{ext}")
            rel = local.replace("\\", "/")
            out.append(f"### {i:04d}　{p.get('name') or '未命名'}")
            meta = []
            if p.get("uploadtime"):
                meta.append("上传：" + ts(p["uploadtime"]))
            if p.get("shoottime"):
                meta.append("拍摄：" + ts(p["shoottime"]))
            if meta:
                out.append("　｜　".join(meta))
            if (p.get("desc") or "").strip():
                out += ["", p["desc"].strip()]
            out += ["", f"![{p.get('name') or i}]({rel})", "", "---", ""]
            manifest.append({
                "url": p.get("url") or p.get("pre"),
                "path": os.path.join(dl_dir, nm, f"{i:04d}_{sanitize(p.get('name'))}.{ext}"),
                "name": p.get("name") or "",
            })
        with open(os.path.join(alb_dir, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(out))

    with open(os.path.join(alb_dir, "00_总目录.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print(f"相册 Markdown 完成：{len(albums)} 个相册文件")

    with open(os.path.join(backup_dir, "_photo_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"下载清单：{len(manifest)} 张 → _photo_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
