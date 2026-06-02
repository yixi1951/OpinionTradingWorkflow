from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.dummy import DummyClassifier
import joblib

root = Path('data/labels')
labels_file = root / 'annotation_sample_for_training.csv'
out_dir = Path('models')
out_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(labels_file)
if 'text' not in df.columns or 'label' not in df.columns:
    raise SystemExit('labels CSV must contain text,label')

label_counts = df['label'].value_counts()
print('Label counts:')
print(label_counts)

X = df['text'].astype(str).tolist()
y = df['label'].astype(str).tolist()

vec = TfidfVectorizer(max_features=25000, ngram_range=(1,2))
X_t = vec.fit_transform(X)

if label_counts.shape[0] < 2:
    print('Only one class detected — training DummyClassifier majority predictor')
    clf = DummyClassifier(strategy='most_frequent')
    clf.fit(X_t, y)
    joblib.dump(clf, out_dir / 'model_dummy_majority.joblib')
    joblib.dump(vec, out_dir / 'tfidf_vectorizer.joblib')
    print('Saved dummy model and vectorizer to models/')
else:
    print('Multiple classes present — please use scripts/train_eval.py')
