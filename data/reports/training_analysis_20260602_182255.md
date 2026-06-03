# 训练与分析报告 (20260602_182255)

- 训练集: `C:/Users/ASUS/Desktop/project/data/labels/annotation_combined_for_training.csv`
- 样本数: **29**

## 标签分布

label
positive    12
negative    11
neutral      6

## 来源构成

source
sample    29

## 真实 Hold-out (20%, train_eval.py)

- 测试集样本: 6
- accuracy: 0.6667
- macro F1: 0.5833

## 5-fold CV (LinearSVC, 全量 29 条)

- macro F1: 0.3305
- accuracy: 0.3793

> 数据量小，CV 与 hold-out 波动大，指标仅供基线参考。
