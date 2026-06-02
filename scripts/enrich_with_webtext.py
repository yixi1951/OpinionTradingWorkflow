import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path
import time

IN = Path('data/labels/annotation_bulk_openclaw.csv')
OUT = Path('data/labels/annotation_bulk_enriched.csv')

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; OpenClawEnricher/1.0)'}


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    # prefer <article>
    article = soup.find('article')
    if article:
        text = ' '.join(p.get_text(separator=' ', strip=True) for p in article.find_all(['p','div']))
        if len(text) > 50:
            return text
    # fallback: collect all <p>
    ps = [p.get_text(separator=' ', strip=True) for p in soup.find_all('p')]
    joined = ' '.join([p for p in ps if p])
    if len(joined) > 50:
        return joined
    # fallback: find largest text-containing div
    divs = soup.find_all('div')
    best = ''
    best_len = 0
    for d in divs:
        t = d.get_text(separator=' ', strip=True)
        if len(t) > best_len:
            best = t
            best_len = len(t)
    if best_len > 20:
        return best
    # last resort: full body text
    body = soup.get_text(separator=' ', strip=True)
    return body


def main(timeout=6, delay=0.5, max_rows=None):
    if not IN.exists():
        print('Input not found:', IN)
        return
    df = pd.read_csv(IN)
    if df.empty:
        print('No rows')
        return
    out_rows = []
    total = len(df) if max_rows is None else min(max_rows, len(df))
    for i, row in df.head(total).iterrows():
        url = row.get('url', '')
        text0 = row.get('text', '') if 'text' in row.index else ''
        enriched = ''
        status = 'skipped'
        if isinstance(url, str) and url.strip():
            try:
                r = requests.get(url, headers=HEADERS, timeout=timeout)
                if r.status_code == 200 and r.content:
                    enriched = extract_text_from_html(r.text)
                    status = 'ok' if enriched and len(enriched)>20 else 'empty'
                else:
                    status = f'http_{r.status_code}'
            except Exception as e:
                status = f'err:{str(e)[:80]}'
            time.sleep(delay)
        else:
            status = 'no_url'
        # if enrichment is empty, fall back to existing text or title/summary
        if not enriched:
            if text0 and isinstance(text0, str) and len(text0.strip())>10:
                enriched = text0
            else:
                for c in ('content','summary','title'):
                    if c in row.index and isinstance(row[c], str) and len(row[c].strip())>10:
                        enriched = row[c]
                        break
        out = row.to_dict()
        out['text_enriched'] = enriched
        out['enrich_status'] = status
        out_rows.append(out)
        print(i, status)
    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT, index=False, encoding='utf-8-sig')
    print('Wrote', OUT)


if __name__ == '__main__':
    main()
