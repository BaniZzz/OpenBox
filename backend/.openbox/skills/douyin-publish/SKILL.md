---
name: douyin-publish
description: Post a finished video to the person's Douyin (抖音) account — check the workspace's Douyin authorization, get a re-authorization QR code when it lapsed, draft the caption and hashtags, confirm them, and hand over a posting QR code the person scans in the Douyin app. Use for 发抖音/投稿/发布到抖音/抖音授权 requests, or right after a video is delivered and the person wants it published.
allowed-tools:
  - douyin_publish
  - question
  - share_file
  - read
---

# 发布到抖音

抖音不允许应用替用户发布：每一条视频都要用户本人用抖音 App 扫码，在抖音里点「发布」。你的工作是把扫码之前的一切准备好，扫码之后把结果查清楚。所有操作只用 `douyin_publish` 工具；不要打开抖音网页、不要让用户把视频传到别处。

## 流程

1. **先看授权** `douyin_publish(action="status")`。
   - 有「已授权」账号 → 进第 3 步。
   - 「已失效」或没有账号 → 第 2 步。
   - 返回 `PLATFORM_NOT_CONFIGURED` → 告诉用户本环境还没接抖音，停止。
2. **重新授权** `douyin_publish(action="authorize")`。工具会把授权二维码贴在回复里并给出链接，10 分钟有效。用一句话告诉用户：电脑上点链接后用抖音扫页面二维码，或手机直接扫回复里的二维码；扫完告诉你一声。用户说扫完了 → 再 `status` 确认变成「已授权」再继续。不要替用户猜测已经授权。
   - 返回 `PLATFORM_ROLE_REQUIRED` → 只有工作空间管理员能绑定，请用户找管理员在「授权中心」绑定。
3. **准备视频的 asset_id**。刚交付的成片：`share_file` 的返回里有 `asset_id`；如果那次是 `attach=true`，回复的元数据里同样有。用户从资源中心指定的文件：让用户在授权中心的「发布到抖音」里选，或者问清文件名后用 `share_file(attach=false)` 登记。视频必须是 mp4/mov、不超过 128 MB。
4. **拟标题和话题**，这是你要替用户想好的部分：
   - 标题 ≤ 55 字，说清视频讲什么、给谁看，口语化，不堆修辞，不出现「AI 生成」之类与内容无关的话。
   - 话题 3–5 个，不带 `#`，优先垂直类目词 + 一个泛流量词（如「装修」「老房改造」「干货分享」）。
   - 用 `question` 出一张确认卡：标题全文、话题列表、可见范围（默认所有人可见）；选项「可以」「改一下」。用户没点「可以」不许 publish。
5. **出投稿码** `douyin_publish(action="publish", asset_id=…, title=…, hashtags=[…])`。工具会把二维码贴在回复里。告诉用户：打开抖音 App 扫码，抖音会自动下载视频进到发布页，标题话题已填好，点「发布」即可；二维码一小时内有效。
6. **查结果**。用户说发了 → `douyin_publish(action="result", job_id=…)`。`published` 就恭喜并给作品 id；`pending` 说明抖音还没回调，等一分钟再查一次；`expired` 重新出码。不要自己轮询超过两次。

## 注意

- 授权最长 195 天免扫码，工具的 `status` 会给出「预计到期」；到期前一周提醒用户去授权中心点「检测」或重新授权。
- 一个工作空间可能绑了多个抖音号；发布时扫码的是哪个账号，视频就发到哪个号，工具无法指定。如果 `status` 列出多个账号，提醒用户用对应的手机扫。
- 对用户不暴露 job_id、asset_id、openid 这类内部标识；错误翻译成人话。
- 视频内容是别人的作品时，不要走投稿，说明抖音要求只发自己创作的内容。
