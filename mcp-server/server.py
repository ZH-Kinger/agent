#!/usr/bin/env python3
"""
wuji-release MCP Server

启动方式：
  stdio（Claude Code 本地）: python server.py
  HTTP（团队共用服务器）:     python server.py --http
  或通过环境变量:             MCP_TRANSPORT=http python server.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from tools.validate import validate_release_input
from tools.changelog import preview_changelog, fetch_unreleased_section
from tools.github_actions import trigger_release, get_workflow_status
from tools.fetch import fetch_changelog
from tools.versions import get_current_versions, suggest_next_version

server = Server("wuji-release")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="validate_release_input",
            description=(
                "校验 repo=version 格式输入是否合法。"
                "触发发布前先调用此工具确认格式正确。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repos_text": {
                        "type": "string",
                        "description": "多行文本，每行格式：repo=version 或 repo=version:changelog_path",
                    }
                },
                "required": ["repos_text"],
            },
        ),
        types.Tool(
            name="preview_changelog",
            description=(
                "预览将 CHANGELOG 中 Unreleased 替换为指定版本后的效果（dry-run，不修改文件）。"
                "建议触发发布前确认 CHANGELOG 内容。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changelog_content": {"type": "string", "description": "CHANGELOG.md 完整文本"},
                    "version": {"type": "string", "description": "目标版本号，如 1.5.0"},
                    "release_date": {"type": "string", "description": "发布日期 YYYY-MM-DD，留空用今天", "default": ""},
                },
                "required": ["changelog_content", "version"],
            },
        ),
        types.Tool(
            name="fetch_changelog",
            description="从 GitHub tag 获取指定仓库某版本的 CHANGELOG 内容。",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "仓库名，如 wujihandpy"},
                    "version": {"type": "string", "description": "版本号，如 1.5.0（不带 v）"},
                    "changelog_path": {"type": "string", "description": "CHANGELOG 路径，默认 CHANGELOG.md", "default": "CHANGELOG.md"},
                },
                "required": ["repo", "version"],
            },
        ),
        types.Tool(
            name="trigger_release",
            description=(
                "触发 release-centralized workflow，批量更新 CHANGELOG 并创建 release PR。"
                "建议先用 validate_release_input 确认格式。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repos_text": {"type": "string", "description": "多行文本，每行 repo=version"},
                    "release_date": {"type": "string", "description": "发布日期 YYYY-MM-DD，留空用当天", "default": ""},
                    "dry_run": {"type": "boolean", "description": "true 时仅预览不创建 PR", "default": False},
                },
                "required": ["repos_text"],
            },
        ),
        types.Tool(
            name="get_workflow_status",
            description="查询最近几次 release workflow 的运行状态。",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_file": {"type": "string", "description": "workflow 文件名", "default": "release-centralized.yml"},
                    "limit": {"type": "integer", "description": "返回最近几条", "default": 5},
                },
            },
        ),
        types.Tool(
            name="suggest_next_version",
            description=(
                "根据仓库当前版本和 Unreleased CHANGELOG 内容，自动推断下一个版本号。"
                "含新功能(Added)→minor bump，含破坏性变更(Removed/Breaking)→major bump，其余→patch bump。"
                "发版前调用此工具可省去手动计算版本号。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "仓库名，如 wujihandpy"},
                    "changelog_path": {"type": "string", "description": "CHANGELOG 路径，默认 CHANGELOG.md", "default": "CHANGELOG.md"},
                },
                "required": ["repo"],
            },
        ),
        types.Tool(
            name="get_current_versions",
            description=(
                "查询各仓库当前已发布的最新版本号和发布日期。"
                "留空 repos 则自动列出组织下所有仓库。"
                "发版前可用此工具确认当前版本，决定下一个版本号。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "仓库名列表，如 [\"wujihandpy\", \"wujihandros2\"]。留空则查询所有仓库。",
                    }
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    match name:
        case "validate_release_input":
            r = validate_release_input(arguments["repos_text"])
            text = r["summary"] if r["ok"] else f"❌ {r['error']}"

        case "preview_changelog":
            r = preview_changelog(
                arguments["changelog_content"],
                arguments["version"],
                arguments.get("release_date", ""),
            )
            text = (
                f"✅ {r['message']}\n\n```markdown\n{r['preview'][:3000]}\n```"
                if r["ok"] else f"❌ {r['error']}"
            )

        case "fetch_changelog":
            r = fetch_changelog(
                arguments["repo"],
                arguments["version"],
                arguments.get("changelog_path", "CHANGELOG.md"),
            )
            text = r["summary"] if r["ok"] else f"❌ {r['error']}"

        case "trigger_release":
            r = trigger_release(
                arguments["repos_text"],
                arguments.get("release_date", ""),
                arguments.get("dry_run", False),
            )
            text = r["message"] if r["ok"] else f"❌ {r['error']}"

        case "get_workflow_status":
            r = get_workflow_status(
                arguments.get("workflow_file", "release-centralized.yml"),
                arguments.get("limit", 5),
            )
            text = r["summary"] if r["ok"] else f"❌ {r['error']}"

        case "get_current_versions":
            r = get_current_versions(arguments.get("repos") or None)
            text = r["summary"] if r["ok"] else f"❌ {r['error']}"

        case "suggest_next_version":
            r = suggest_next_version(
                arguments["repo"],
                arguments.get("changelog_path", "CHANGELOG.md"),
            )
            text = r["summary"] if r["ok"] else f"❌ {r['error']}"

        case _:
            text = f"❓ 未知工具: {name}"

    return [types.TextContent(type="text", text=text)]


def _run_stdio():
    async def _main():
        async with stdio_server() as (r, w):
            await server.run(r, w, server.create_initialization_options())
    asyncio.run(_main())


def _run_http():
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse, JSONResponse
    from starlette.routing import Route
    from mcp.server.sse import SseServerTransport
    from tools.review import pr_review
    import uvicorn

    port = int(os.environ.get("MCP_PORT", "8080"))
    review_token = os.environ.get("REVIEW_TOKEN", "")
    sse = SseServerTransport("/mcp/messages")

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_review(request: Request):
        # Token 鉴权
        auth = request.headers.get("authorization", "")
        if review_token and auth != f"Bearer {review_token}":
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        repo = data.get("repo", "")
        pr_number = data.get("pr_number") or data.get("pr")
        if not repo or not pr_number:
            return JSONResponse({"error": "repo and pr_number are required"}, status_code=400)

        # Jira 构造配置（从环境变量读取）
        jira_integration = None
        if os.environ.get("JIRA_SYNC_TO_JIRA", "false").lower() == "true":
            jira_integration = {
                "sync_to_jira": True,
                "status_mapping": {
                    "blocker": os.environ.get("JIRA_BLOCKER_STATUS_ID", "3"),  # 默认退回 To Do
                }
            }

        result = pr_review(
            repo=repo,
            pr_number=int(pr_number),
            title=data.get("title", ""),
            body=data.get("body", ""),
            language=data.get("language", "zh"),
            jira_integration=jira_integration,
        )

        if not result["ok"]:
            return JSONResponse({"error": result["error"]}, status_code=500)

        review_text = result["review"]
        jira_synced = result.get("jira_synced", False)
        jira_action = result.get("jira_action", None)

        # 可选：如果 Jira 已退回，在文本开头标记（GitHub Actions 可解析）
        if jira_synced and jira_action == "blocked_and_retuned":
            prefix = "---\n[TRIGGER_JIRA_RETUN]:true\n---\n\n"
            review_text = prefix + review_text

        return PlainTextResponse(review_text)

    app = Starlette(routes=[
        Route("/mcp/sse", endpoint=handle_sse),
        Route("/mcp/messages", endpoint=sse.handle_post_message, methods=["POST"]),
        Route("/review", endpoint=handle_review, methods=["POST"]),
        Route("/health", endpoint=lambda _: PlainTextResponse("ok")),
    ])
    print(f"🚀 wuji-release MCP HTTP Server → http://0.0.0.0:{port}/mcp/sse")
    print(f"🔍 PR Review endpoint → http://0.0.0.0:{port}/review")
    uvicorn.run(app, host="0.0.0.0", port=port)


def main():
    use_http = "--http" in sys.argv or os.environ.get("MCP_TRANSPORT") == "http"
    if use_http:
        _run_http()
    else:
        _run_stdio()


if __name__ == "__main__":
    main()