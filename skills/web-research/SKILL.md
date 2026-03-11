---
description: "网络信息检索、资料整理与深度研究工作流"
nanobot:
  always: false
---

# 网络研究工作流

## 标准研究流程

遇到需要联网获取信息的任务，按以下步骤执行：

### 第一步：搜索关键词

使用 `web_search` 工具搜索，关键词策略：
- **具体化**：加上时间范围（如 `2025`）、领域限定词
- **多角度**：先搜中文，再搜英文，结果互补
- **来源筛选**：优先 `.gov`、`.edu`、知名媒体（Reuters、Bloomberg、36kr）

```
web_search("XXX 最新进展 2025 site:reuters.com OR site:bloomberg.com")
```

### 第二步：精读重要页面

用 `web_fetch` 获取关键页面全文，抓取重点：
- 数据、统计数字
- 关键结论、观点
- 日期（区分新旧信息）

### 第三步：交叉验证

对重要信息至少找 2 个独立来源确认，标注信息来源和日期。

### 第四步：整理输出

按以下格式组织：
```markdown
## 核心结论
[1-3 句总结]

## 详细信息
[分点或分段]

## 信息来源
- [来源标题](URL) — YYYY-MM-DD
```

## 股票与财经信息

推荐搜索源：
- A股行情：`site:eastmoney.com` 或 `site:10jqka.com.cn`
- 美股行情：`site:finance.yahoo.com` 或 `site:marketwatch.com`
- 财经新闻：`site:reuters.com/finance` 或 `site:bloomberg.com`

常用查询模板：
```
web_search("贵州茅台 股票 今日行情 000858")
web_search("S&P 500 market summary today 2025")
web_search("美联储利率决议 最新 2025")
```

## 新闻聚合

```
web_search("今日国内重要新闻 2025-03-11")
web_search("international news headlines today March 2025")
web_search("科技行业 重要事件 本周")
```

## 注意事项

- 网页抓取结果可能含噪音（广告、导航栏），注意甄别正文
- 财经数据有实效性，注明获取时间
- 分析类文章区分"事实"与"观点"
