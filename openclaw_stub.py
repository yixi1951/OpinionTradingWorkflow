from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()


class Payload(BaseModel):
    texts: List[str]


POS = ["上涨", "利好", "突破", "增长", "看多", "反弹", "盈利", "强势", "买入", "乐观"]
NEG = ["下跌", "利空", "风险", "暴跌", "看空", "回撤", "亏损", "弱势", "卖出", "悲观"]


@app.post("/api/v1/sentiment")
def sentiment(p: Payload):
    scores = []
    for t in p.texts:
        pos = sum(t.count(w) for w in POS)
        neg = sum(t.count(w) for w in NEG)
        s = (pos - neg) / (pos + neg + 5)
        scores.append(max(-1.0, min(1.0, float(s))))
    return {"scores": scores}
