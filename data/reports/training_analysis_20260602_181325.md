# 训练与分析报告 (20260602_181325)

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

## Hold-out 测试 (LinearSVC, 20%)

- accuracy: 0.8966
- macro F1: 0.8993

## CV (LinearSVC, 全量)

- macro F1: 0.3596
- accuracy: 0.4483

## Bulk 人工 vs OpenClaw

- 样本: 113
- 一致率: 47.79%
- 人工分布: {'neutral': 61, 'positive': 34, 'negative': 18}
- OpenClaw分布: {'neutral': 95, 'bull': 11, 'bear': 7}
