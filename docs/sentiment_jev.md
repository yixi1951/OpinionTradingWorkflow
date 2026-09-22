# TypeSafe Jev sentiment cascade

Live A-share social sentiment uses this failover order (configurable):

1. **Jev** (`POST https://api.typesafe.ai/v1/systemone`) when `TYPESAFE_API_KEY` or `JEV_API_KEY` is set
2. **DeepSeek** → optional **Qwen** (existing `llm_failover`)
3. **Keyword** lexicon (always available; sole path when `SCORING_MODE=keyword`)

## Configuration

| Variable | Purpose |
|----------|---------|
| `SCORING_MODE` | `ai` / `jev` / `hybrid` = live cascade; `keyword` = offline (CI) |
| `SCORING_PROVIDER` | Override order, e.g. `jev,deepseek,keyword` |
| `config/settings.yaml` → `scoring.provider` | Default chain when env unset |
| `TYPESAFE_API_KEY` / `JEV_API_KEY` | Jev auth |
| `JEV_MODEL` / `TYPESAFE_MODEL` | Model pin (`jev-latest` default) |
| `JEV_MIN_CONFIDENCE` | Below threshold → DeepSeek (default `0.40`) |
| `JEV_FALLBACK` | `0` disables failover on HTTP/parse errors |

## Scalar mapping

Each post is one Jev call with a single **score** question (5 ordered levels, indices `0..4`):

| Index | Rubric (zh) | Scalar |
|-------|-------------|--------|
| 0 | 强烈看空 | -1.0 |
| 1 | 偏空 | -0.5 |
| 2 | 中性 | 0.0 |
| 3 | 偏多 | +0.5 |
| 4 | 强烈看多 | +1.0 |

Jev returns a probability-weighted mean index `s`; we map  
`scalar = clamp(2 * s / (n - 1) - 1)` with `n = 5`.

Results expose `source="jev"` on `SentimentResult` / pipeline `score_source` for UI and logs.
