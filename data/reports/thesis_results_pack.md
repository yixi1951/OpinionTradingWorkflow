# 实证成果包（高级配图）

流水线：**采集 → OpenClaw 验真 → Jev/DeepSeek 打分 → FM / Logit**。

当前正式 LLM 打分帖数：**4,080**（jev=131 · deepseek=3,949）。

## 图版

| 图 | 文件 | 内容 |
|----|------|------|
| 01 | `figures/fig01_pipeline.png` | 验真→打分→测评流水线 |
| 02 | `figures/fig02_coverage.png` | 打分覆盖（环形图 + LLM 细分） |
| 03 | `figures/fig03_fm_forest.png` | FM 森林图（±1.96 SE） |
| 04 | `figures/fig04_fm_tstat.png` | Newey–West t 热力图 |
| 05 | `figures/fig05_logit_auc.png` | Logit AUC 分组柱 |
| 06 | `figures/fig06_llm_timeline.png` | 日度 LLM 覆盖强度 |
| 07 | `figures/fig07_dict_vs_llm.png` | 词典分 vs LLM 分散点 |

## 主表摘要

### Q4 文本挖掘日度情绪（sent_llm）

| h | coef | SE | t | n_obs |
|---|------|----|---|-------|
| 1 | 0.0008 | 0.0006 | 1.262 | 1031 |
| 3 | 0.0024 | 0.0020 | 1.163 | 897 |
| 5 | 0.0044 | 0.0029 | 1.512 | 791 |

### Q5 看涨指数（Bullishness）

| h | coef | SE | t | n_obs |
|---|------|----|---|-------|
| 1 | 0.0022 | 0.0018 | 1.238 | 1031 |
| 3 | 0.0061 | 0.0027 | **2.247** | 897 |
| 5 | 0.0036 | 0.0044 | 0.813 | 791 |

### Logit AUC（sent_llm）

| h | AUC | accuracy |
|---|-----|----------|
| 1 | 0.543 | 0.550 |
| 3 | 0.543 | 0.576 |
| 5 | 0.521 | 0.514 |

> Q5 在 h=3 上 Newey–West t 超过约 1.96；Q4 尚未显著。覆盖仍可扩展后再作终表。检验可预测性，不声称因果。  
> Walk-Forward：`data/reports/walk_forward_report.md`（当前样本外偏弱）。
