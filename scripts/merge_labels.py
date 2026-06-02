import pandas as pd
from pathlib import Path


def cohen_kappa(y1, y2, categories=None):
    # compute Cohen's kappa without sklearn
    if categories is None:
        cats = sorted(set(y1.dropna().unique()) | set(y2.dropna().unique()))
    else:
        cats = categories
    cat_idx = {c: i for i, c in enumerate(cats)}
    n = len(y1)
    # build confusion matrix
    import numpy as np

    mat = np.zeros((len(cats), len(cats)), dtype=int)
    valid = 0
    for a, b in zip(y1, y2):
        if pd.isna(a) or pd.isna(b):
            continue
        ia = cat_idx.get(a, None)
        ib = cat_idx.get(b, None)
        if ia is None or ib is None:
            continue
        mat[ia, ib] += 1
        valid += 1
    if valid == 0:
        return None, 0
    obs = np.trace(mat) / valid
    row_marg = mat.sum(axis=1) / valid
    col_marg = mat.sum(axis=0) / valid
    exp = (row_marg * col_marg).sum()
    if exp == 1.0:
        return None, valid
    kappa = (obs - exp) / (1 - exp)
    return kappa, valid


def map_to_category(score, pos_thresh=0.2, neg_thresh=-0.2):
    try:
        if pd.isna(score):
            return "neutral"
        s = float(score)
    except Exception:
        return str(score)
    if s > pos_thresh:
        return "positive"
    if s < neg_thresh:
        return "negative"
    return "neutral"


def main():
    root = Path("data/labels")
    human_path = root / "annotation_sample.csv"
    openclaw_path = root / "annotation_sample_openclaw.csv"
    out_merged = root / "annotation_sample_merged.csv"
    out_consensus = root / "annotation_sample_labeled.csv"

    human = pd.read_csv(human_path)
    openc = pd.read_csv(openclaw_path)

    # Ensure id exists
    if "id" not in human.columns:
        human = human.reset_index().rename(columns={"index": "id"})
    if "id" not in openc.columns:
        openc = openc.reset_index().rename(columns={"index": "id"})

    merged = pd.merge(human, openc[["id", "openclaw_score", "openclaw_label"]], on="id", how="inner")

    merged["human_label_cat"] = merged["label"].apply(map_to_category)
    if "openclaw_label" not in merged.columns:
        merged["openclaw_label"] = merged["openclaw_score"].apply(map_to_category)

    # Cohen's Kappa (categorical)
    y1_cat = merged["human_label_cat"]
    y2_cat = merged["openclaw_label"]
    kappa, n = cohen_kappa(y1_cat, y2_cat, categories=["negative", "neutral", "positive"])
    if kappa is None:
        print("No overlapping categorical labels to compute kappa.")
    else:
        print(f"Cohen's kappa: {kappa:.4f} (n={n})")

    merged.to_csv(out_merged, index=False)

    # consensus: use human when available, otherwise openclaw; mark conflicts
    def consensus_row(row):
        if row["human_label_cat"] == row["openclaw_label"]:
            return row["human_label_cat"]
        return "conflict"

    merged["consensus_label"] = merged.apply(consensus_row, axis=1)
    merged.to_csv(out_merged, index=False)
    merged[["id", "platform", "symbol", "text", "label", "human_label_cat", "openclaw_score", "openclaw_label", "consensus_label"]].to_csv(out_consensus, index=False)

    print(f"Wrote merged -> {out_merged}\nWrote consensus labeled -> {out_consensus}")


if __name__ == "__main__":
    main()
