---
description: "Git 版本控制常用操作与工作流"
nanobot:
  always: false
  requires:
    bins: ["git"]
---

# Git 操作指南

## 查看状态与历史

```bash
git status                          # 查看工作区状态
git log --oneline -20               # 查看最近 20 条提交
git log --graph --oneline --all     # 查看分支图
git diff HEAD~1                     # 查看最近一次提交的改动
git diff --stat                     # 简洁改动统计
```

## 分支操作

```bash
git branch -a                       # 查看所有分支（包括远程）
git checkout -b feature/xxx         # 创建并切换新分支
git merge --no-ff feature/xxx       # 合并分支（保留合并记录）
git rebase main                     # 变基到 main（整理提交历史）
git branch -d feature/xxx           # 删除已合并分支
```

## 提交规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

| type | 含义 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| refactor | 重构（不改变功能） |
| docs | 文档更新 |
| test | 测试相关 |
| chore | 构建/工具变更 |

示例：
```
feat(auth): add JWT token refresh
fix(api): handle 429 rate limit with retry
docs: update API key configuration guide
```

## 撤销与修复

```bash
git restore <file>                  # 丢弃工作区改动
git restore --staged <file>         # 取消暂存
git commit --amend --no-edit        # 修改最后一次提交（未推送时）
git revert <commit>                 # 安全撤销某次提交（生成新提交）
git stash && git stash pop          # 临时保存/恢复工作区
```

## 远程操作

```bash
git remote -v                       # 查看远程地址
git fetch --all                     # 拉取所有远程更新（不合并）
git pull --rebase origin main       # 拉取并变基
git push -u origin HEAD             # 推送当前分支并设置 upstream
git push --force-with-lease         # 安全强推（比 --force 更安全）
```

## 排查问题

```bash
git bisect start / good / bad       # 二分查找引入 Bug 的提交
git blame <file>                    # 查看每行的最后修改者
git log -S "keyword" --source --all # 搜索提交历史中的关键词
```
