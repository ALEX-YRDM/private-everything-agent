---
description: "代码审查：系统化 Code Review 流程与常见问题检查清单"
nanobot:
  always: false
---

# 代码审查指南

## 审查优先级

### P0 — 必须修复（阻塞合并）
- 安全漏洞（SQL 注入、XSS、硬编码密钥）
- 数据丢失风险（未处理事务、缺失回滚）
- 明确的 Bug（逻辑错误、空指针未处理）

### P1 — 应当修复
- 性能问题（N+1 查询、不必要的全量加载）
- 错误处理缺失（裸 `except`、未记录异常）
- 测试覆盖不足（核心路径无测试）

### P2 — 建议改进
- 代码可读性（命名不清、函数过长）
- 重复代码（可抽取公共函数）
- 注释缺失（复杂业务逻辑无说明）

## 安全检查清单

```
[ ] 用户输入是否经过验证/转义？
[ ] SQL 查询是否使用参数化（无字符串拼接）？
[ ] API Key / 密码是否通过环境变量注入？
[ ] 敏感数据是否出现在日志中？
[ ] 权限检查是否完整（认证 ≠ 授权）？
[ ] 文件操作是否限制了路径遍历？
[ ] 第三方依赖是否有已知漏洞？
```

## Python 常见问题

```python
# ❌ 可变默认参数陷阱
def add_item(item, lst=[]):  # 所有调用共享同一个 lst
    lst.append(item)
    return lst

# ✅ 正确写法
def add_item(item, lst=None):
    if lst is None:
        lst = []
    lst.append(item)
    return lst

# ❌ 裸 except 吞掉所有异常
try:
    ...
except:
    pass

# ✅ 捕获具体异常并记录
try:
    ...
except ValueError as e:
    logger.error(f"数据格式错误: {e}")
    raise

# ❌ 在循环内查询数据库（N+1）
for user_id in user_ids:
    user = db.get(user_id)   # N 次查询

# ✅ 批量查询
users = db.get_many(user_ids)  # 1 次查询
```

## 审查评论格式

```
[P0] 这里存在 SQL 注入风险，应改用参数化查询：
     db.execute("SELECT * WHERE id = ?", (user_id,))

[P1] 此函数超过 80 行，建议拆分为 process_request() + validate_input()

[P2] 变量名 `d` 不够清晰，建议改为 `user_data`

[NIT] 空行多了一行（非阻塞性建议）

[Q] 这里为什么选择 X 而不是 Y？想了解背景
```

## 自我审查 Checklist（提 PR 前）

```
[ ] 功能是否符合需求描述？
[ ] 是否删除了调试代码（print、TODO、临时注释）？
[ ] 新增的函数/类是否有文档字符串？
[ ] 边界条件（空值、空列表、极大/小数）是否处理？
[ ] 是否添加了对应的测试用例？
[ ] CI 是否通过（lint + test）？
[ ] PR 描述是否清晰说明了"做了什么"和"为什么"？
```
