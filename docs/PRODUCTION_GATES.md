# 产品边界：舆情查询平台

本仓库对外产品定位为 **A 股舆情查询与研究辅助**，不是交易系统。

## 产品范围内

| 能力 | 说明 |
|------|------|
| 研究工作台 | 总览、自选、舆情证据、系统状态 |
| 用户中心 | 注册 / 登录 / 邮箱验证 / 密码找回 |
| RBAC | `viewer` / `analyst` / `admin` |
| 持久化 | SQLite 默认；可选 PostgreSQL |
| 研究流水线 | 采集 → 打分 → 聚合 → 报告（内部可含纸面回测） |

## 明确不包含

- 真实下单 / OMS / 券商对接
- 订单审批、成交回报、实盘对账
- `trader` 角色与 `/v1/trading/*` API

内部 `PaperBrokerAdapter` / sandbox 仅用于研究回测与信号导出，不对用户开放交易。

## 运维

```powershell
$env:PYTHONPATH = "src"
python scripts/ops_drill.py
python scripts/smtp_probe.py --to you@example.com
```
