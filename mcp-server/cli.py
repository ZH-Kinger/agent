#!/usr/bin/env python3
"""
wuji-release CLI — 不依赖 Claude，直接在终端操作 Release / Onboarding 流程

用法:
  wuji-review init --server-url http://your-server:8080 --bootstrap-token xxx
  wuji-review doctor --server-url http://your-server:8080
  wuji-release validate "wujihandpy=1.5.0\nwujihandros2=2.0.0"
  wuji-release fetch wujihandpy 1.5.0
  wuji-release trigger "wujihandpy=1.5.0" --date 2026-05-01
  wuji-release trigger "wujihandpy=1.5.0" --dry-run
  wuji-release status
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))

import click
import httpx
from tools.validate import validate_release_input
from tools.github_actions import trigger_release, get_workflow_status
from tools.fetch import fetch_changelog
from tools.versions import get_current_versions, suggest_next_version

PACKAGE_ROOT = Path(__file__).resolve().parent
WORKFLOW_TEMPLATE = PACKAGE_ROOT / "templates" / "ci-pr-pipeline.yml"
DEFAULT_MCP_SERVER_NAME = "wuji-release"
DEFAULT_GITHUB_ORG = "wuji-technology"


class CliError(click.ClickException):
    pass


def _find_git_root(start: Path) -> Path | None:
    start = start.resolve()
    for current in (start, *start.parents):
        if (current / ".git").exists():
            return current
    return None


def _ensure_template_exists() -> None:
    if not WORKFLOW_TEMPLATE.exists():
        raise CliError(f"缺少 workflow 模板: {WORKFLOW_TEMPLATE}")


def _normalize_server_url(server_url: str) -> str:
    url = server_url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CliError("--server-url 必须是完整地址，例如 http://115.191.2.86:8080")
    return url


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON 文件格式错误: {path} ({exc})") from exc


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_workflow(repo_root: Path, force: bool) -> tuple[Path, str]:
    _ensure_template_exists()
    target_dir = repo_root / ".github" / "workflows"
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / "ci-pr-pipeline.yml"
    template_text = WORKFLOW_TEMPLATE.read_text(encoding="utf-8")

    if target_path.exists():
        existing_text = target_path.read_text(encoding="utf-8")
        if existing_text == template_text:
            return target_path, "kept"
        if not force:
            raise CliError(f"{target_path} 已存在且内容不同，使用 --force 可覆盖")

    target_path.write_text(template_text, encoding="utf-8")
    return target_path, "written"


def _build_mcp_server_entry(mode: str, github_org: str, server_url: str) -> dict:
    if mode == "stdio":
        return {
            "type": "stdio",
            "command": "wuji-release-mcp",
            "env": {
                "GITHUB_TOKEN": "${GITHUB_TOKEN}",
                "GITHUB_ORG": github_org,
            },
        }

    if mode == "sse":
        if not server_url:
            raise CliError("SSE 模式需要 --server-url")
        return {
            "type": "sse",
            "url": f"{server_url}/mcp/sse",
        }

    raise CliError(f"不支持的 MCP 模式: {mode}")


def _ensure_mcp_config(repo_root: Path, mode: str, github_org: str, server_url: str) -> tuple[Path, str]:
    mcp_path = repo_root / ".mcp.json"
    config = _read_json(mcp_path) if mcp_path.exists() else {}
    config.setdefault("mcpServers", {})

    entry = _build_mcp_server_entry(mode, github_org, server_url)
    status = "written"
    if config["mcpServers"].get(DEFAULT_MCP_SERVER_NAME) == entry:
        status = "kept"
    else:
        config["mcpServers"][DEFAULT_MCP_SERVER_NAME] = entry
        _write_json(mcp_path, config)

    return mcp_path, status


def _gh_exists() -> bool:
    return shutil.which("gh") is not None


def _gh_auth_ok() -> tuple[bool, str]:
    if not _gh_exists():
        return False, "未检测到 gh，请先安装 GitHub CLI"

    proc = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return True, "gh 已登录"

    stderr = (proc.stderr or proc.stdout or "").strip()
    return False, stderr or "gh 未登录，请先执行 gh auth login"


def _gh_repo_full_name(repo_root: Path) -> str:
    proc = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise CliError(f"读取当前 GitHub 仓库失败\n{stderr}")

    repo_full_name = proc.stdout.strip()
    if not repo_full_name or "/" not in repo_full_name:
        raise CliError("无法识别当前仓库的 org/repo")
    return repo_full_name


def _set_github_secret(repo_root: Path, name: str, value: str) -> None:
    proc = subprocess.run(
        ["gh", "secret", "set", name, "--body", value],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise CliError(f"设置 GitHub Secret 失败: {name}\n{stderr}")


def _register_repo_token(server_url: str, bootstrap_token: str, repo_full_name: str) -> str:
    try:
        response = httpx.post(
            f"{server_url}/bootstrap/register-repo",
            headers={"Authorization": f"Bearer {bootstrap_token}"},
            json={"repo_full_name": repo_full_name},
            timeout=15.0,
        )
    except Exception as exc:
        raise CliError(f"调用服务端注册接口失败: {exc}") from exc

    if response.status_code != 200:
        try:
            payload = response.json()
            message = payload.get("error") or payload
        except Exception:
            message = response.text.strip() or f"HTTP {response.status_code}"
        raise CliError(f"服务端注册仓库失败: {message}")

    payload = response.json()
    review_token = str(payload.get("review_token", "")).strip()
    if not review_token:
        raise CliError("服务端没有返回 review_token")
    return review_token


def _print_next_steps(repo_root: Path, workflow_path: Path, mcp_path: Path | None) -> None:
    click.echo()
    click.secho("下一步：", fg="cyan")
    click.echo(f"1. git add {workflow_path.relative_to(repo_root)}")
    if mcp_path:
        click.echo(f"2. git add {mcp_path.relative_to(repo_root)}")
        click.echo("3. git commit -m \"ci: bootstrap wuji review\"")
        click.echo("4. git push")
        click.echo("5. 提一个测试 PR，确认 PR Convention Check 和 AI Code Review 正常")
    else:
        click.echo("2. git commit -m \"ci: bootstrap wuji review\"")
        click.echo("3. git push")
        click.echo("4. 提一个测试 PR，确认 PR Convention Check 和 AI Code Review 正常")


def _check_http_endpoint(url: str) -> tuple[bool, str]:
    try:
        response = httpx.get(url, timeout=10.0)
        return response.status_code < 500, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    """wuji-release / wuji-review — Release 自动化与仓库初始化工具。"""


@main.command()
@click.option("--repo-path", default=".", type=click.Path(path_type=Path, file_okay=False), help="目标仓库路径")
@click.option("--server-url", default="", help="Review Server 地址，例如 http://115.191.2.86:8080")
@click.option("--bootstrap-token", default="", help="初始化注册用管理员口令")
@click.option("--github-org", default=DEFAULT_GITHUB_ORG, help="写入 stdio MCP 配置时使用的 GitHub 组织")
@click.option("--mcp-mode", type=click.Choice(["auto", "sse", "stdio", "skip"]), default="auto", show_default=True, help="初始化 Claude Code MCP 的方式")
@click.option("--set-secrets/--no-set-secrets", default=True, show_default=True, help="如果 gh 可用，则自动写入 GitHub Secrets")
@click.option("--force", is_flag=True, default=False, help="覆盖已有 workflow 文件")
@click.option("--yes", is_flag=True, default=False, help="跳过 secrets 写入确认")
def init(repo_path, server_url, bootstrap_token, github_org, mcp_mode, set_secrets, force, yes):
    """一条命令完成 workflow + GitHub Secrets + Claude MCP 初始化。"""
    repo_root = _find_git_root(repo_path)
    if not repo_root:
        raise CliError("当前目录不是 Git 仓库，请在业务仓库里执行，或通过 --repo-path 指定")

    normalized_server_url = _normalize_server_url(server_url) if server_url else ""
    resolved_mcp_mode = mcp_mode
    if resolved_mcp_mode == "auto":
        resolved_mcp_mode = "sse" if normalized_server_url else "stdio"

    click.secho(f"仓库: {repo_root}", fg="cyan")

    workflow_path, workflow_status = _ensure_workflow(repo_root, force)
    if workflow_status == "written":
        click.secho(f"已写入 workflow: {workflow_path}", fg="green")
    else:
        click.secho(f"workflow 已存在，无需修改: {workflow_path}", fg="yellow")

    mcp_path = None
    if resolved_mcp_mode != "skip":
        mcp_path, mcp_status = _ensure_mcp_config(repo_root, resolved_mcp_mode, github_org, normalized_server_url)
        if mcp_status == "written":
            click.secho(f"已写入 Claude MCP 配置: {mcp_path}", fg="green")
        else:
            click.secho(f"Claude MCP 配置已存在，无需修改: {mcp_path}", fg="yellow")

    gh_ok, gh_message = _gh_auth_ok()
    if gh_ok:
        click.secho(gh_message, fg="green")
    else:
        click.secho(gh_message, fg="yellow")

    repo_full_name = ""
    if gh_ok:
        repo_full_name = _gh_repo_full_name(repo_root)
        click.secho(f"GitHub 仓库: {repo_full_name}", fg="green")

    review_token = ""
    if normalized_server_url and bootstrap_token:
        if not repo_full_name:
            click.secho("跳过服务端注册：需要先安装并登录 gh，才能识别当前仓库", fg="yellow")
        else:
            review_token = _register_repo_token(normalized_server_url, bootstrap_token, repo_full_name)
            click.secho("已从服务端注册并获取仓库专属 REVIEW_TOKEN", fg="green")

    if set_secrets:
        if not gh_ok:
            click.secho("跳过 GitHub Secrets 写入：gh 不可用或未登录", fg="yellow")
        elif not normalized_server_url:
            click.secho("跳过 GitHub Secrets 写入：请提供 --server-url", fg="yellow")
        elif not review_token:
            click.secho("跳过 GitHub Secrets 写入：请提供 --bootstrap-token，或先手动准备 REVIEW_TOKEN", fg="yellow")
        else:
            if yes or click.confirm("要把 REVIEW_SERVER_URL 和 REVIEW_TOKEN 写入当前 GitHub 仓库 Secrets 吗？", default=True):
                _set_github_secret(repo_root, "REVIEW_SERVER_URL", normalized_server_url)
                _set_github_secret(repo_root, "REVIEW_TOKEN", review_token)
                click.secho("已写入 GitHub Secrets: REVIEW_SERVER_URL, REVIEW_TOKEN", fg="green")

    if normalized_server_url:
        health_ok, health_message = _check_http_endpoint(f"{normalized_server_url}/health")
        color = "green" if health_ok else "yellow"
        click.secho(f"/health 检查: {health_message}", fg=color)

    _print_next_steps(repo_root, workflow_path, mcp_path)


@main.command()
@click.option("--repo-path", default=".", type=click.Path(path_type=Path, file_okay=False), help="目标仓库路径")
@click.option("--server-url", default="", help="可选：Review Server 地址，例如 http://115.191.2.86:8080")
def doctor(repo_path, server_url):
    """检查仓库接入状态、gh 登录状态和服务端连通性。"""
    repo_root = _find_git_root(repo_path)
    if not repo_root:
        raise CliError("当前目录不是 Git 仓库，请在业务仓库里执行，或通过 --repo-path 指定")

    click.secho(f"仓库: {repo_root}", fg="cyan")

    workflow_path = repo_root / ".github" / "workflows" / "ci-pr-pipeline.yml"
    if workflow_path.exists():
        click.secho(f"[ok] workflow 已存在: {workflow_path}", fg="green")
    else:
        click.secho(f"[missing] workflow 不存在: {workflow_path}", fg="yellow")

    mcp_path = repo_root / ".mcp.json"
    if mcp_path.exists():
        try:
            config = _read_json(mcp_path)
            has_server = bool(config.get("mcpServers", {}).get(DEFAULT_MCP_SERVER_NAME))
            color = "green" if has_server else "yellow"
            label = "ok" if has_server else "missing"
            click.secho(f"[{label}] Claude MCP 配置: {mcp_path}", fg=color)
        except CliError as exc:
            click.secho(f"[error] {exc}", fg="red")
    else:
        click.secho(f"[missing] 未找到 Claude MCP 配置: {mcp_path}", fg="yellow")

    gh_ok, gh_message = _gh_auth_ok()
    click.secho(f"[{'ok' if gh_ok else 'warn'}] {gh_message}", fg="green" if gh_ok else "yellow")
    if gh_ok:
        try:
            click.secho(f"[ok] GitHub 仓库: {_gh_repo_full_name(repo_root)}", fg="green")
        except CliError as exc:
            click.secho(f"[warn] {exc}", fg="yellow")

    if server_url:
        normalized_server_url = _normalize_server_url(server_url)
        for name in ["/health", "/ready", "/debug/config", "/mcp/sse"]:
            ok, message = _check_http_endpoint(f"{normalized_server_url}{name}")
            click.secho(f"[{'ok' if ok else 'warn'}] {name}: {message}", fg="green" if ok else "yellow")


@main.command()
@click.argument("repos_text")
def validate(repos_text):
    """校验 repo=version 格式是否合法。

    REPOS_TEXT: 多行文本，每行 repo=version，用 \n 分隔
    示例: wuji-release validate $'wujihandpy=1.5.0\nwujihandros2=2.0.0'
    """
    text = repos_text.replace("\\n", "\n")
    r = validate_release_input(text)
    if r["ok"]:
        click.echo(r["summary"])
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument("repo")
@click.argument("version")
@click.option("--path", default="CHANGELOG.md", help="CHANGELOG 文件路径")
def fetch(repo, version, path):
    """从 GitHub tag 获取指定仓库某版本的 CHANGELOG 内容。

    示例: wuji-release fetch wujihandpy 1.5.0
    """
    r = fetch_changelog(repo, version, path)
    if r["ok"]:
        click.echo(r["summary"])
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument("repos_text")
@click.option("--date", default="", help="发布日期 YYYY-MM-DD，留空用当天")
@click.option("--dry-run", is_flag=True, default=False, help="仅预览，不创建 PR")
def trigger(repos_text, date, dry_run):
    """触发 release-centralized workflow，批量创建 release PR。

    REPOS_TEXT: 多行文本，每行 repo=version，用 \n 分隔
    示例: wuji-release trigger $'wujihandpy=1.5.0\nwujihandros2=2.0.0' --date 2026-05-01
    """
    text = repos_text.replace("\\n", "\n")
    v = validate_release_input(text)
    if not v["ok"]:
        click.secho(f"❌ 格式校验失败: {v['error']}", fg="red", err=True)
        sys.exit(1)
    click.echo(v["summary"])

    if dry_run:
        click.secho("🧪 Dry run 模式，不会创建 PR", fg="yellow")
    else:
        click.confirm("确认触发正式发布？", abort=True)

    r = trigger_release(text, date, dry_run)
    if r["ok"]:
        click.secho(r["message"], fg="green")
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


@main.command(name="next-version")
@click.argument("repo")
@click.option("--path", default="CHANGELOG.md", help="CHANGELOG 文件路径")
def next_version(repo, path):
    """根据 Unreleased 内容推断下一个版本号。

    示例: wuji-release next-version wujihandpy
    """
    r = suggest_next_version(repo, path)
    if r["ok"]:
        click.echo(r["summary"])
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument("repos", nargs=-1)
def versions(repos):
    """查询各仓库当前已发布的最新版本。

    不指定仓库则查询组织下所有仓库。

    示例: wuji-release versions
            wuji-release versions wujihandpy wujihandros2
    """
    r = get_current_versions(list(repos) if repos else None)
    if r["ok"]:
        click.echo(r["summary"])
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.option("--workflow", default="release-centralized.yml", help="workflow 文件名")
@click.option("--limit", default=5, help="返回最近几条")
def status(workflow, limit):
    """查询最近几次 workflow 运行状态。

    示例: wuji-release status
            wuji-release status --workflow docs-collect-changelogs.yml --limit 3
    """
    r = get_workflow_status(workflow, limit)
    if r["ok"]:
        click.echo(r["summary"])
    else:
        click.secho(f"❌ {r['error']}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
