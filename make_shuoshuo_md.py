# -*- coding: utf-8 -*-
"""把 shuoshuo_raw.json 按年份生成为 Markdown（时间正序编号）

用法:
    python make_shuoshuo_md.py backups/123456789
"""
import json
import os
import sys
import time
from collections import defaultdict


def ts(t):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(t)))


def pic_urls(pic_list):
    urls = []
    for p in pic_list or []:
        for k in ("url3", "url2", "url1"):  # 原图 > 大图 > 缩略
            if p.get(k):
                urls.append(p[k])
                break
    return urls


def fmt_reply(r):
    name = r.get("name", "匿名")
    target = r.get("reply_name", "")
    t = r.get("createTime2") or r.get("createTime", "")
    t2 = f"（{t}）" if t else ""
    arrow = f" → **{target}**" if target else ""
    return f"  - **{name}**{arrow}{t2}：{r.get('content', '').strip()}"


def fmt_comment(c):
    name = c.get("name", "匿名")
    t = c.get("createTime2") or (ts(c["create_time"]) if c.get("create_time") else c.get("createTime", ""))
    tag = " 🔒私密" if c.get("private") else ""
    lines = [f"- **{name}**（{t}）{tag}：{c.get('content', '').strip() or '（无文字）'}"]
    for r in c.get("replylist") or []:
        lines.append(fmt_reply(r))
    return lines


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python make_shuoshuo_md.py <备份目录>（含 shuoshuo_raw.json）")
        return 1
    backup_dir = sys.argv[1]
    data = json.load(open(os.path.join(backup_dir, "shuoshuo_raw.json"), encoding="utf-8"))
    msgs = data["msglist"]
    uin = data["uin"]

    out_dir = os.path.join(backup_dir, "说说备份")
    os.makedirs(out_dir, exist_ok=True)

    by_year = defaultdict(list)
    for m in msgs:
        by_year[time.strftime("%Y", time.localtime(m["created_time"]))].append(m)

    year_span = f"{min(by_year)}–{max(by_year)}" if by_year else "-"
    index = [
        "# QQ空间说说备份", "",
        f"- **账号**：{uin}（{msgs[0].get('name', '') if msgs else ''}）",
        f"- **备份时间**：{time.strftime('%Y-%m-%d %H:%M')}",
        f"- **说说总数**：{len(msgs)} 条（{year_span}）",
        f"- **有评论的说说**：{sum(1 for m in msgs if m.get('commentlist'))} 条；"
        f"评论互动共 {sum(m.get('cmtnum', 0) for m in msgs)} 条",
        f"- **带图片的说说**：{sum(1 for m in msgs if m.get('pic'))} 条（图片以链接形式保存）", "",
        "| 年份 | 条数 | 文件 |", "|---|---|---|",
    ]
    for year in sorted(by_year):
        ymsgs = by_year[year]
        fname = f"说说_{year}.md"
        index.append(f"| {year} | {len(ymsgs)} | [{fname}]({fname}) |")

        lines = [f"# {year} 年说说（{len(ymsgs)} 条）", ""]
        seq_start = sum(len(by_year[y]) for y in sorted(by_year) if y < year)  # 全局正序编号
        for i, m in enumerate(sorted(ymsgs, key=lambda x: x["created_time"])):
            no = seq_start + i + 1
            src = f" ｜ 来自 {m['source_name']}" if m.get("source_name") else ""
            lines += [f"## #{no:03d}　{ts(m['created_time'])}{src}", ""]
            content = (m.get("content") or "").strip()
            lines.append(content if content else "（无文字）")
            lines.append("")
            urls = pic_urls(m.get("pic"))
            if urls:
                lines += [f"**📷 图片（{len(urls)} 张）**：", ""]
                lines += [f"{j}. {u}" for j, u in enumerate(urls, 1)]
                lines.append("")
            if m.get("secret"):
                lines += ["*（部分可见/私密说说）*", ""]
            comments = m.get("commentlist") or []
            if comments:
                lines += [f"**💬 评论（{m.get('cmtnum', len(comments))} 条）**：", ""]
                for c in comments:
                    lines.extend(fmt_comment(c))
                lines.append("")
            lines += ["---", ""]
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    with open(os.path.join(out_dir, "00_总目录.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")

    total_comments = sum(len(m.get("commentlist") or []) for m in msgs)
    print(f"完成：{len(by_year)} 个年份文件 + 总目录，共 {len(msgs)} 条说说 / {total_comments} 条评论")
    print("输出目录:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
