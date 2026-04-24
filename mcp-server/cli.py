#!/usr/bin/env python3
"""
wuji-release CLI — 不依赖 Claude，直接在终端操作 Release 流程

用法:
  wuji-release validate "wujihandpy=1.5.0\nwujihandros2=2.0.0"
  wuji-release fetch wujihandpy 1.5.0
  wuji-release trigger "wujihandpy=1.5.0" --date 2026-05-01
  wuji-release trigger "wujihandpy=1.5.0" --dry-run
  wuji-release status
  wuji-release status --workflow docs-collect-changelogs.yml --limit 3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import click
from tools.validate import validate_release_input
from tools.changelog import fetch_unreleased_section
from tools.github_actions import trigger_release, get_workflow_status
from tools.fetch import fetch_changelog
from tools.versions import get_current_versions, suggest_next_version


@click.group()
def main():
    """wuji-release — Release 自动化命令行工具"""


@main.command()
@click.argument("repos_text")
def validate(repos_text):
    """校验 repo=version 格式是否合法。

    REPOS_TEXT: 多行文本，每行 repo=version，用 \\n 分隔
    示例: wuji-release validate $'wujihandpy=1.5.0\\nwujihandros2=2.0.0'
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

    REPOS_TEXT: 多行文本，每行 repo=version，用 \\n 分隔
    示例: wuji-release trigger $'wujihandpy=1.5.0\\nwujihandros2=2.0.0' --date 2026-05-01
    """
    # 先校验
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


@main.command()
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