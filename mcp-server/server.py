#!/usr/bin/env python3
"""
wuji-release MCP Server

启动方式：
  stdio（Claude Code 本地）: python server.py
  HTTP（团队共用服务器）:     python server.py --http
  或通过环境变量:             MCP_TRANSPORT=http python server.py
"""
import asyncio
import logging
import os
import re
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from config import (
    BOOTSTRAP_TOKEN,
    DEBUG_MODE,
    LOG_LEVEL,
    MCP_PORT,
    MCP_TRANSPORT,
    REVIEW_TOKEN,
    get_repo_token,
    issue_repo_token,
    public_runtime_config,
    get_repo_reviewers,
    set_repo_reviewers,
)
from tools.validate import validate_release_input
from tools.changelog import preview_changelog
from tools.github_actions import trigger_release, get_workflow_status
from tools.fetch import fetch_changelog
from tools.versions import get_current_versions, suggest_next_version

server = Server("wuji-release")
logger = logging.getLogger("wuji-release")
REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def setup_logging():
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


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
    from tools.jira import create_jira_issue, extract_jira_id_from_text, add_jira_comment
    from tools.feishu import send_review_card, notify_reviewers
    import uvicorn

    sse = SseServerTransport("/mcp/messages")

    def unauthorized_response(message: str = "Unauthorized"):
        return JSONResponse({"error": message}, status_code=401)

    def bad_request(message: str):
        return JSONResponse({"error": message}, status_code=400)

    def server_error(message: str, request_id: str = ""):
        payload = {"error": message}
        if request_id:
            payload["request_id"] = request_id
        return JSONResponse(payload, status_code=500)

    def log_request_end(name: str, request_id: str, started_at: float, status_code: int, **fields):
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        details = " ".join(f"{k}={v}" for k, v in fields.items() if v not in ("", None))
        logger.info(
            "%s request finished request_id=%s status=%s elapsed_ms=%s %s",
            name,
            request_id,
            status_code,
            elapsed_ms,
            details,
        )

    def parse_bearer_token(auth_header: str) -> str:
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return ""
        return auth_header[len(prefix):].strip()

    def verify_review_token(auth_header: str, org: str, repo: str) -> tuple[bool, str]:
        token = parse_bearer_token(auth_header)
        if not token:
            return False, "Missing bearer token"

        repo_token = get_repo_token(org, repo)
        if repo_token:
            return token == repo_token, "repo"

        if REVIEW_TOKEN:
            return token == REVIEW_TOKEN, "shared"

        return True, "open"

    async def handle_sse(scope, receive, send):
        request_id = f"sse-{int(time.time() * 1000)}"
        started_at = time.perf_counter()
        client = scope.get("client") or ("unknown", "")
        logger.info("sse connect request_id=%s client=%s:%s", request_id, client[0], client[1])
        try:
            async with sse.connect_sse(scope, receive, send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
            log_request_end("sse", request_id, started_at, 200, client=client[0])
        except Exception as exc:
            logger.exception("sse connect failed request_id=%s error=%s", request_id, exc)
            if DEBUG_MODE:
                body = f"SSE connection failed\nrequest_id={request_id}\n\n{traceback.format_exc()}"
            else:
                body = f"SSE connection failed. request_id={request_id}. Check server logs."
            response = PlainTextResponse(body, status_code=500)
            await response(scope, receive, send)

    async def handle_debug_config(request: Request):
        return JSONResponse(public_runtime_config())

    async def handle_ready(request: Request):
        return JSONResponse({"ok": True, **public_runtime_config()})

    async def handle_bootstrap_register(request: Request):
        request_id = f"bootstrap-{int(time.time() * 1000)}"
        started_at = time.perf_counter()
        auth = parse_bearer_token(request.headers.get("authorization", ""))
        if not BOOTSTRAP_TOKEN or auth != BOOTSTRAP_TOKEN:
            log_request_end("bootstrap", request_id, started_at, 401)
            return unauthorized_response("Invalid bootstrap token")

        try:
            data = await request.json()
        except Exception:
            log_request_end("bootstrap", request_id, started_at, 400)
            return bad_request("Invalid JSON")

        repo_full_name = str(data.get("repo_full_name", "")).strip()
        if not REPO_SLUG_RE.match(repo_full_name):
            log_request_end("bootstrap", request_id, started_at, 400, repo_full_name=repo_full_name)
            return bad_request("repo_full_name must be org/repo")

        org, repo = repo_full_name.split("/", 1)
        review_token = issue_repo_token(org, repo)
        logger.info("bootstrap register request_id=%s repo=%s", request_id, repo_full_name)
        log_request_end("bootstrap", request_id, started_at, 200, repo=repo_full_name)
        return JSONResponse({
            "ok": True,
            "repo_full_name": repo_full_name,
            "review_token": review_token,
            "request_id": request_id,
        })

    async def handle_reviewers(request: Request):
        """GET /reviewers/{org}/{repo} → list reviewers; POST /reviewers → set reviewers"""
        if request.method == "GET":
            path_parts = request.url.path.strip("/").split("/")
            if len(path_parts) < 3:
                return bad_request("Path: /reviewers/{org}/{repo}")
            org, repo = path_parts[1], path_parts[2]
            reviewers = get_repo_reviewers(org, repo)
            return JSONResponse({"repo": f"{org}/{repo}", "reviewers": reviewers})

        # POST
        try:
            data = await request.json()
        except Exception:
            return bad_request("Invalid JSON")

        repo_full_name = str(data.get("repo_full_name", "")).strip()
        if not REPO_SLUG_RE.match(repo_full_name):
            return bad_request("repo_full_name must be org/repo")

        auth = parse_bearer_token(request.headers.get("authorization", ""))
        if not BOOTSTRAP_TOKEN or auth != BOOTSTRAP_TOKEN:
            return unauthorized_response("Invalid bootstrap token")

        reviewers = data.get("reviewers", [])
        if not isinstance(reviewers, list):
            return bad_request("reviewers must be a list of {open_id, name}")

        org, repo = repo_full_name.split("/", 1)
        set_repo_reviewers(org, repo, reviewers)
        logger.info("reviewers updated repo=%s count=%d", repo_full_name, len(reviewers))
        return JSONResponse({"ok": True, "repo": repo_full_name, "reviewers": reviewers})

    async def handle_review(request: Request):
        request_id = f"review-{int(time.time() * 1000)}"
        started_at = time.perf_counter()

        try:
            data = await request.json()
        except Exception:
            log_request_end("review", request_id, started_at, 400)
            return bad_request("Invalid JSON")

        repo = data.get("repo", "")
        org = data.get("org", os.environ.get("GITHUB_ORG", ""))
        pr_number = data.get("pr_number") or data.get("pr")
        if not repo or not pr_number:
            log_request_end("review", request_id, started_at, 400, repo=repo, pr_number=pr_number)
            return bad_request("repo and pr_number are required")

        auth_ok, auth_mode = verify_review_token(request.headers.get("authorization", ""), org, repo)
        if not auth_ok:
            log_request_end("review", request_id, started_at, 401, repo=repo, pr_number=pr_number)
            return unauthorized_response()

        logger.info("review request started request_id=%s repo=%s pr_number=%s auth=%s", request_id, repo, pr_number, auth_mode)

        jira_integration = None
        if os.environ.get("JIRA_SYNC_TO_JIRA", "false").lower() == "true":
            jira_integration = {
                "sync_to_jira": True,
                "status_mapping": {
                    "blocker": os.environ.get("JIRA_BLOCKER_STATUS_ID", "3"),
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
            logger.error("review failed request_id=%s repo=%s pr_number=%s error=%s", request_id, repo, pr_number, result["error"])
            log_request_end("review", request_id, started_at, 500, repo=repo, pr_number=pr_number)
            return server_error(result["error"], request_id)

        review_text = result["review"]
        jira_synced = result.get("jira_synced", False)
        jira_action = result.get("jira_action", None)

        if jira_synced and jira_action == "blocked_and_retuned":
            prefix = "---\n[TRIGGER_JIRA_RETUN]:true\n---\n\n"
            review_text = prefix + review_text

        log_request_end("review", request_id, started_at, 200, repo=repo, pr_number=pr_number, auth=auth_mode)
        return PlainTextResponse(review_text)

    async def handle_pipeline(request: Request):
        request_id = f"pipeline-{int(time.time() * 1000)}"
        started_at = time.perf_counter()

        try:
            data = await request.json()
        except Exception:
            log_request_end("pipeline", request_id, started_at, 400)
            return bad_request("Invalid JSON")

        repo = data.get("repo", "")
        pr_number = data.get("pr_number") or data.get("pr")
        title = data.get("title", "")
        body = data.get("body", "")
        org = data.get("org", os.environ.get("GITHUB_ORG", ""))
        pr_url = f"https://github.com/{org}/{repo}/pull/{pr_number}"

        if not repo or not pr_number:
            log_request_end("pipeline", request_id, started_at, 400, repo=repo, pr_number=pr_number)
            return bad_request("repo and pr_number are required")

        auth_ok, auth_mode = verify_review_token(request.headers.get("authorization", ""), org, repo)
        if not auth_ok:
            log_request_end("pipeline", request_id, started_at, 401, repo=repo, pr_number=pr_number)
            return unauthorized_response()

        logger.info("pipeline request started request_id=%s repo=%s pr_number=%s org=%s auth=%s", request_id, repo, pr_number, org, auth_mode)
        result_log = {"steps": []}

        jira_id = extract_jira_id_from_text(body) or extract_jira_id_from_text(title)
        jira_url = ""
        if not jira_id:
            jira_result = create_jira_issue(title=title, body=body, pr_url=pr_url, repo=repo)
            if jira_result["ok"]:
                jira_id = jira_result["issue_id"]
                jira_url = jira_result.get("issue_url", "")
                result_log["steps"].append(f"✅ Jira 工单已创建: {jira_id}")
            else:
                result_log["steps"].append(f"⚠️ Jira 创建失败: {jira_result['error']}")
                logger.warning("jira create failed request_id=%s repo=%s pr_number=%s error=%s", request_id, repo, pr_number, jira_result["error"])
        else:
            result_log["steps"].append(f"ℹ️ 已关联 Jira: {jira_id}")

        review_result = pr_review(
            repo=repo,
            pr_number=int(pr_number),
            title=title,
            body=body,
            language=data.get("language", "zh"),
        )

        if not review_result["ok"]:
            logger.error("pipeline review failed request_id=%s repo=%s pr_number=%s error=%s", request_id, repo, pr_number, review_result["error"])
            log_request_end("pipeline", request_id, started_at, 500, repo=repo, pr_number=pr_number)
            return server_error(review_result["error"], request_id)

        review_text = review_result["review"]
        has_blocker = bool(re.search(r"\|\s*Blocker\s*\|", review_text, re.MULTILINE))
        result_log["steps"].append("✅ AI Review 完成")

        comment_parts = []
        if jira_id:
            jira_link = f"[{jira_id}]({jira_url})" if jira_url else jira_id
            comment_parts.append(f"> 📌 Jira 工单: {jira_link}")
        comment_parts.append(review_text)
        final_comment = "\n\n".join(comment_parts)

        summary_match = re.search(r"###\s*(整体结论|总体评价|Summary)\s*\n(.+?)(?=\n###|$)", review_text, re.DOTALL)
        review_summary = summary_match.group(2).strip() if summary_match else review_text[:300]

        if jira_id:
            # Append review summary as Jira comment
            jira_comment_result = add_jira_comment(jira_id, f"h3. AI Review 摘要\n{review_summary}\n\n---\nPR: {pr_url}")
            if jira_comment_result.get("ok"):
                result_log["steps"].append(f"✅ Jira 评论已追加: {jira_id}")
            else:
                logger.warning("jira comment failed request_id=%s jira_id=%s error=%s", request_id, jira_id, jira_comment_result.get("error"))

        feishu_result = send_review_card(
            pr_title=title,
            pr_url=pr_url,
            repo=repo,
            review_summary=review_summary,
            jira_issue_id=jira_id,
            jira_issue_url=jira_url,
            has_blocker=has_blocker,
        )
        if feishu_result["ok"]:
            result_log["steps"].append("✅ 飞书通知已发送")
        else:
            result_log["steps"].append(f"⚠️ 飞书通知失败: {feishu_result['error']}")
            logger.warning("feishu notify failed request_id=%s repo=%s pr_number=%s error=%s", request_id, repo, pr_number, feishu_result["error"])

        # Notify reviewers
        reviewers = get_repo_reviewers(org, repo)
        if reviewers:
            reviewer_result = notify_reviewers(
                pr_title=title,
                pr_url=pr_url,
                repo=repo,
                reviewers=reviewers,
                jira_issue_id=jira_id,
                jira_issue_url=jira_url,
            )
            if reviewer_result.get("ok"):
                result_log["steps"].append(f"✅ 审核人已通知 ({reviewer_result['notified']}人)")
            else:
                result_log["steps"].append(f"⚠️ 审核人通知失败: {reviewer_result.get('error', '')}")
                logger.warning("reviewer notify failed request_id=%s error=%s", request_id, reviewer_result.get("error"))

        log_request_end("pipeline", request_id, started_at, 200, repo=repo, pr_number=pr_number, has_blocker=has_blocker, auth=auth_mode)
        return JSONResponse({
            "review": final_comment,
            "jira_id": jira_id,
            "jira_url": jira_url,
            "has_blocker": has_blocker,
            "steps": result_log["steps"],
            "request_id": request_id,
        })

    app = Starlette(routes=[
        Route("/mcp/sse", endpoint=handle_sse),
        Route("/mcp/messages", endpoint=sse.handle_post_message, methods=["POST"]),
        Route("/review", endpoint=handle_review, methods=["POST"]),
        Route("/pr-pipeline", endpoint=handle_pipeline, methods=["POST"]),
        Route("/bootstrap/register-repo", endpoint=handle_bootstrap_register, methods=["POST"]),
        Route("/reviewers/{org}/{repo}", endpoint=handle_reviewers),
        Route("/reviewers", endpoint=handle_reviewers, methods=["POST"]),
        Route("/health", endpoint=lambda _: PlainTextResponse("ok")),
        Route("/ready", endpoint=handle_ready),
        Route("/debug/config", endpoint=handle_debug_config),
    ])
    logger.info("wuji-release MCP HTTP Server listening on http://0.0.0.0:%s/mcp/sse", MCP_PORT)
    logger.info("PR Review endpoint listening on http://0.0.0.0:%s/review", MCP_PORT)
    logger.info("PR Pipeline endpoint listening on http://0.0.0.0:%s/pr-pipeline", MCP_PORT)
    logger.info("Bootstrap endpoint listening on http://0.0.0.0:%s/bootstrap/register-repo", MCP_PORT)
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)


def main():
    setup_logging()
    use_http = "--http" in sys.argv or MCP_TRANSPORT == "http"
    if use_http:
        _run_http()
    else:
        _run_stdio()


if __name__ == "__main__":
    main()
