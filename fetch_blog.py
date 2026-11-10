# -*- coding: utf-8 -*-
"""拉取 QQ 空间日志全量备份：列表 → 正文 → 评论，存为 backups/<QQ号>/blog_raw.json

三个接口（均挂在 user.qzone.qq.com 的代理路径下）:
  列表   blognew/get_abs          JSONP，totalNum 为总数
  正文   blognew/blog_output_data  返回 GB2312 编码的旧版详情页 HTML，
                                  正文在 blogDetailDiv 标记之后；
                                  必须带 styledm/imgdm/bdm/mode/timestamp 等
                                  参数，否则报 param error
  评论   blognew/get_comment_list  topicId = "{uin}_{blogId}"，
                                  poster 是嵌套 dict，replies 为楼中楼

用法:
    python fetch_blog.py
    python fetch_blog.py -c my_cookies.json -o backups
"""
import argparse
import json
import os
import time

from common import DEFAULT_BACKUP_ROOT, DEFAULT_COOKIES, g_tk, load_cookies, make_session, output_dir, parse_jsonp

PROXY = "https://user.qzone.qq.com/proxy/domain/b.qzone.qq.com/cgi-bin/blognew/"
BLOG_LIST_PAGE = "https://qzs.qq.com/qzone/app/blog/v6/bloglist.html"


def is_tran(item: dict) -> bool:
    """判断是否纯转载日志（tranFlag 等字段，或标题带'转载'前缀）"""
    for k in ("tranFlag", "tranblog", "isTran"):
        if item.get(k):
            return True
    title = (item.get("title") or "").lstrip()
    return title.startswith(("转载：", "转：", "[转载]", "【转载】", "转载-"))


def extract_content_html(page_html: str) -> str:
    """从详情页 HTML 里截出正文容器"""
    i = page_html.find("blogDetailDiv")
    if i < 0:
        return ""
    j = page_html.find("<script", i)
    if j < 0:
        j = page_html.find("</div></div></div>", i)
    return page_html[i:j] if j > i else page_html[i:i + 200000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--cookies", default=DEFAULT_COOKIES)
    ap.add_argument("-o", "--out", default=DEFAULT_BACKUP_ROOT, help="备份根目录")
    args = ap.parse_args()

    jar = load_cookies(args.cookies)
    uin = jar["uin"].lstrip("o0")
    out_dir = output_dir(args.out, jar)
    gtk = g_tk(jar["p_skey"])
    s = make_session(jar, BLOG_LIST_PAGE)

    # ===== 1. 日志列表 =====
    r = s.get(PROXY + "get_abs", params={
        "hostUin": uin, "uin": uin, "blogType": 0, "reqInfo": 1, "pos": 0,
        "num": 20, "sortType": 0, "ref": "qzone", "inCharset": "utf-8",
        "outCharset": "utf-8", "g_tk": gtk, "callback": "_Callback"}, timeout=30)
    d = parse_jsonp(r.text)
    if d.get("code") != 0:
        print("FAIL: 列表 code =", d.get("code"), d.get("message"))
        return 1
    total = d["data"]["totalNum"]
    lst = list(d["data"]["list"])
    print(f"日志总数: {total}")
    while len(lst) < total:
        time.sleep(1.0)
        page = parse_jsonp(s.get(PROXY + "get_abs", params={
            "hostUin": uin, "uin": uin, "blogType": 0, "reqInfo": 1, "pos": len(lst),
            "num": 20, "sortType": 0, "ref": "qzone", "inCharset": "utf-8",
            "outCharset": "utf-8", "g_tk": gtk, "callback": "_Callback"}, timeout=30).text)
        if page.get("code") != 0 or not page.get("data", {}).get("list"):
            print(f"  pos={len(lst)} 异常，重试")
            time.sleep(5)
            continue
        lst.extend(page["data"]["list"])
        if len(lst) % 100 == 0 or len(lst) >= total:
            print(f"  列表 {len(lst)}/{total}")

    originals = [b for b in lst if not is_tran(b)]
    trans = [b for b in lst if is_tran(b)]
    print(f"原创 {len(originals)} 篇，纯转载 {len(trans)} 篇（排除）")

    # ===== 2. 正文 + 评论 =====
    blogs, failed = [], []
    for i, b in enumerate(originals, 1):
        bid = str(b["blogId"])
        time.sleep(1.0)
        detail_html, comments, ctotal = "", [], 0
        try:
            r = s.get(PROXY + "blog_output_data", params={
                "uin": uin, "blogid": bid, "styledm": "qzonestyle.gtimg.cn",
                "imgdm": "qzs.qq.com", "bdm": "b.qzone.qq.com", "mode": "2",
                "numperpage": "50", "timestamp": int(time.time()), "dprefix": "",
                "inCharset": "gb2312", "outCharset": "gb2312", "ref": "qzone",
                "page": "1", "refererurl": BLOG_LIST_PAGE},
                timeout=30)
            r.encoding = "gb2312"
            if "blogDetailDiv" not in r.text:
                raise RuntimeError("详情页无正文标记(param error?)")
            detail_html = extract_content_html(r.text)
        except Exception as e:
            print(f"  [{i}/{len(originals)}] {bid} 正文失败: {e}")
            failed.append(bid)

        # 评论（列表里 commentNum>0 才拉）
        cnum = int(b.get("commentNum") or 0)
        if cnum > 0:
            start, done_comments = 0, []
            try:
                while start == 0 or len(done_comments) < ctotal:
                    cr = parse_jsonp(s.get(PROXY + "get_comment_list", params={
                        "uin": uin, "num": 50, "topicId": f"{uin}_{bid}", "start": start,
                        "iNotice": 0, "inCharset": "utf-8", "outCharset": "utf-8",
                        "format": "jsonp", "ref": "qzone", "g_tk": gtk}, timeout=30).text)
                    if cr.get("code") != 0:
                        break
                    cd = cr.get("data", {})
                    ctotal = cd.get("total", 0)
                    done_comments.extend(cd.get("comments", []))
                    start += 50
                    if not cd.get("comments"):
                        break
                    time.sleep(0.6)
                comments = done_comments
            except Exception as e:
                print(f"  {bid} 评论失败: {e}")

        blogs.append({
            "blogId": bid, "title": b.get("title", ""), "pubTime": b.get("pubTime", ""),
            "cate": b.get("cate", ""), "commentNum": cnum, "contentHtml": detail_html,
            "comments": comments, "commentTotal": ctotal,
        })
        if i % 10 == 0 or i == len(originals):
            print(f"  进度 {i}/{len(originals)}")

    path = os.path.join(out_dir, "blog_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"uin": uin, "total": total, "original": len(originals),
                   "tran_skipped": len(trans), "failed": failed, "blogs": blogs},
                  f, ensure_ascii=False, indent=1)
    print(f"DONE: {len(blogs)} 篇（失败 {len(failed)}）→ {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
