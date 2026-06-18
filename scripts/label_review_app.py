import streamlit as st
import pandas as pd
from pathlib import Path

DATA_DIR = Path('data/labels')
DEFAULT_FILES = [
    'annotation_bulk.csv',
    'annotation_bulk_openclaw.csv',
    'annotation_bulk_enriched_openclaw.csv',
    'annotation_sample.csv',
    'annotation_sample_openclaw.csv',
    'annotation_sample_auto.csv',
]

REVIEW_BY_SOURCE = {
    'annotation_bulk.csv': 'annotation_bulk_review.csv',
    'annotation_bulk_enriched_openclaw.csv': 'annotation_bulk_review.csv',
    'annotation_bulk_openclaw.csv': 'annotation_bulk_review.csv',
    'annotation_sample.csv': 'annotation_sample_review.csv',
    'annotation_sample_openclaw.csv': 'annotation_sample_review.csv',
    'annotation_sample_auto.csv': 'annotation_sample_review.csv',
}

MERGED_BY_SOURCE = {
    'annotation_bulk.csv': 'annotation_bulk_review_merged.csv',
    'annotation_bulk_enriched_openclaw.csv': 'annotation_bulk_review_merged.csv',
    'annotation_bulk_openclaw.csv': 'annotation_bulk_review_merged.csv',
    'annotation_sample_openclaw.csv': 'annotation_sample_review_merged.csv',
    'annotation_sample.csv': 'annotation_sample_review_merged.csv',
    'annotation_sample_auto.csv': 'annotation_sample_review_merged.csv',
    'annotation_sample.csv': 'annotation_sample_review_merged.csv',
}

st.set_page_config(page_title='Label Review', layout='centered')
st.title('标注 / 复核界面')

st.sidebar.header('配置')
choice = st.sidebar.selectbox('选择数据文件', DEFAULT_FILES, index=0)
path = DATA_DIR / choice
if not path.exists():
    st.sidebar.error(f'文件不存在: {path}')
    st.stop()

shuffle = st.sidebar.checkbox('随机顺序', value=False)
start_idx = st.sidebar.number_input('起始索引 (0-based)', min_value=0, value=0)
only_with_text = st.sidebar.checkbox('仅显示 text 非空', value=False)

review_path = DATA_DIR / REVIEW_BY_SOURCE.get(choice, 'annotation_review.csv')
merged_path = DATA_DIR / MERGED_BY_SOURCE.get(choice, 'annotation_review_merged.csv')


@st.cache_data
def load_df(p, filter_nonempty_text):
    df = pd.read_csv(p)
    if 'id' not in df.columns:
        df = df.reset_index().rename(columns={'index': 'id'})
    if filter_nonempty_text and 'text' in df.columns:
        df = df[df['text'].fillna('').astype(str).str.strip() != ''].reset_index(drop=True)
        df['id'] = range(len(df))
    if 'label' not in df.columns and 'openclaw_label' in df.columns:
        df['label'] = df['openclaw_label']
    return df


df = load_df(str(path), only_with_text)
if shuffle:
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df['id'] = df.index

if review_path.exists():
    review_df = pd.read_csv(review_path)
else:
    review_df = pd.DataFrame(columns=['id', 'label', 'notes', 'annotator'])

n = len(df)
if n == 0:
    st.warning('当前筛选条件下没有样本，请关闭「仅显示 text 非空」或检查数据文件。')
    st.stop()

idx = st.number_input('样本索引', min_value=0, max_value=max(0, n - 1), value=min(int(start_idx), n - 1))
row = df.iloc[int(idx)]
rid = int(row.get('id', idx))

st.markdown('**元信息**')
meta = {
    'id': rid,
    'platform': row.get('platform'),
    'symbol': row.get('symbol'),
    'trade_date': row.get('trade_date'),
    'openclaw_score': row.get('openclaw_score'),
    'openclaw_label': row.get('openclaw_label'),
}
if pd.notna(row.get('url')) and str(row.get('url', '')).strip():
    meta['url'] = row.get('url')
st.write(meta)

if pd.notna(row.get('title')) and str(row.get('title', '')).strip():
    st.markdown('**标题**')
    st.write(row.get('title'))

st.markdown('**文本内容**')
text_val = row.get('text', '')
if pd.isna(text_val) or not str(text_val).strip():
    st.warning('本条 text 为空，可跳过或结合 title/summary 复核。')
st.write(text_val)

existing = review_df[review_df['id'] == rid]
source_label = str(row.get('openclaw_label', row.get('label', '')) or '')
saved_label = existing['label'].iloc[0] if not existing.empty else None
prev_notes = existing['notes'].iloc[0] if not existing.empty else ''
if not isinstance(prev_notes, str):
    prev_notes = ''

label_state_key = f'review_label_{rid}'
if label_state_key not in st.session_state:
    if saved_label in ('positive', 'neutral', 'negative'):
        st.session_state[label_state_key] = saved_label
    elif source_label in ('positive', 'neutral', 'negative'):
        st.session_state[label_state_key] = source_label
    else:
        st.session_state[label_state_key] = 'neutral'

st.markdown('**原始标签 (OpenClaw / 数据文件)**')
st.write(source_label or '—')

st.markdown('**已保存复核标签**')
st.write(saved_label if saved_label else '（尚未保存）')

st.markdown('**复核操作**')
col1, col2, col3 = st.columns(3)
with col1:
    if st.button('Positive', key=f'btn_pos_{rid}'):
        st.session_state[label_state_key] = 'positive'
        st.rerun()
with col2:
    if st.button('Neutral', key=f'btn_neu_{rid}'):
        st.session_state[label_state_key] = 'neutral'
        st.rerun()
with col3:
    if st.button('Negative', key=f'btn_neg_{rid}'):
        st.session_state[label_state_key] = 'negative'
        st.rerun()

st.selectbox(
    '确认标签',
    ['positive', 'neutral', 'negative'],
    key=label_state_key,
)
selected_label = st.session_state[label_state_key]
notes = st.text_area('备注 (可选)', value=prev_notes, key=f'notes_{rid}')
annotator = st.text_input('标注者 ID', value='annotator1', key=f'annotator_{rid}')

if st.button('保存标注', key=f'save_{rid}'):
    review_df = review_df[review_df['id'] != rid]
    review_df = pd.concat(
        [review_df, pd.DataFrame([{'id': rid, 'label': selected_label, 'notes': notes, 'annotator': annotator}])],
        ignore_index=True,
    )
    review_df.to_csv(review_path, index=False)
    st.success(f'已保存: id={rid} → {selected_label}（写入 {review_path.name}）')
    st.rerun()

st.markdown('**导出 / 状态**')
st.write(f'数据源: {choice} | 样本数: {n} | 已复核: {len(review_df)} | 输出: {review_path.name}')

if not review_df.empty:
    if st.button('导出合并 CSV'):
        merged = pd.merge(df, review_df[['id', 'label', 'notes', 'annotator']], on='id', how='left', suffixes=('', '_review'))
        merged.to_csv(merged_path, index=False)
        st.success(f'已写入 {merged_path}')

    csv_bytes = review_df.to_csv(index=False).encode('utf-8')
    st.download_button('下载 review CSV', csv_bytes, file_name=review_path.name, mime='text/csv')

st.markdown('**统计（目前 review）**')
if not review_df.empty:
    st.write(review_df['label'].value_counts())
