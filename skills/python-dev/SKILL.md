---
description: "Python 开发最佳实践与常用模式"
nanobot:
  always: false
  requires:
    bins: ["python3"]
---

# Python 开发技能

## 代码风格

- 使用 `ruff` 进行代码检查和格式化
- 类型注解优先，使用 `mypy` 静态检查
- 函数长度不超过 50 行，单一职责原则

## 常用命令

```bash
# 运行测试
python3 -m pytest tests/ -v

# 代码格式化
ruff format .

# 类型检查
mypy src/

# 安装依赖
pip install -e ".[dev]"
```

## 项目结构建议

```
project/
├── src/
│   └── mypackage/
├── tests/
├── pyproject.toml
└── README.md
```

## 异步编程

使用 `asyncio` 时注意：
- `async def` 函数必须用 `await` 调用
- 并发任务使用 `asyncio.gather()`
- 避免在异步函数中调用阻塞 IO

```python
import asyncio

async def main():
    results = await asyncio.gather(
        task1(),
        task2(),
    )
    return results
```
