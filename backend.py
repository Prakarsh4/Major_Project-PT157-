
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
import os
import csv
import joblib
import pandas as pd
from datetime import datetime, timezone

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "placement_history.csv")


def log_placement(pod_name, selected_node, cpu_request, memory_request, strategy, status):
    file_exists = os.path.isfile(HISTORY_FILE)

    with open(HISTORY_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "timestamp",
                "pod_name",
                "selected_node",
                "cpu_request",
                "memory_request",
                "strategy",
                "status"
            ])

        writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            pod_name,
            selected_node,
            cpu_request,
            memory_request,
            strategy,
            status
        ])

MODEL_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "placement_model.joblib"
)

ml_bundle = joblib.load(MODEL_FILE)
ml_model = ml_bundle["model"]
ml_features = ml_bundle["features"]

app = FastAPI(title="Container Placement API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_cluster_config():
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()


def quantity_to_float(value):
    """Convert Kubernetes CPU/memory quantities to a numeric value."""
    if not value:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    try:
        from kubernetes.utils.quantity import parse_quantity
        return float(parse_quantity(str(value)))
    except Exception:
        return 0.0


def cpu_quantity_to_m(value):
    """Convert a Kubernetes CPU quantity (for example, 5m) to millicores."""
    if value is None:
        return None
    try:
        from kubernetes.utils.quantity import parse_quantity
        return float(parse_quantity(str(value))) * 1000
    except Exception:
        return None


def memory_quantity_to_mi(value):
    """Convert a Kubernetes memory quantity to MiB."""
    if value is None:
        return None
    try:
        from kubernetes.utils.quantity import parse_quantity
        return float(parse_quantity(str(value))) / (1024 * 1024)
    except Exception:
        return None

@app.get("/")
def root():
    return {"message": "Container Placement API is running"}


@app.get("/api/history")
def get_history():
    try:
        if not os.path.isfile(HISTORY_FILE):
            return {"success": True, "count": 0, "history": []}

        with open(HISTORY_FILE, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            history = list(reader)

        return {
            "success": True,
            "count": len(history),
            "history": history
        }

    except Exception as exc:
        return {"success": False, "message": str(exc)}



@app.get("/api/cluster")
def get_cluster():
    try:
        load_cluster_config()
        api = client.CoreV1Api()

        nodes = api.list_node().items
        pods = api.list_pod_for_all_namespaces().items

        # Metrics are optional: preserve the cluster response when the API is
        # temporarily unavailable or a particular object has no metric yet.
        custom_api = client.CustomObjectsApi()
        node_metrics = {}
        pod_metrics = {}
        try:
            result = custom_api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="nodes"
            )
            node_metrics = {
                item.get("metadata", {}).get("name"): item.get("usage", {})
                for item in result.get("items", [])
            }
        except Exception:
            pass
        try:
            result = custom_api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="pods"
            )
            pod_metrics = {
                (item.get("metadata", {}).get("namespace"), item.get("metadata", {}).get("name")): item
                for item in result.get("items", [])
            }
        except Exception:
            pass

        workers = []
        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" in labels:
                continue

            name = node.metadata.name
            allocatable = node.status.allocatable or {}
            assigned_pods = [
                pod for pod in pods
                if pod.spec.node_name == name
                and pod.status.phase not in ("Succeeded", "Failed")
            ]

            cpu_requests_m = 0
            memory_requests_mi = 0
            for pod in assigned_pods:
                for container in (pod.spec.containers or []):
                    requests = (
                        container.resources.requests
                        if container.resources and container.resources.requests
                        else {}
                    )
                    cpu = str(requests.get("cpu", "0"))
                    memory = str(requests.get("memory", "0"))

                    if cpu.endswith("m"):
                        cpu_requests_m += quantity_to_float(cpu[:-1])
                    else:
                        cpu_requests_m += quantity_to_float(cpu) * 1000

                    if memory.endswith("Ki"):
                        memory_requests_mi += quantity_to_float(memory[:-2]) / 1024
                    elif memory.endswith("Gi"):
                        memory_requests_mi += quantity_to_float(memory[:-2]) * 1024
                    elif memory.endswith("Mi"):
                        memory_requests_mi += quantity_to_float(memory[:-2])
                    else:
                        memory_requests_mi += quantity_to_float(memory) / (1024 * 1024)

            cpu_total_m = quantity_to_float(allocatable.get("cpu", "0")) * 1000
            memory_total_mi = quantity_to_float(allocatable.get("memory", "0")) / (1024 * 1024)
            node_usage = node_metrics.get(name, {})
            cpu_usage_m = cpu_quantity_to_m(node_usage.get("cpu"))
            memory_usage_mi = memory_quantity_to_mi(node_usage.get("memory"))
            pod_rows = []
            for pod in assigned_pods:
                metric = pod_metrics.get((pod.metadata.namespace, pod.metadata.name))
                containers = metric.get("containers", []) if metric else []
                cpu_values = [
                    cpu_quantity_to_m(container.get("usage", {}).get("cpu"))
                    for container in containers
                ]
                memory_values = [
                    memory_quantity_to_mi(container.get("usage", {}).get("memory"))
                    for container in containers
                ]
                cpu_values = [value for value in cpu_values if value is not None]
                memory_values = [value for value in memory_values if value is not None]
                pod_rows.append({
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "cpu_usage_m": round(sum(cpu_values)) if cpu_values else None,
                    "memory_usage_mi": round(sum(memory_values)) if memory_values else None,
                })

            workers.append({
                "name": name,
                "status": "Ready" if any(
                    condition.type == "Ready" and condition.status == "True"
                    for condition in (node.status.conditions or [])
                ) else "NotReady",
                "cpu_capacity_m": round(cpu_total_m),
                "memory_capacity_mi": round(memory_total_mi),
                "cpu_requests_m": round(cpu_requests_m),
                "memory_requests_mi": round(memory_requests_mi),
                "cpu_usage_m": round(cpu_usage_m) if cpu_usage_m is not None else None,
                "memory_usage_mi": round(memory_usage_mi) if memory_usage_mi is not None else None,
                "pod_count": len(assigned_pods),
                "pods": pod_rows,
            })

        return {
            "cluster": "kind",
            "worker_count": len(workers),
            "workers": workers,
        }

    except Exception as exc:
        return {
            "error": str(exc),
            "hint": "Check that Docker Desktop and the kind cluster are running, and kubectl can access the cluster.",
        }

