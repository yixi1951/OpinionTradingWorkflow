Usage
-----

Fetch and enrich pipeline:

- `scripts/fetch_and_enrich.py`  : fetches `url` for rows in `data/labels/annotation_bulk_openclaw.csv`, extracts article text, caches HTML to `data/raw/html_cache`, and writes enriched CSV to `data/labels/annotation_bulk_enriched_openclaw.csv` (also updates `annotation_bulk_openclaw.csv`).

Run example:

```powershell
.venv\Scripts\python.exe scripts\fetch_and_enrich.py --limit 50 --delay 0.5
```

Notes:
- Requires network access. May fail on sites with anti-bot measures.
- The script uses simple heuristics; manual inspection recommended.
