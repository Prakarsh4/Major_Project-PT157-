from datetime import datetime, timezone

from kubernetes import client, config
from kubernetes.utils.quantity import parse_quantity


def cpu_cores(value):
    value = str(value)
    if value.endswith("m"):
        return float(value[:-1]) / 1000
    return float(parse_quantity(value))


def memory_bytes(value):
    return float(parse_quantity(str(value)))


def pod_requests(pod):
    cpu = 0.0
    memory = 0.0

    # Sum regular container requests.
    for container in (pod.spec.containers or []):
        requests = container.resources.requests or {}
        cpu += cpu_cores(requests.get("cpu", "0"))
        memory += memory_bytes(requests.get("memory", "0"))

    return cpu, memory


def main():
    config.load_kube_config()
    api = client.CoreV1Api()

    nodes = api.list_node().items
    pods = api.list_pod_for_all_namespaces().items

    candidates = []

    for node in nodes:
        name = node.metadata.name

        # Only use worker nodes, not the control-plane.
        if "node-role.kubernetes.io/control-plane" in (
            node.metadata.labels or {}
        ):
            continue

        allocatable = node.status.allocatable
        cpu_total = cpu_cores(allocatable["cpu"])
        memory_total = memory_bytes(allocatable["memory"])

        cpu_used = 0.0
        memory_used = 0.0

        for pod in pods:
            if pod.spec.node_name != name:
                continue
            if pod.status.phase in ("Succeeded", "Failed"):
                continue

            cpu_req, memory_req = pod_requests(pod)
            cpu_used += cpu_req
            memory_used += memory_req

        cpu_free = cpu_total - cpu_used
        memory_free = memory_total - memory_used

        print(
            f"{name}: free CPU={cpu_free:.2f} cores, "
            f"free memory={memory_free / (1024**2):.0f} Mi"
        )

        # Requested resources for the new workload.
        request_cpu = 0.1
        request_memory = 128 * 1024**2

        if cpu_free < request_cpu or memory_free < request_memory:
            continue

        # Best-fit score: prefer balanced remaining CPU/memory capacity.
        cpu_after = (cpu_used + request_cpu) / cpu_total
        memory_after = (memory_used + request_memory) / memory_total
        score = abs(cpu_after - memory_after)

        candidates.append((score, name))

    if not candidates:
        print("No worker has enough allocatable CPU and memory.")
        return

    _, selected_node = min(candidates, key=lambda item: item[0])

    pod_name = "placement-demo-" + datetime.now(
        timezone.utc
    ).strftime("%H%M%S")

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
                        requests={"cpu": "100m", "memory": "128Mi"},
                        limits={"cpu": "250m", "memory": "256Mi"}
                    )
                )
            ]
        )
    )

    print(f"\nBest-fit selected: {selected_node}")
    print(f"Creating real Kubernetes Pod: {pod_name}")

    api.create_namespaced_pod(namespace="default", body=pod)

    print("\nPod submitted. Verify placement with:")
    print("kubectl get pods -o wide")


if __name__ == "__main__":
    main()