from pydantic import BaseModel, Field
from datetime import datetime, timezone




class DeployRequest(BaseModel):
    name: str = Field(
        default="demo-workload",
        pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
        max_length=40
    )
    cpu_m: int = Field(default=100, ge=50, le=2000)
    memory_mi: int = Field(default=128, ge=64, le=2048)
    strategy: str = Field(default="Best Fit", pattern=r"^(Best Fit|ML Ranker)$")


@app.get("/api/comparison")
def get_comparison():
    try:
        history = []

        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", newline="") as file:
                reader = csv.DictReader(file)
                history = list(reader)

        comparison = {}

        for strategy in ["Best Fit", "ML Ranker"]:
            records = [
                row for row in history
                if row.get("strategy") == strategy
            ]

            total = len(records)
            successful = sum(
                1 for row in records
                if row.get("status") in ("Created", "Running")
            )

            comparison[strategy] = {
                "total_deployments": total,
                "successful_deployments": successful,
                "success_rate_percent": round(
                    successful / total * 100, 2
                ) if total else 0
            }

        return {
            "success": True,
            "comparison": comparison
        }

    except Exception as exc:
        return {
            "success": False,
            "message": str(exc)
        }


@app.post("/api/deploy")
def deploy_workload(request: DeployRequest):
    try:
        load_cluster_config()
        api = client.CoreV1Api()

        nodes = api.list_node().items
        pods = api.list_pod_for_all_namespaces().items
        candidates = []

        for node in nodes:
            labels = node.metadata.labels or {}
            if "node-role.kubernetes.io/control-plane" in labels:
                continue

            conditions = node.status.conditions or []
            is_ready = any(
                c.type == "Ready" and c.status == "True"
                for c in conditions
            )
            if not is_ready:
                continue

            node_name = node.metadata.name
            allocatable = node.status.allocatable or {}

            def cpu_to_m(value):
                value = str(value or "0")
                return float(value[:-1]) if value.endswith("m") else float(value) * 1000

            def mem_to_mi(value):
                value = str(value or "0")
                if value.endswith("Ki"):
                    return float(value[:-2]) / 1024
                if value.endswith("Mi"):
                    return float(value[:-2])
                if value.endswith("Gi"):
                    return float(value[:-2]) * 1024
                return float(value) / (1024 * 1024)

            cpu_capacity = cpu_to_m(allocatable.get("cpu"))
            memory_capacity = mem_to_mi(allocatable.get("memory"))

            cpu_used = 0.0
            memory_used = 0.0

            for pod in pods:
                if pod.spec.node_name != node_name:
                    continue
                if pod.status.phase in ("Succeeded", "Failed"):
                    continue

                for container in (pod.spec.containers or []):
                    resources = container.resources
                    requests = resources.requests if resources and resources.requests else {}
                    cpu_used += cpu_to_m(requests.get("cpu", "0"))
                    memory_used += mem_to_mi(requests.get("memory", "0"))

            if cpu_capacity - cpu_used < request.cpu_m:
                continue
            if memory_capacity - memory_used < request.memory_mi:
                continue

            
            cpu_after = (cpu_used + request.cpu_m) / cpu_capacity
            memory_after = (memory_used + request.memory_mi) / memory_capacity

            if request.strategy == "ML Ranker":
                features_row = {
                    "cpu_capacity_m": cpu_capacity,
                    "memory_capacity_mi": memory_capacity,
                    "cpu_used_m": cpu_used,
                    "memory_used_mi": memory_used,
                    "request_cpu_m": request.cpu_m,
                    "request_memory_mi": request.memory_mi,
                    "cpu_free_m": cpu_capacity - cpu_used,
                    "memory_free_mi": memory_capacity - memory_used,
                    "cpu_util_after": cpu_after,
                    "memory_util_after": memory_after,
                    "feasible": 1,
                }
                candidates.append(
                    (features_row, node_name)
                )
            else:
                score = abs(cpu_after - memory_after)
                candidates.append((score, node_name))


        if not candidates:
            return {
                "success": False,
                "message": "No Ready worker has enough requested CPU and memory."
            }

        
        if request.strategy == "ML Ranker":
            candidate_features = pd.DataFrame(
                [item[0] for item in candidates],
                columns=ml_features
            )
            probabilities = ml_model.predict_proba(candidate_features)
            positive_index = list(ml_model.classes_).index(1)

            selected_index = max(
                range(len(candidates)),
                key=lambda i: probabilities[i][positive_index]
            )
            _, selected_node = candidates[selected_index]
        else:
            _, selected_node = min(candidates, key=lambda item: item[0])

        pod_name = f"{request.name}-{datetime.now(timezone.utc).strftime('%H%M%S')}"

        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                labels={"app": "placement-demo"}
            ),
            spec=client.V1PodSpec(
                node_selector={"kubernetes.io/hostname": selected_node},
                containers=[
                    client.V1Container(
                        name="nginx",
                        image="nginx:alpine",
                        ports=[client.V1ContainerPort(container_port=80)],
                        resources=client.V1ResourceRequirements(
                            requests={
                                "cpu": f"{request.cpu_m}m",
                                "memory": f"{request.memory_mi}Mi"
                            },
                            limits={
                                "cpu": f"{min(request.cpu_m * 2, 4000)}m",
                                "memory": f"{min(request.memory_mi * 2, 4096)}Mi"
                            }
                        )
                    )
                ]
            )
        )

        api.create_namespaced_pod(namespace="default", body=pod)
        try:
            log_placement(
        pod_name=pod_name,
        selected_node=selected_node,
        cpu_request=f"{request.cpu_m}m",
        memory_request=f"{request.memory_mi}Mi",
        strategy=request.strategy,
        status="Created"
    )
        except Exception as log_error:
            print(f"CSV logging failed: {log_error}")

        return {
            "success": True,
            "pod": pod_name,
            "selected_node": selected_node,
            "cpu_request": f"{request.cpu_m}m",
            "memory_request": f"{request.memory_mi}Mi",
            "strategy": request.strategy
        }

    except Exception as exc:
        return {"success": False, "message": str(exc)}
