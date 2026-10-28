
import pandas as pd
import joblib
from sklearn.model_selection import GroupShuffleSplit

df = pd.read_csv("training_dataset.csv")
df["scenario_id"] = df.index // 2

saved = joblib.load("placement_model.joblib")
model = saved["model"]
features = saved["features"]

splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.2,
    random_state=42
)

_, test_idx = next(
    splitter.split(df[features], df["selected"], groups=df["scenario_id"])
)

test_df = df.iloc[test_idx].copy()
test_df["score"] = model.predict_proba(test_df[features])[:, 1]

total = 0
feasible_choices = 0
heuristic_matches = 0

for scenario_id, group in test_df.groupby("scenario_id"):
    if len(group) != 2:
        continue

    total += 1

    # Rank both workers by probability of being the heuristic's selected worker.
    ranked = group.sort_values("score", ascending=False)
    chosen = ranked.iloc[0]

    if chosen["feasible"] == 1:
        feasible_choices += 1

    if chosen["selected"] == 1:
        heuristic_matches += 1

print(f"Complete scenarios: {total}")
print(f"Feasible winner choices: {feasible_choices}/{total}")
print(f"Exact Best Fit matches: {heuristic_matches}/{total}")

if total:
    print(f"Feasible choice rate: {feasible_choices / total:.2%}")
    print(f"Best Fit match rate: {heuristic_matches / total:.2%}")
