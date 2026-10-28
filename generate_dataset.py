
import csv
import random

random.seed(42)

OUTPUT_FILE = "training_dataset.csv"
NUM_SCENARIOS = 5000

rows = []

for _ in range(NUM_SCENARIOS):
    # Simulated worker capacities and current resource usage
    workers = []

    for worker_id in range(2):
        cpu_capacity = 8000
        memory_capacity = 7934

        cpu_used = random.randint(0, 6000)
        memory_used = random.randint(0, 6000)

        workers.append({
            "worker_id": worker_id,
            "cpu_capacity": cpu_capacity,
            "memory_capacity": memory_capacity,
            "cpu_used": cpu_used,
            "memory_used": memory_used,
        })

    # Incoming workload request
    request_cpu = random.choice([100, 250, 500, 750, 1000, 1500, 2000])
    request_memory = random.choice([128, 256, 512, 768, 1024, 1536, 2048])

    candidates = []

    for worker in workers:
        cpu_free = worker["cpu_capacity"] - worker["cpu_used"]
        memory_free = worker["memory_capacity"] - worker["memory_used"]

        if cpu_free < request_cpu or memory_free < request_memory:
            continue

        cpu_after = (worker["cpu_used"] + request_cpu) / worker["cpu_capacity"]
        memory_after = (
            worker["memory_used"] + request_memory
        ) / worker["memory_capacity"]

        # Baseline label: resource-balance heuristic
        score = abs(cpu_after - memory_after)

        candidates.append((score, worker))

    # Skip scenarios where neither worker can fit the workload
    if not candidates:
        continue

    _, chosen = min(candidates, key=lambda item: item[0])

    for worker in workers:
        cpu_free = worker["cpu_capacity"] - worker["cpu_used"]
        memory_free = worker["memory_capacity"] - worker["memory_used"]

        rows.append({
            "worker_id": worker["worker_id"],
            "cpu_capacity_m": worker["cpu_capacity"],
            "memory_capacity_mi": worker["memory_capacity"],
            "cpu_used_m": worker["cpu_used"],
            "memory_used_mi": worker["memory_used"],
            "request_cpu_m": request_cpu,
            "request_memory_mi": request_memory,
            "cpu_free_m": cpu_free,
            "memory_free_mi": memory_free,
            "cpu_util_after": (
                worker["cpu_used"] + request_cpu
            ) / worker["cpu_capacity"],
            "memory_util_after": (
                worker["memory_used"] + request_memory
            ) / worker["memory_capacity"],
            "feasible": int(
                cpu_free >= request_cpu
                and memory_free >= request_memory
            ),
            "selected": int(worker["worker_id"] == chosen["worker_id"]),
        })

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Dataset saved: {OUTPUT_FILE}")
print(f"Scenarios generated: {len(rows) // 2}")
print(f"Training rows: {len(rows)}")
print("Label: selected = 1 means chosen by the resource-balance heuristic.")
