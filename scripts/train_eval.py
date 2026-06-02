"""训练与评估脚本（TF-IDF + SVM / RandomForest），可选 MLflow 记录

用法示例：
  python scripts/train_eval.py --labels data/labels/annotation_sample_labeled.csv --out_dir models --test_size 0.2

输出：
 - models/tfidf_vectorizer.joblib
 - models/model_<name>.joblib
 - metrics_<timestamp>.json (若 MLflow 未安装，保存本地)

依赖：scikit-learn, pandas, joblib, mlflow (可选)
"""
import argparse
import json
from pathlib import Path
import time

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except Exception:
    MLFLOW_AVAILABLE = False


def safe_load_labels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if 'text' not in df.columns or 'label' not in df.columns:
        raise ValueError('labels CSV must contain columns: text,label')
    return df


def train_and_eval(df: pd.DataFrame, out_dir: Path, test_size: float = 0.2, random_state: int = 42):
    out_dir.mkdir(parents=True, exist_ok=True)
    X = df['text'].astype(str).tolist()
    y = df['label'].astype(str).tolist()

    # simple label encoding
    labels = sorted(list(pd.Series(y).unique()))
    label2idx = {l: i for i, l in enumerate(labels)}
    y_enc = [label2idx[x] for x in y]

    X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=test_size, random_state=random_state, stratify=y_enc if len(labels) > 1 else None)

    vec = TfidfVectorizer(max_features=25000, ngram_range=(1,2))
    X_train_t = vec.fit_transform(X_train)
    X_test_t = vec.transform(X_test)

    models = {
        'linear_svc': LinearSVC(random_state=random_state, max_iter=10000),
        'rf': RandomForestClassifier(n_estimators=200, random_state=random_state, n_jobs=-1),
    }

    results = {}

    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train_t, y_train)
        preds = model.predict(X_test_t)
        report = classification_report(y_test, preds, target_names=labels, output_dict=True)
        cm = confusion_matrix(y_test, preds).tolist()
        results[name] = {'report': report, 'confusion_matrix': cm}
        # save model
        joblib.dump(model, out_dir / f"model_{name}.joblib")
        print(f"Saved model_{name}.joblib")

    # save vectorizer
    joblib.dump(vec, out_dir / "tfidf_vectorizer.joblib")
    print("Saved tfidf_vectorizer.joblib")

    meta = {
        'labels': labels,
        'timestamp': int(time.time()),
        'test_size': test_size,
        'n_samples': len(df),
    }

    if MLFLOW_AVAILABLE:
        mlflow.set_experiment('opinion_trading_experiments')
        with mlflow.start_run():
            mlflow.log_params(meta)
            for name, res in results.items():
                # log macro f1
                mlflow.log_metric(f"{name}_macro_f1", res['report']['macro avg']['f1-score'])
            # optionally log models
            for name in models.keys():
                mlflow.sklearn.log_model(models[name], f"model_{name}")
            mlflow.sklearn.log_model(vec, "tfidf_vectorizer")
    else:
        out_path = out_dir / f"metrics_{meta['timestamp']}.json"
        out_path.write_text(json.dumps({'meta': meta, 'results': results}, ensure_ascii=False, indent=2))
        print(f"Wrote metrics to {out_path}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=str, required=True)
    parser.add_argument("--out_dir", type=str, default="models")
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--random_state", type=int, default=42)
    args = parser.parse_args()

    df = safe_load_labels(Path(args.labels))
    res = train_and_eval(df, Path(args.out_dir), test_size=args.test_size, random_state=args.random_state)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
