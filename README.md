# qzone-backup — QQ空间本地备份工具

把 QQ 空间的**说说、日志、留言板、相册**完整备份到本地：

- 说说 / 日志 / 留言板 → 按年份（或单文件）生成 Markdown，含发送时间、来源设备、评论区互动（含楼中楼回复、私密标记）
- 相册 → 照片原图批量下载到本地 + 每个相册一份 Markdown 目录
- 全程只读，不向 QQ 空间写入任何数据
- 中间产物为原始 JSON（`*_raw.json`），想换任何输出格式都可以从它重新生成

本项目曾在 2026-11 实测备份 3 个账号：约 2100 条说说、515 篇日志、190 条留言、3881 张照片原图，全部零失败。

## 原理

QQ 空间没有官方导出功能。本工具用你扫码登录后的 Cookie（`p_skey` 计算 `g_tk` 校验值），调用 QQ 空间网页版自己的 CGI 接口分页拉取数据：

| 内容 | 接口 |
|---|---|
| 说说 | `taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6` |
| 日志 | `b.qzone.qq.com/cgi-bin/blognew/get_abs` + `blog_output_data` + `get_comment_list` |
| 留言板 | `m.qzone.qq.com/cgi-bin/new/get_msgb` |
| 相册 | `photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3` + `cgi_list_photo` |

**为什么不直接读浏览器里已登录的 Cookie？** 新版 Edge/Chrome 的 Cookie 采用 App-Bound 加密，密钥绑定浏览器自身进程，本地解不开，默认配置目录上也无法开远程调试端口。所以最干净的方式是：启动一个独立调试浏览器实例，**人工扫码登录一次**，经 DevTools Protocol 拿到登录态。登录与备份用的是独立实例，不影响你日常使用的浏览器。

## 使用

```bash
pip install -r requirements.txt

# 1. 扫码登录（弹出浏览器窗口，用手机 QQ 扫码）
python login_qr.py

# 2. 一键备份当前登录账号的全部内容
python backup_all.py

# 或者分步执行
python fetch_shuoshuo.py          # 说说 → backups/<QQ号>/shuoshuo_raw.json
python fetch_blog.py              # 日志 → backups/<QQ号>/blog_raw.json
python fetch_board_albums.py      # 留言板+相册元数据 → backups/<QQ号>/{board,albums}_raw.json
python make_shuoshuo_md.py backups/<QQ号>
python make_blog_md.py backups/<QQ号>
python make_board_albums_md.py backups/<QQ号>   # 同时生成 _photo_manifest.json
python download_photos.py backups/<QQ号>        # 批量下载相册原图
```

多账号：每个账号重复 1-2 步即可，数据按 QQ 号自动分目录存放（`backups/<QQ号>/`）。

### 输出结构

```
backups/<QQ号>/
├── shuoshuo_raw.json        # 说说原始数据（接口返回原样）
├── blog_raw.json            # 日志原始数据
├── board_raw.json           # 留言板原始数据
├── albums_raw.json          # 相册/照片元数据
├── _photo_manifest.json     # 照片下载清单
├── 说说备份/                # 按年份的 Markdown + 00_总目录.md
├── 日志备份/
├── 留言备份/
└── 相册备份/
    ├── 00_总目录.md
    ├── 相册_某相册.md
    └── 相册下载/            # 照片原图
```

## 已知坑（代码里有注释）

- 日志正文接口返回的是 **GB2312 编码的旧版详情页 HTML**，缺参数会报 `param error`；正文在 `blogDetailDiv` 标记之后
- 留言板接口**单次最多返回 6 条**，分页要按实际返回数推进
- 相册清单里相册 ID 字段叫 `id` 而不是 `albumId`
- 说说 JSONP 返回结尾多一个 `);`，剥壳要用 `rfind(")")`
- 纯转载日志可通过 `tranFlag` / 标题前缀识别并排除（`fetch_blog.py` 里的 `is_tran`）

## 免责声明与注意事项

- 本工具仅导出**你自己账号**的数据，用于个人备份；请遵守 QQ 空间用户协议，勿用于批量抓取他人数据
- `qzone_cookies.json` 是**登录凭证**，等同于你的账号权限：备份完成后请删除，切勿提交到任何仓库或分享（本项目 `.gitignore` 已默认排除）
- 接口调用带 0.6~1.5 秒间隔限速；数据量大时整个备份约需 10-30 分钟（主要耗在照片下载）
- 已删除的内容无法恢复：接口只能拿到服务器上还存在的数据
- 接口是网页版内部 CGI，随时可能变化；若失效可参考接口表中各参数自行调整

## License

MIT
