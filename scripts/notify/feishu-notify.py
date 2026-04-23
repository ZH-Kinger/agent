#!/usr/bin/env python3
"""
发送飞书 webhook 通知

支持 Release 成功和失败两种通知类型
"""
import argparse
import requests
import sys


def send_release_notification(webhook_url, repo, version, release_url, status):
    """
    发送 Release 完成通知

    Args:
        webhook_url: 飞书 webhook URL
        repo: 仓库名 (如 wujihandpy)
        version: 版本号 (如 1.5.0)
        release_url: GitHub Release URL
        status: success 或 failed
    """

    if status == 'success':
        template = "green"
        title = f"🚀 {repo} v{version} 发布成功"
        content_lines = [
            f"**仓库**: {repo}",
            f"**版本**: v{version}",
            "**状态**: ✅ 已发布"
        ]
        button_text = "查看 Release"
        button_url = release_url
    else:
        template = "red"
        title = f"❌ {repo} v{version} 发布失败"
        content_lines = [
            f"**仓库**: {repo}",
            f"**版本**: v{version}",
            "**状态**: ❌ 发布失败"
        ]
        button_text = None
        button_url = None

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"content": title, "tag": "plain_text"},
                "template": template
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": "\n".join(content_lines),
                        "tag": "lark_md"
                    }
                }
            ]
        }
    }

    # 添加按钮
    if button_text and button_url:
        card["card"]["elements"].append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"content": button_text, "tag": "plain_text"},
                "url": button_url,
                "type": "primary"
            }]
        })

    try:
        response = requests.post(webhook_url, json=card, timeout=10)
        response.raise_for_status()
        print("✅ 飞书通知发送成功")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ 飞书通知发送失败: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}", file=sys.stderr)
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='发送飞书 webhook 通知'
    )
    parser.add_argument('--webhook', required=True, help='飞书 webhook URL')
    parser.add_argument('--repo', required=True, help='仓库名')
    parser.add_argument('--version', required=True, help='版本号')
    parser.add_argument('--release-url', required=True, help='Release URL')
    parser.add_argument('--status', required=True, choices=['success', 'failed'])

    args = parser.parse_args()

    success = send_release_notification(
        args.webhook,
        args.repo,
        args.version,
        args.release_url,
        args.status
    )

    sys.exit(0 if success else 1)
