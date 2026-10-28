
import pandas as pd
import joblib

from sklearn.model_selection import GroupShuffleSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

DATA_FILE = "training_dataset.csv"
MODEL_FILE = "placement_model.joblib"

df = pd.read_csv(DATA_FILE)
df["scenario_id"] = df.index // 2

features = [
    "cpu_capacity_m",
    "memory_capacity_mi",
    "cpu_used_m",
    "memory_used_mi",
    "request_cpu_m",
    "request_memory_mi",
    "cpu_free_m",
    "memory_free_mi",
    "cpu_util_after",
    "memory_util_after",
    "feasible",
]

X = df[features]
y = df["selected"]
groups = df["scenario_id"]

splitter = GroupShuffleSplit(
    n_splits=1,
    test_size=0.2,
    random_state=42
)

train_idx, test_idx = next(
    splitter.split(X, y, groups=groups)
)

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=12,
    min_samples_leaf=2,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

predictions = model.predict(X_test)

print(f"Training rows: {len(train_idx)}")
print(f"Test rows: {len(test_idx)}")
print(f"Row-level accuracy: {accuracy_score(y_test, predictions):.2%}")
print("\nClassification report:")
print(classification_report(y_test, predictions, zero_division=0))

joblib.dump(
    {"model": model, "features": features},
    MODEL_FILE
)

print(f"\nModel saved to: {MODEL_FILE}")
