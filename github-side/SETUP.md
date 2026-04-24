# github-side — GitHub 端部署文件

> 放到每个需要自动化的仓库的 `.github/` 目录下

## 目录结构

```
your-repo/
└── .github/
    └── workflows/
        ├── ci-pr-pipeline.yml    # PR 触发：规范检查 + 调用云服务器 AI Review
        └── release-auto.yml      # Tag 触发：自动创建 GitHub Release
```

## 部署步骤

### 1. 复制 workflow 文件
```bash
# 进入你的项目仓库
cd your-repo
mkdir -p .github/workflows

# 复制 workflow 文件
cp github-side/workflows/*.yml .github/workflows/
```

### 2. 配置仓库 Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `REVIEW_SERVER_URL` | 云服务器地址 | `http://your-server:8080` |
| `REVIEW_TOKEN` | 访问云服务器的 Token | 自定义字符串 |

> `GITHUB_TOKEN` 是 GitHub 自动提供的，不需要手动配置。

### 3. 启用分支保护（建议）

Settings → Branches → Branch protection rules → main：
- ✅ Require status checks to pass before merging
- ✅ Require: `PR Convention Check`, `AI Code Review`
- ✅ Automatically delete head branches

## 工作原理

```
PR 创建/更新
    │
    ├── Job 1: convention-check
    │   └── 检查 PR 标题格式 + 工作项引用
    │
    └── Job 2: ai-review
        └── curl → 你的云服务器 /pr-pipeline
            └── 服务器执行：AI Review + Jira + 飞书
            └── 返回结果 → 评论到 PR
```
