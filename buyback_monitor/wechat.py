from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class PublishResult:
    status: str
    error: str | None = None


def publish_article(title: str, html_path: Path) -> PublishResult:
    if os.getenv("WECHAT_ENABLE_PUBLISH") != "1":
        return PublishResult("skipped", "WECHAT_ENABLE_PUBLISH 未开启，已生成日报 HTML。")
    app_id = os.getenv("WECHAT_APP_ID")
    app_secret = os.getenv("WECHAT_APP_SECRET")
    thumb_media_id = os.getenv("WECHAT_THUMB_MEDIA_ID")
    author = os.getenv("WECHAT_AUTHOR", "")
    if not app_id or not app_secret or not thumb_media_id:
        return PublishResult("failed", "缺少 WECHAT_APP_ID / WECHAT_APP_SECRET / WECHAT_THUMB_MEDIA_ID。")

    try:
        token_url = "https://api.weixin.qq.com/cgi-bin/token?" + urlencode(
            {"grant_type": "client_credential", "appid": app_id, "secret": app_secret}
        )
        with urlopen(Request(token_url), timeout=30) as response:
            token_json = json.loads(response.read().decode("utf-8"))
        token = token_json.get("access_token")
        if not token:
            return PublishResult("failed", f"获取 access_token 失败：{token_json}")

        content = html_path.read_text(encoding="utf-8")
        draft_body = json.dumps(
            {
                "articles": [
                    {
                        "title": title,
                        "author": author,
                        "digest": "港股回购计划监控日报",
                        "content": content,
                        "thumb_media_id": thumb_media_id,
                        "need_open_comment": 0,
                        "only_fans_can_comment": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        draft_req = Request(
            "https://api.weixin.qq.com/cgi-bin/draft/add?" + urlencode({"access_token": token}),
            data=draft_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(draft_req, timeout=45) as response:
            draft_json = json.loads(response.read().decode("utf-8"))
        media_id = draft_json.get("media_id")
        if not media_id:
            return PublishResult("failed", f"创建草稿失败：{draft_json}")

        publish_req = Request(
            "https://api.weixin.qq.com/cgi-bin/freepublish/submit?" + urlencode({"access_token": token}),
            data=json.dumps({"media_id": media_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(publish_req, timeout=45) as response:
            publish_json = json.loads(response.read().decode("utf-8"))
        if publish_json.get("errcode", 0) not in (0, None):
            return PublishResult("failed", f"提交发布失败：{publish_json}")
        return PublishResult("submitted", str(publish_json))
    except Exception as exc:
        return PublishResult("failed", str(exc))
