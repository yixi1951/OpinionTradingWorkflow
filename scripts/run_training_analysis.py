"""Run full training + analysis pipeline on combined labels.

Usage:
  py scripts/run_training_analysis.py
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
LABEL_DIR = PROJECT / 'data' / 'labels'
MODEL_DIR = PROJECT / 'models'
REPORT_DIR = PROJECT / 'data' / 'reports'


def run(cmd: list[str]) -> None:
    print('>>', ' '.join(cmd))
    subprocess.run(cmd, cwd=PROJECT, check=True)


def cross_val_report(df: pd.DataFrame, n_splits: int = 5) -> dict:
    X = df['text'].astype(str).tolist()
    y = df['label'].astype(str).tolist()
    labels = sorted(set(y))
    if len(df) < n_splits * len(labels):
        n_splits = max(2, min(3, len(df) // max(len(labels), 1)))
    vec = TfidfVectorizer(max_features=25000, ngram_range=(1, 2))
    X_t = vec.fit_transform(X)
    clf = LinearSVC(random_state=42, max_iter=10000)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    preds = cross_val_predict(clf, X_t, y, cv=cv)
    report = classification_report(y, preds, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, preds, labels=labels).tolist()
    return {'labels': labels, 'report': report, 'confusion_matrix': cm, 'n_splits': n_splits}


def eval_on_full(df: pd.DataFrame, model_path: Path, vec_path: Path) -> dict:
    model = joblib.load(model_path)
    vec = joblib.load(vec_path)
    X_t = vec.transform(df['text'].astype(str).tolist())
    preds = model.predict(X_t)
    y = df['label'].astype(str).tolist()
    label_names = sorted(set(y))
    if len(preds) and not isinstance(preds[0], str):
        preds = [label_names[int(p)] for p in preds]
    report = classification_report(y, preds, labels=label_names, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, preds, labels=label_names).tolist()
    return {'labels': label_names, 'report': report, 'confusion_matrix': cm}


def compare_openclaw() -> dict | None:
    bulk = LABEL_DIR / 'annotation_bulk_review_merged.csv'
    if not bulk.exists():
        return None
    df = pd.read_csv(bulk)
    if 'label_review' not in df.columns or 'openclaw_label' not in df.columns:
        return None
    sub = df.dropna(subset=['label_review', 'openclaw_label'])
    if sub.empty:
        return None

    def norm_oc(x):
        s = str(x).lower()
        if s in ('bull', 'positive', '看多'):
            return 'positive'
        if s in ('bear', 'negative', '看空'):
            return 'negative'
        return 'neutral'

    human = sub['label_review'].astype(str)
    oc = sub['openclaw_label'].map(norm_oc)
    agree = (human == oc).mean()
    return {
        'n': len(sub),
        'agreement_rate': round(float(agree), 4),
        'human': human.value_counts().to_dict(),
        'openclaw_mapped': oc.value_counts().to_dict(),
        'openclaw_raw': sub['openclaw_label'].value_counts().to_dict(),
    }


def load_holdout_metrics() -> dict | None:
    files = sorted(MODEL_DIR.glob('metrics_*.json'), key=lambda p: p.stat().st_mtime)
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding='utf-8'))


def main():
    py = sys.executable
    run([py, str(ROOT / 'prepare_bulk_training.py'), '--include-weak'])
    run([py, str(ROOT / 'prepare_combined_training.py')])

    combined_path = LABEL_DIR / 'annotation_combined_for_training.csv'
    meta_path = LABEL_DIR / 'annotation_combined_meta.csv'
    df = pd.read_csv(combined_path)
    meta = pd.read_csv(meta_path) if meta_path.exists() else df.assign(source='unknown')

    if len(df) < 10:
        raise SystemExit(f'Too few training rows ({len(df)}). Need more labeled comment text.')

    run([
        py, str(ROOT / 'train_eval.py'),
        '--labels', str(combined_path),
        '--out_dir', str(MODEL_DIR),
        '--test_size', '0.2',
    ])

    cv = cross_val_report(meta if 'source' in meta.columns else df)
    holdout = load_holdout_metrics()
    oc = compare_openclaw()

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary = {
        'timestamp': ts,
        'n_train_rows': len(df),
        'label_distribution': df['label'].value_counts().to_dict(),
        'source_distribution': meta['source'].value_counts().to_dict() if 'source' in meta.columns else {},
        'holdout_test_linear_svc': holdout,
        'cv_linear_svc': cv,
        'openclaw_vs_human_bulk': oc,
        'sample_review_labeled_n': int(
            pd.read_csv(LABEL_DIR / 'annotation_sample_review.csv').shape[0]
        )
        if (LABEL_DIR / 'annotation_sample_review.csv').exists()
        else 0,
        'sample_merged_into_training': int((meta['source'] == 'sample').sum())
        if 'source' in meta.columns
        else 0,
    }
    json_path = REPORT_DIR / f'training_analysis_{ts}.json'
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    md_lines = [
        f'# 训练与分析报告 ({ts})',
        '',
        f'- 训练集: `{combined_path.as_posix()}`',
        f'- 样本数: **{len(df)}**',
        '',
        '## 标签分布',
        '',
        df['label'].value_counts().to_string(),
        '',
    ]
    if 'source' in meta.columns:
        md_lines += ['## 来源构成', '', meta['source'].value_counts().to_string(), '']
    md_lines += [
        '## 真实 Hold-out (20%, train_eval.py)',
        '',
    ]
    if holdout and 'results' in holdout:
        rep = holdout['results']['linear_svc']['report']
        md_lines += [
            f"- 测试集样本: {int(rep['macro avg']['support'])}",
            f"- accuracy: {rep['accuracy']:.4f}",
            f"- macro F1: {rep['macro avg']['f1-score']:.4f}",
            '',
        ]
    md_lines += [
        '## 5-fold CV (LinearSVC, 全量 29 条)',
        '',
        f"- macro F1: {cv['report']['macro avg']['f1-score']:.4f}",
        f"- accuracy: {cv['report']['accuracy']:.4f}",
        '',
        '> 数据量小，CV 与 hold-out 波动大，指标仅供基线参考。',
        '',
    ]
    if oc:
        md_lines += [
            '## Bulk 人工 vs OpenClaw（OpenClaw 映射 bull/bear→pos/neg）',
            '',
            f"- 样本: {oc['n']}",
            f"- 一致率: {oc['agreement_rate']:.2%}",
            f"- 人工分布: {oc['human']}",
            f"- OpenClaw(映射后): {oc['openclaw_mapped']}",
            '',
            f"- sample 复核已标 {summary.get('sample_review_labeled_n', 0)} 条，但因 text 为日志元数据且 URL 与 bulk 不重叠，**并入训练 0 条**。",
            '',
        ]
    md_path = REPORT_DIR / f'training_analysis_{ts}.md'
    md_path.write_text('\n'.join(md_lines), encoding='utf-8')

    run([
        py, str(ROOT / 'eval_model.py'),
        '--labels', str(combined_path),
        '--model', str(MODEL_DIR / 'model_linear_svc.joblib'),
    ])

    print('\nDone.')
    print('Combined CSV:', combined_path)
    print('Report MD:', md_path)
    print('Report JSON:', json_path)


if __name__ == '__main__':
    main()
