"""Exports REAL cross-validated numbers for the demo page (web-demo). Run: python ml/export_demo_data.py"""
import json, pathlib, numpy as np, pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
R = pathlib.Path(__file__).parent
df = pd.read_csv(R / "data/b_depressed.csv"); y = df.depressed.values
X = df.drop(columns=["depressed", "Survey_id", "Ville_id"])
m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
p = np.zeros(len(y))
for tr, te in GroupKFold(5).split(X, y, groups=df.Ville_id.values):
    p[te] = clone(m).fit(X.iloc[tr], y[tr]).predict_proba(X.iloc[te])[:, 1]
fpr, tpr, _ = roc_curve(y, p); idx = np.linspace(0, len(fpr) - 1, 28).astype(int)
thr = []
for t in np.quantile(p, np.linspace(.05, .95, 19)):
    f = p >= t; thr.append([round(float(t), 3), int((f & (y == 1)).sum()), int((f & (y == 0)).sum()), int((~f & (y == 1)).sum()), int((~f & (y == 0)).sum())])
order = np.argsort(-p); lift = {str(k): round(float(y[order[:int(len(y) * k / 100)]].sum() / y.sum()), 3) for k in (10, 20, 30, 50)}
hist = {}
for c in ("Age", "Number_children", "education_level", "total_members"):
    b = np.linspace(df[c].min(), df[c].max(), 11)
    hist[c] = dict(lo=float(b[0]), hi=float(b[-1]), c0=np.histogram(df[c][y == 0], b)[0].tolist(), c1=np.histogram(df[c][y == 1], b)[0].tolist())
res = json.load(open(R / "reports/results.json"))["models"]
out = dict(roc=[[round(float(fpr[i]), 3), round(float(tpr[i]), 3)] for i in idx], thr=thr, lift=lift, hist=hist,
           cls=[int((y == 0).sum()), int((y == 1).sum())], cmp=res)
(R / "demo_data.json").write_text(json.dumps(out, separators=(",", ":"))); print("ok", len(json.dumps(out)), "bytes", lift)
