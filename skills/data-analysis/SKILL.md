---
description: "数据分析：Python pandas/numpy 数据处理与可视化"
nanobot:
  always: false
  requires:
    bins: ["python3"]
---

# 数据分析技能

## 数据探索（EDA）

```python
import pandas as pd
import numpy as np

df = pd.read_csv("data.csv")

# 基础信息
print(df.shape)          # 行列数
print(df.dtypes)         # 数据类型
print(df.head())         # 前5行
df.info()                # 完整信息（含缺失值）
df.describe()            # 数值列统计摘要

# 缺失值分析
df.isnull().sum()
df.isnull().mean() * 100  # 缺失率百分比

# 唯一值
df["category"].value_counts()
df["category"].nunique()
```

## 数据清洗

```python
# 处理缺失值
df.dropna(subset=["key_column"])          # 删除关键列为空的行
df["price"].fillna(df["price"].median())  # 用中位数填充

# 去重
df.drop_duplicates(subset=["id"], keep="last")

# 类型转换
df["date"] = pd.to_datetime(df["date"])
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

# 字符串清理
df["name"] = df["name"].str.strip().str.lower()

# 过滤异常值（IQR 方法）
Q1, Q3 = df["value"].quantile([0.25, 0.75])
IQR = Q3 - Q1
df_clean = df[df["value"].between(Q1 - 1.5*IQR, Q3 + 1.5*IQR)]
```

## 数据聚合

```python
# 分组统计
df.groupby("category")["sales"].agg(["sum", "mean", "count"])

# 透视表
pd.pivot_table(df, values="revenue", index="month",
               columns="product", aggfunc="sum", fill_value=0)

# 时序重采样
df.set_index("date").resample("M")["value"].sum()

# 滚动统计
df["ma7"] = df["price"].rolling(7).mean()   # 7日移动平均
```

## 可视化（matplotlib/seaborn）

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 折线图（时序）
plt.figure(figsize=(12, 5))
plt.plot(df["date"], df["value"], linewidth=1.5)
plt.title("趋势图")
plt.tight_layout()
plt.savefig("trend.png", dpi=150)

# 分布直方图
sns.histplot(df["value"], bins=30, kde=True)

# 相关性热力图
sns.heatmap(df.corr(), annot=True, fmt=".2f", cmap="coolwarm")

# 箱线图（对比分组）
sns.boxplot(x="category", y="value", data=df)
```

## 常用统计检验

```python
from scipy import stats

# T检验（两组均值差异）
t_stat, p_value = stats.ttest_ind(group_a, group_b)
print(f"p-value: {p_value:.4f}")  # < 0.05 则差异显著

# 卡方检验（类别变量关联）
chi2, p, dof, expected = stats.chi2_contingency(contingency_table)

# 相关性
corr, p_val = stats.pearsonr(x, y)   # 线性相关
corr, p_val = stats.spearmanr(x, y)  # 排名相关（非线性）
```

## 报告输出模板

分析完成后按以下结构输出：

1. **数据概况**：行数、字段、时间范围
2. **关键发现**：3-5 条核心结论（用数字支撑）
3. **异常点**：缺失、异常值说明
4. **图表**：保存到工作目录
5. **建议**：基于数据的行动建议
