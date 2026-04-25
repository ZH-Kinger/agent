# GitHub Integration Quickstart

5 分钟把一个业务仓库接入 PR 自动 Review。

## 推荐方式：一条命令初始化

先安装工具，然后在目标业务仓库执行：

```bash
pip install git+https://github.com/ZH-Kinger/agent.git#subdirectory=mcp-server
wuji-review init --server-url http://<服务器IP>:8080 --bootstrap-token <BOOTSTRAP_TOKEN>
```

它会自动：

- 写入 `.github/workflows/ci-pr-pipeline.yml`
- 写入 `.mcp.json`，把 Claude Code 接好
- 检查 `gh auth status`
- 识别当前 GitHub 仓库
- 调服务端 `/bootstrap/register-repo` 申请仓库专属 `REVIEW_TOKEN`
- 在可用时自动写入 `REVIEW_SERVER_URL`、`REVIEW_TOKEN` 到 GitHub Secrets
- 检查服务端 `/health`
- 输出测试 PR 的下一步

如果只想检查接入状态：

```bash
wuji-review doctor --server-url http://<服务器IP>:8080
```

## 你会得到什么

- PR 标题和描述规范检查
- AI Review 自动评论到 PR
- 可选的 Jira 自动建单与飞书通知
- Claude Code 可直接连接 MCP
- 每个仓库自己的 REVIEW_TOKEN

## 前提

- Review Server 已部署并能访问 `GET /health`
- 服务端已配置 `BOOTSTRAP_TOKEN`
- 你拥有目标仓库的 Admin 权限
- 如果要自动写 Secrets，本机已安装并登录 `gh`
- 已拿到两个值：
  - `REVIEW_SERVER_URL`
  - `BOOTSTRAP_TOKEN`

## 手动方式

如果暂时不想用初始化命令，也可以手动操作。

### 第一步：复制 workflow

把下面文件复制到你的业务仓库：

```text
.github/workflows/ci-pr-pipeline.yml
```

来源：`github-side/workflows/ci-pr-pipeline.yml`

### 第二步：配置两个 Secrets

GitHub 仓库 → Settings → Secrets and variables → Actions → Secrets

| Secret | 说明 |
|---|---|
| `REVIEW_SERVER_URL` | 例如 `http://115.191.2.86:8080` |
| `REVIEW_TOKEN` | 通过 `/bootstrap/register-repo` 为当前仓库签发的 token |

如果多个仓库共用同一套服务，依然建议每个仓库使用自己的 `REVIEW_TOKEN`。

### 第三步：提一个测试 PR

建议测试内容：

- PR 标题：`feat: test review pipeline`
- PR 描述包含：`Resolve m-000001`

预期结果：

- `PR Convention Check` 通过
- `AI Code Review` 运行成功
- PR 页面出现 AI 评论

## 失败时先查什么

### 1. workflow 直接失败
优先看：
- Secret 是否缺失
- `REVIEW_SERVER_URL` 是否可访问
- `REVIEW_TOKEN` 是否和当前仓库匹配

### 2. 服务端注册失败
优先看：
- `BOOTSTRAP_TOKEN` 是否正确
- 服务端是否已配置 `REPO_TOKENS_FILE`
- `POST /bootstrap/register-repo` 是否可访问

### 3. 服务器返回 401
说明 token 不一致，或者拿错了别的仓库 token。

### 4. 服务器返回 5xx
先到服务器查看：

```bash
docker logs --tail 200 wuji-review-server
```

## 下一步

- 平台部署与诊断：看 `server-side/SETUP.md`
- Claude Code / MCP 接入：看 `mcp-server/README.md`
- 发版自动化：看 `docs/release-automation.md`
