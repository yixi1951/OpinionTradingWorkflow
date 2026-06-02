"""评估与混淆矩阵绘制脚本

用法：
  python scripts/eval_model.py --labels data/labels/annotation_sample_labeled.csv --model models/model_linear_svc.joblib

输出：classification_report 打印与 confusion_matrix_<model>.png
"""
import argparse
from pathlib import Path
import pandas as pd
import joblib
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--labels', type=str, required=True)
    parser.add_argument('--model', type=str, required=True)
    args = parser.parse_args()

    df = pd.read_csv(args.labels)
    if 'text' not in df.columns or 'label' not in df.columns:
        raise ValueError('labels CSV must contain text,label')
    model = joblib.load(args.model)
    vec = None
    # try to find vectorizer next to model
    vpath = Path(args.model).parent / 'tfidf_vectorizer.joblib'
    if vpath.exists():
        vec = joblib.load(vpath)

    X = df['text'].astype(str).tolist()
    if vec is not None:
        X_t = vec.transform(X)
    else:
        raise RuntimeError('Vectorizer not found at models/tfidf_vectorizer.joblib')

    preds = model.predict(X_t)
    labels = sorted(list(pd.Series(df['label'].astype(str)).unique()))
    # if labels are strings, we need mapping; this script assumes model trained on encoded ints in same order
    print('Classification Report:')
    print(classification_report(df['label'].astype(str).map({l: i for i, l in enumerate(labels)}), preds, target_names=labels))

    cm = confusion_matrix(df['label'].astype(str).map({l: i for i, l in enumerate(labels)}), preds)
    plt.figure(figsize=(6,5))
    sns.heatmap(cm, annot=True, fmt='d', xticklabels=labels, yticklabels=labels, cmap='Blues')
    plt.xlabel('pred')
    plt.ylabel('true')
    out_png = Path(f'confusion_matrix_{Path(args.model).stem}.png')
    plt.savefig(out_png, bbox_inches='tight')
    print('Saved', out_png)

if __name__ == '__main__':
    main()
