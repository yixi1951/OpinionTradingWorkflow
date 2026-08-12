# 研究执行适配器（非交易）

本平台是舆情查询产品。下列适配器只服务研究流水线（纸面回测 / 信号导出），**没有实盘 OMS**。

| 类 | 作用 |
|----|------|
| `PaperBrokerAdapter` | 将研究意图写入 `execution_intents_*.jsonl` |
| `SignalExportAdapter` | CSV 导出供人工阅读 |
| `SandboxBrokerAdapter` | 本地仿真成交，用于内部回测对齐 |

配置：`execution.mode` = `paper` | `export` | `sandbox`。

`get_broker_adapter("live")` 会直接报错，防止误接交易通道。
