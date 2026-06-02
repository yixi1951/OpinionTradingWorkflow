"""简单自动标注：基于中文情感词典的启发式标注（供人工复核）

输出: data/labels/annotation_sample_auto.csv，包含建议标签与置信度
"""
from pathlib import Path
import pandas as pd
import re

POS_WORDS = [
    '涨', '上涨', '利好', '买入', '看好', '爆发', '增长', '高', '盈利', '超预期', '利好消息', '回升', '重回', '爆涨'
]
NEG_WORDS = [
    '跌', '下跌', '利空', '卖出', '看空', '下滑', '亏损', '低', '不及', '停牌', '风险', '警惕', '砸盘', '暴跌'
]

TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+")


def score_text(text: str) -> dict:
    if not isinstance(text, str):
        return {'pos': 0, 'neg': 0}
    s = text
    tokens = TOKEN_RE.findall(s)
    joined = ''.join(tokens)
    pos = sum(joined.count(w) for w in POS_WORDS)
    neg = sum(joined.count(w) for w in NEG_WORDS)
    return {'pos': pos, 'neg': neg}


def decide_label(pos: int, neg: int):
    if pos == 0 and neg == 0:
        return 'neutral', 0.0
    diff = pos - neg
    total = pos + neg
    conf = abs(diff) / total
    if diff > 0:
        return 'bull', round(conf, 3)
    elif diff < 0:
        return 'bear', round(conf, 3)
    else:
        return 'neutral', 0.0


def main(infile='data/labels/annotation_sample.csv', out='data/labels/annotation_sample_auto.csv'):
    p = Path(infile)
    if not p.exists():
        print('Input not found:', infile)
        return
    df = pd.read_csv(p)
    if 'text' not in df.columns:
        # try to locate a text-like column
        for c in ['content', 'summary', 'title']:
            if c in df.columns:
                df['text'] = df[c].astype(str)
                break
    if 'text' not in df.columns:
        df['text'] = df.astype(str).agg(' '.join, axis=1)
    outs = []
    for _, row in df.iterrows():
        txt = row.get('text', '')
        sc = score_text(txt)
        label, conf = decide_label(sc['pos'], sc['neg'])
        outs.append({**row.to_dict(), 'auto_label': label, 'auto_confidence': conf, 'pos_count': sc['pos'], 'neg_count': sc['neg']})
    out_df = pd.DataFrame(outs)
    out_df.to_csv(out, index=False, encoding='utf-8-sig')
    print('Wrote', out)


if __name__ == '__main__':
    main()
