# -*- coding: utf-8 -*-
"""把 blog_raw.json 生成为按年份的 Markdown（正文 HTML 转文本，评论含楼中楼）

用法:
    python make_blog_md.py backups/123456789
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from html.parser import HTMLParser


class HtmlToText(HTMLParser):
    """日志正文 HTML → Markdown 文本：图片留链接，换行保留"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if src:
                self.out.append(f"\n![{a.get('alt') or ''}]({src})\n")
        elif tag == "br":
            self.out.append("\n")
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "blockquote"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "blockquote"):
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html2md(raw: str) -> str:
    if not raw:
        return ""
    raw = re.sub(r'^[^>]*blogDetailDiv[^>]*>', '', raw)  # 去掉提取时带入的容器标签头
    p = HtmlToText()
    p.feed(raw)
    text = "".join(p.out)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(l.strip() for l in text.split("\n")).strip()


def fmt_ts(unix):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(unix)))


def poster_name(c):
    p = c.get("poster") or {}
    if isinstance(p, dict):
        return p.get("name") or p.get("id") or "匿名"
    return "匿名"


def fmt_comment(c):
    t = fmt_ts(c["postTime"]) if c.get("postTime") else ""
    lines = [f"- **{poster_name(c)}**（{t}）：{(c.get('content') or '').strip()}"]
    for r in c.get("replies") or []:
        rt = fmt_ts(r["postTime"]) if r.get("postTime") else ""
        lines.append(f"  - **{poster_name(r)}**（{rt}）：{(r.get('content') or '').strip()}")
    return lines


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python make_blog_md.py <备份目录>（含 blog_raw.json）")
        return 1
    backup_dir = sys.argv[1]
    data = json.load(open(os.path.join(backup_dir, "blog_raw.json"), encoding="utf-8"))
    blogs = sorted(data["blogs"], key=lambda b: b.get("pubTime") or "")

    out_dir = os.path.join(backup_dir, "日志备份")
    os.makedirs(out_dir, exist_ok=True)

    by_year = defaultdict(list)
    for n, b in enumerate(blogs, 1):
        by_year[(b.get("pubTime") or "未知")[:4]].append((n, b))

    index = [
        "# QQ空间日志备份", "",
        f"- **账号**：{data['uin']}",
        f"- **备份时间**：{time.strftime('%Y-%m-%d %H:%M')}",
        f"- **日志总数**：{data['total']} 篇，其中原创 {data['original']} 篇、纯转载 {data['tran_skipped']} 篇（已排除）",
        f"- **成功备份**：{len(blogs)} 篇（失败 {len(data.get('failed', []))} 篇）",
        f"- **带评论的日志**：{sum(1 for b in blogs if b.get('comments'))} 篇", "",
        "| 年份 | 篇数 | 文件 |", "|---|---|---|",
    ]
    for year in sorted(by_year):
        fname = f"日志_{year}.md"
        index.append(f"| {year} | {len(by_year[year])} | [{fname}]({fname}) |")

    for year in sorted(by_year):
        fname = f"日志_{year}.md"
        lines = [f"# {year} 年日志（{len(by_year[year])} 篇）", ""]
        for n, b in by_year[year]:
            lines.append(f"## #{n:03d}　{b.get('title') or '（无标题）'}")
            meta = []
            if b.get("pubTime"):
                meta.append(b["pubTime"])
            if b.get("cate"):
                meta.append(f"分类：{b['cate']}")
            if meta:
                lines += ["", "　|　".join(meta)]
            lines.append("")
            body = html2md(b.get("contentHtml") or "")
            lines.append(body if body else "（正文提取失败，可看 blog_raw.json 原始数据）")
            lines.append("")
            comments = b.get("comments") or []
            if comments:
                lines += [f"**💬 评论（{b.get('commentTotal') or len(comments)} 条）**：", ""]
                for c in comments:
                    lines.extend(fmt_comment(c))
                lines.append("")
            lines += ["---", ""]
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    with open(os.path.join(out_dir, "00_总目录.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")

    print(f"完成：{len(by_year)} 个年份文件，共 {len(blogs)} 篇日志")
    print("输出目录:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
