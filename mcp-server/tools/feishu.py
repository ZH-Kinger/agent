"""Tool: feishu — 飞书消息通知（支持富文本卡片 + 审核人 @ 通知）"""
import httpx
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID, FEISHU_ENABLED


def _get_tenant_token() -> str:
    """获取飞书 tenant_access_token"""
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")
    return data["tenant_access_token"]


def send_review_card(
    pr_title: str,
    pr_url: str,
    repo: str,
    review_summary: str,
    jira_issue_id: str = "",
    jira_issue_url: str = "",
    has_blocker: bool = False,
    chat_id: str = "",
) -> dict:
    """
    发送 PR Review 结果到飞书群（富文本卡片）。

    Args:
        pr_title: PR 标题
        pr_url: PR 链接
        repo: 仓库名
        review_summary: Review 摘要（取前 500 字）
        jira_issue_id: Jira 工单号
        jira_issue_url: Jira 工单链接
        has_blocker: 是否有 Blocker
        chat_id: 飞书群 ID（留空用默认）

    Returns:
        {"ok": True} 或 {"ok": False, "error": "..."}
    """
    if not FEISHU_ENABLED:
        return {"ok": False, "error": "飞书未启用（缺 FEISHU_APP_ID/APP_SECRET）"}

    target_chat = chat_id or FEISHU_CHAT_ID
    if not target_chat:
        return {"ok": False, "error": "未配置 FEISHU_CHAT_ID"}

    try:
        token = _get_tenant_token()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # 状态标记
    status_emoji = "❌ 发现 Blocker" if has_blocker else "✅ 审查通过"
    status_color = "red" if has_blocker else "green"

    # Jira 信息
    jira_line = ""
    if jira_issue_id:
        jira_line = f"\n**Jira 工单**: [{jira_issue_id}]({jira_issue_url})" if jira_issue_url else f"\n**Jira 工单**: {jira_issue_id}"

    # 截断 review 摘要
    summary_truncated = review_summary[:500]
    if len(review_summary) > 500:
        summary_truncated += "\n\n... (查看完整 Review 请点击 PR 链接)"

    # 构建富文本卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🤖 AI Review: {repo}"},
            "template": status_color,
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**PR**: [{pr_title}]({pr_url})\n"
                        f"**仓库**: {repo}\n"
                        f"**结论**: {status_emoji}"
                        f"{jira_line}"
                    ),
                },
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Review 摘要**:\n{summary_truncated}",
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看 PR"},
                        "type": "primary",
                        "url": pr_url,
                    }
                ],
            },
        ],
    }

    # 如果有 Jira 链接，加个按钮
    if jira_issue_url:
        card["elements"][-1]["actions"].append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": f"查看 {jira_issue_id}"},
            "url": jira_issue_url,
        })

    # 发送
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "receive_id": target_chat,
        "msg_type": "interactive",
        "content": __import__("json").dumps(card, ensure_ascii=False),
    }

    try:
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers=headers,
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            return {"ok": True}
        else:
            return {"ok": False, "error": f"飞书发送失败: code={data.get('code')}, msg={data.get('msg')}"}
    except Exception as e:
        return {"ok": False, "error": f"飞书请求失败: {e}"}


def notify_reviewers(
    pr_title: str,
    pr_url: str,
    repo: str,
    reviewers: list[dict],
    jira_issue_id: str = "",
    jira_issue_url: str = "",
) -> dict:
    """
    发送审核通知给指定审核人（飞书个人消息）。

    Args:
        pr_title: PR 标题
        pr_url: PR 链接
        repo: 仓库名
        reviewers: [{"open_id": "ou_xxx", "name": "张三"}, ...]
        jira_issue_id: Jira 工单号
        jira_issue_url: Jira 工单链接

    Returns:
        {"ok": True, "notified": 3} 或 {"ok": False, "error": "..."}
    """
    if not FEISHU_ENABLED:
        return {"ok": False, "error": "飞书未启用"}

    if not reviewers:
        return {"ok": False, "error": "无审核人"}

    try:
        token = _get_tenant_token()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Build reviewer mention text
    mention_parts = []
    for r in reviewers:
        open_id = r.get("open_id", "")
        name = r.get("name", open_id)
        if open_id:
            mention_parts.append(f'<at user_id="{open_id}">{name}</at>')
    mention_text = " ".join(mention_parts)

    jira_line = ""
    if jira_issue_id:
        jira_line = f"\n**Jira 工单**: [{jira_issue_id}]({jira_issue_url})" if jira_issue_url else f"\n**Jira 工单**: {jira_issue_id}"

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📢 审核请求: {repo}"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"{mention_text}\n\n"
                        f"**PR**: [{pr_title}]({pr_url})\n"
                        f"**仓库**: {repo}"
                        f"{jira_line}\n\n"
                        f"请尽快审核此 PR"
                    ),
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "审核 PR"},
                        "type": "primary",
                        "url": pr_url,
                    }
                ],
            },
        ],
    }

    notified = 0
    errors = []
    for reviewer in reviewers:
        open_id = reviewer.get("open_id", "")
        if not open_id:
            continue
        payload = {
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": __import__("json").dumps(card, ensure_ascii=False),
        }
        try:
            resp = httpx.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
                headers=headers,
                json=payload,
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                notified += 1
            else:
                errors.append(f"{reviewer.get('name', open_id)}: code={data.get('code')}, msg={data.get('msg')}")
        except Exception as e:
            errors.append(f"{reviewer.get('name', open_id)}: {e}")

    if notified > 0:
        result = {"ok": True, "notified": notified}
        if errors:
            result["errors"] = errors
        return result
    return {"ok": False, "error": f"全部发送失败: {'; '.join(errors)}"}
