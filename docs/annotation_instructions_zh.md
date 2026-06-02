标注说明（中文）

目标：对采集到的帖子进行情感三分类标注：看多（bull）、看空（bear）、中性（neutral）。

字段说明：
- id: 标注行编号
- platform: 数据来源平台（如 xueqiu, weibo, douyin 等）
- symbol: 涉及的股票代码（若无可留空）
- trade_date: 帖子日期
- text: 帖子文本（需足够展示给标注者）
- label: 标注结果，取值之一：`bull` / `bear` / `neutral`（标注时填写）
- notes: 可选，标注者备注

标注规则（简要）:
1. Bull（看多）: 表达明确看涨或利好预期的文本，例如建议买入、预期股价上涨、积极的产品/业绩预期等。
2. Bear（看空）: 表达明确看空或利空预期的文本，例如建议卖出、预期股价下跌、负面新闻/质疑等。
3. Neutral（中性）: 既不明显看多也不明显看空，或仅为信息性描述、转发、疑问、无情绪倾向的评论。

注意事项:
- 若文本同时包含正负倾向，判断作者整体语气倾向为准。
- 对于显然非金融讨论或无关内容，可标为 `neutral` 并在 `notes` 中标注理由。
- 标注时请尽量保持一致，遇到模糊情况可先标 `neutral`。

流程建议：
1. 使用 `scripts/sample_annotation.py` 抽取样本 CSV（默认 100 条）到 `data/labels/annotation_sample.csv`。
2. 在本地使用 Excel/Google Sheets 打开，填写 `label` 列并保存为 CSV。建议两位标注者独立标注并计算 Cohen's Kappa。
3. 返回到仓库后，运行评估脚本合并标注并生成训练/测试集。

标注示例行（CSV 列顺序）:
id,platform,symbol,trade_date,text,label,notes

文件位置：`data/labels/annotation_sample.csv`（由抽样脚本生成）
