# 实证成果包（高级配图）

流水线：**采集 → OpenClaw 验真 → Jev/DeepSeek 打分 → FM / Logit**。

当前正式 LLM 打分帖数：**3,780**（jev=131 · deepseek=3,649）。

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

## 主表摘要（Q4 sent_llm）

| h | coef | SE | t | n_obs |
|---|------|----|---|-------|
| 1 | 0.0007 | 0.0006 | 1.242 | 1031 |
| 3 | 0.0022 | 0.0020 | 1.103 | 897 |
| 5 | 0.0043 | 0.0028 | 1.516 | 791 |

### Logit AUC

| h | AUC | accuracy |
|---|-----|----------|
| 1 | 0.543 | 0.552 |
| 3 | 0.544 | 0.573 |
| 5 | 0.520 | 0.514 |

> 样本级 LLM 覆盖下系数可能不显著；扩大 Jev/DS 后再作终表解读。检验可预测性，不声称因果。
