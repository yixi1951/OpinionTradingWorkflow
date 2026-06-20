# 训练与分析报告 (20260602_182141)

- 训练集: `C:/Users/ASUS/Desktop/project/data/labels/annotation_combined_for_training.csv`
- 样本数: **29**

## 标签分布

label
positive    12
negative    11
neutral      6

## 来源构成

source
bulk    29

## 真实 Hold-out (20%, train_eval.py)

- 测试集样本: 6
- accuracy: 0.5000
- macro F1: 0.2222

## 5-fold CV (LinearSVC, 全量 29 条)

- macro F1: 0.3596
- accuracy: 0.4483

> 数据量小，CV 与 hold-out 波动大，指标仅供基线参考。

## Bulk 人工 vs OpenClaw（OpenClaw 映射 bull/bear→pos/neg）

- 样本: 113
- 一致率: 57.52%
- 人工分布: {'neutral': 61, 'positive': 34, 'negative': 18}
- OpenClaw(映射后): {'neutral': 95, 'positive': 11, 'negative': 7}

- sample 复核已标 29 条，但因 text 为日志元数据且 URL 与 bulk 不重叠，**并入训练 0 条**。
