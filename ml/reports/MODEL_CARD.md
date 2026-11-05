# MODEL CARD (educational learning exercise, auto-generated from a real run)

**Not a medical device. Not diagnostic. Not for screening or any decision about a person.** Synthetic/learning use only.
This model is **not** deployed and **not** connected to the API (`inference_unavailable` remains in force).

## Data
- File: `b_depressed.csv` (not redistributed). **Source, licence and consent basis: UNVERIFIED.**
- 1429 rows, 23 columns, 255 villages (`Ville_id`); positive rate 0.1666.
- Features are household/economic survey fields (assets, expenses, income, family size, age, sex, education).
  They are **not** symptom or questionnaire data. **Target meaning of `depressed` is undocumented** (how it was measured is unknown).
- Nulls: {'no_lasting_investmen': 20}. Duplicate feature rows (ignoring IDs): 45.

## Method
Baselines: logistic regression and random forest, class-weight balanced, 5-fold CV, seed 42.
Two validation schemes: random stratified folds vs **folds grouped by village** (rows from one village never in train and test).

## Results (real run; see `results.json`)
Chance-level PR-AUC equals the positive rate (0.167).

| Model | Scheme | ROC-AUC | PR-AUC | Balanced acc. | Precision@0.5 | Recall@0.5 |
|---|---|---|---|---|---|---|
| logistic_regression | random_stratified_5fold | 0.551 | 0.194 | 0.526 | 0.185 | 0.445 |
| logistic_regression | grouped_by_village_5fold | 0.542 | 0.196 | 0.522 | 0.182 | 0.441 |
| random_forest | random_stratified_5fold | 0.533 | 0.195 | 0.495 | 0.143 | 0.05 |
| random_forest | grouped_by_village_5fold | 0.507 | 0.189 | 0.503 | 0.182 | 0.059 |

## Limitations and Model Gate status
- Gate items NOT satisfied: dataset provenance/licence, target definition, population fit, subgroup analysis, clinical review.
- Leakage risk: households in the same village share/overlap values; compare the two schemes above.
- No threshold, risk category or percentage derived here has any clinical meaning.
