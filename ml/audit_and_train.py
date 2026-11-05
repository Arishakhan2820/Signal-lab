"""OFFLINE ML learning exercise (educational). Not wired into the API. Not clinical.
Dataset: b_depressed.csv (obtained separately; provenance/licence UNVERIFIED, so it is not committed).
Run:  python ml/audit_and_train.py   -> writes ml/reports/results.json and ml/reports/MODEL_CARD.md"""
import json
import pathlib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

ROOT = pathlib.Path(__file__).parent
SEED = 42
df = pd.read_csv(ROOT / "data" / "b_depressed.csv")
y = df["depressed"].to_numpy()
groups = df["Ville_id"].to_numpy()
X = df.drop(columns=["depressed", "Survey_id", "Ville_id"])

audit = {
    "rows": int(len(df)), "columns": int(df.shape[1]),
    "villages": int(df["Ville_id"].nunique()),
    "positive_rate": round(float(y.mean()), 4),
    "null_cells_by_column": {k: int(v) for k, v in df.isna().sum().items() if v},
    "duplicate_rows_excluding_ids": int(X.assign(y=y).duplicated().sum()),
    "rows_per_village_median": float(df.groupby("Ville_id").size().median()),
}
multi = df.groupby("Ville_id").filter(lambda g: len(g) > 1)
audit["share_of_multirow_villages_with_identical_asset_values"] = round(float(
    (multi.groupby("Ville_id")["durable_asset"].nunique() == 1).mean()), 3)

models = {
    "logistic_regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                         LogisticRegression(max_iter=2000, class_weight="balanced")),
    "random_forest": make_pipeline(SimpleImputer(strategy="median"),
                                   RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample",
                                                          min_samples_leaf=3, random_state=SEED, n_jobs=-1)),
}


def cv(model, splitter, **kw):
    prob = np.zeros(len(y))
    for tr, te in splitter.split(X, y, **kw):
        m = __import__("sklearn.base", fromlist=["clone"]).clone(model).fit(X.iloc[tr], y[tr])
        prob[te] = m.predict_proba(X.iloc[te])[:, 1]
    pred = (prob >= 0.5).astype(int)
    return {"roc_auc": round(roc_auc_score(y, prob), 3), "pr_auc": round(average_precision_score(y, prob), 3),
            "balanced_accuracy": round(balanced_accuracy_score(y, pred), 3),
            "precision@0.5": round(precision_score(y, pred, zero_division=0), 3),
            "recall@0.5": round(recall_score(y, pred), 3)}


results = {"seed": SEED, "audit": audit,
           "baseline_pr_auc_if_random": round(float(y.mean()), 3), "models": {}}
for name, model in models.items():
    results["models"][name] = {
        "random_stratified_5fold": cv(model, StratifiedKFold(5, shuffle=True, random_state=SEED)),
        "grouped_by_village_5fold": cv(model, GroupKFold(5), groups=groups),
    }
(ROOT / "reports" / "results.json").write_text(json.dumps(results, indent=2))

card = f"""# MODEL CARD (educational learning exercise, auto-generated from a real run)

**Not a medical device. Not diagnostic. Not for screening or any decision about a person.** Synthetic/learning use only.
This model is **not** deployed and **not** connected to the API (`inference_unavailable` remains in force).

## Data
- File: `b_depressed.csv` (not redistributed). **Source, licence and consent basis: UNVERIFIED.**
- {audit['rows']} rows, {audit['columns']} columns, {audit['villages']} villages (`Ville_id`); positive rate {audit['positive_rate']}.
- Features are household/economic survey fields (assets, expenses, income, family size, age, sex, education).
  They are **not** symptom or questionnaire data. **Target meaning of `depressed` is undocumented** (how it was measured is unknown).
- Nulls: {audit['null_cells_by_column']}. Duplicate feature rows (ignoring IDs): {audit['duplicate_rows_excluding_ids']}.

## Method
Baselines: logistic regression and random forest, class-weight balanced, 5-fold CV, seed {SEED}.
Two validation schemes: random stratified folds vs **folds grouped by village** (rows from one village never in train and test).

## Results (real run; see `results.json`)
Chance-level PR-AUC equals the positive rate ({results['baseline_pr_auc_if_random']}).

| Model | Scheme | ROC-AUC | PR-AUC | Balanced acc. | Precision@0.5 | Recall@0.5 |
|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {n} | {sch} | {m['roc_auc']} | {m['pr_auc']} | {m['balanced_accuracy']} | {m['precision@0.5']} | {m['recall@0.5']} |"
    for n, v in results["models"].items() for sch, m in v.items()) + """

## Limitations and Model Gate status
- Gate items NOT satisfied: dataset provenance/licence, target definition, population fit, subgroup analysis, clinical review.
- Leakage risk: households in the same village share/overlap values; compare the two schemes above.
- No threshold, risk category or percentage derived here has any clinical meaning.
"""
(ROOT / "reports" / "MODEL_CARD.md").write_text(card)
print(json.dumps(results, indent=2))
