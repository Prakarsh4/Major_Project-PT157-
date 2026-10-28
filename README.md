# Machine Learning-Based Container Placement for Efficient Resource Utilisation

A Kubernetes-based container placement prototype that combines resource-aware scheduling, a Best Fit heuristic, and a Random Forest-based ranking model to explore CPU and memory-aware workload placement.

## Overview

Container orchestration platforms such as Kubernetes manage the deployment of containerised applications across worker nodes. Choosing an appropriate node for an incoming workload requires considering available resources, workload requirements, and placement constraints.

This project implements a local container placement prototype with a web dashboard, a Python backend, a Kind-based Kubernetes cluster, and two placement strategies:

- **Best Fit:** A heuristic-based approach that evaluates candidate worker nodes using CPU and memory resource information.
- **ML Ranker:** A Random Forest-based model that ranks feasible candidate nodes using features derived from resource capacities, availability, workload requests, and utilisation estimates.

The application allows users to submit workloads, inspect cluster information, observe placement decisions, and review recorded placement history.

> **Project status:** Academic prototype for local demonstration and experimentation. Production readiness and large-scale scalability have not been established.

## Objectives

- Demonstrate resource-aware container placement in a Kubernetes environment.
- Check worker-node feasibility against CPU and memory requirements.
- Implement a Best Fit placement baseline.
- Generate a synthetic dataset for candidate-worker placement scenarios.
- Train and integrate a Random Forest-based placement ranker.
- Connect a React dashboard to a FastAPI backend.
- Record placement decisions and evaluate ML decisions against the heuristic baseline.

## Architecture

```text
                 User
                  |
                  v
        React + Vite Dashboard
                  |
                  v
           FastAPI Backend
                  |
          +-------+-------+
          |               |
          v               v
    Resource and      Placement Strategy
    Feasibility       Selection
    Checks            /          \
                    Best Fit    ML Ranker
                                  |
                                  v
                          Trained Random Forest
                                  |
                                  v
                         Eligible Worker Node
                                  |
                                  v
                          Kubernetes API
                                  |
                                  v
                           Pod Deployment
                                  |
                                  v
                       Placement History / UI
```

The diagram represents the high-level workflow. Exact API behaviour and implementation details should be verified against the source code.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React.js, Vite, CSS |
| Backend | Python, FastAPI |
| Container runtime | Docker Desktop |
| Kubernetes environment | Kind |
| Container orchestration | Kubernetes |
| Machine learning | scikit-learn, Random Forest |
| Dataset | Synthetic CSV data |
| Model persistence | Joblib |
| Placement history | CSV |
| Development environment | Visual Studio Code |

## Project Structure

```text
container-placement-project/
├── backend.py
├── placement_engine.py
├── generate_dataset.py
├── train_model.py
├── evaluate_placement.py
├── training_dataset.csv
├── placement_model.joblib
├── placement_history.csv
├── .gitignore
├── README.md
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── index.html
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── App.css
        ├── index.css
        └── main.jsx
```

`placement_history.csv` may be generated locally at runtime and is intentionally excluded from version control. The listing above describes the expected project layout; optional or generated files may differ in your checkout.

## Prerequisites

Install or configure the following before running the application:

- macOS, Linux, or another compatible development environment.
- Python and pip.
- Node.js and npm.
- Docker Desktop or a compatible Docker installation.
- Kind.
- kubectl.

A local Kubernetes cluster is required for actual Kubernetes deployment functionality. Frontend development alone does not require a running cluster.

## Installation and Setup

### 1. Clone the repository

After publishing the repository to GitHub, clone it using your repository URL:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd container-placement-project
```

Replace the placeholder with your actual repository URL.

### 2. Set up the Python environment

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Install the dependencies required by the backend and ML scripts. If a `requirements.txt` file is available:

```bash
pip install -r requirements.txt
```

If no dependency file exists yet, create one after verifying the actual imports and tested package versions. Do not assume this command will work until that file is present.

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Start Docker and Kubernetes

Start Docker Desktop, then verify the installation:

```bash
docker --version
kubectl version --client
kind version
```

Check whether the project cluster already exists:

```bash
kind get clusters
kubectl get nodes
```

If the required `placement-demo` cluster does not exist, create it using the project's verified Kind configuration. For example, if a compatible `cluster.yaml` is included:

```bash
kind create cluster --name placement-demo --config cluster.yaml
```

Do not create a duplicate cluster if the intended cluster already exists.

Verify that the nodes are ready:

```bash
kubectl get nodes
```

## Running the Application

Open two terminals in Visual Studio Code.

### Terminal 1 — Backend

From the project root:

```bash
source .venv/bin/activate
python -m uvicorn backend:app --reload --port 8000
```

If the environment's Python command differs, use the Python executable inside `.venv`.

The backend is expected to be available at:

- API base URL: `http://localhost:8000`
- Interactive API documentation: `http://localhost:8000/docs`

These addresses assume the backend is running locally on the specified port.

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Open the local URL printed by Vite in the terminal, commonly:

`http://localhost:5173`

Keep Docker Desktop, the Kubernetes cluster, and the backend running when using features that depend on live cluster information.

## Dataset and Model

The project uses synthetic training data generated by `generate_dataset.py`.

The dataset represents simulated placement scenarios with candidate worker nodes. Features include resource capacities, free-resource estimates, workload requests, utilisation-related values, and feasibility information. The exact schema should be checked in `training_dataset.csv`.

The dataset's labels are derived from a Best Fit-style heuristic. Consequently, the Random Forest model learns patterns associated with that baseline. Model agreement with Best Fit does not demonstrate that ML is more effective than the heuristic.

### Generate the dataset

```bash
source .venv/bin/activate
python generate_dataset.py
```

**Warning:** Inspect the script before running it if you want to preserve an existing dataset. It may overwrite generated output.

### Train the model

```bash
python train_model.py
```

Check the script's output paths before retraining, since it may replace `placement_model.joblib`.

### Evaluate the model

```bash
python evaluate_placement.py
```

Use the evaluation script and its actual output as the source of truth for reported metrics. Results may change if the dataset, code, or model changes.

## Placement Strategies

### Best Fit

The heuristic evaluates candidate worker nodes based on resource availability and a score derived from post-placement CPU and memory utilisation. Feasibility checks are used to avoid selecting candidates that cannot satisfy the workload's resource requests.

Refer to `placement_engine.py` and `backend.py` for the exact implementation.

### ML Ranker

The Random Forest classifier estimates candidate scores or selection probabilities using resource-related features. The backend uses these scores to rank feasible worker nodes.

The ML Ranker is currently a prototype model trained on synthetic, heuristic-labelled data. It should not be interpreted as an independently validated optimal scheduler.

## Monitoring and Verification

Use Kubernetes commands to inspect the cluster and deployed workloads:

```bash
kubectl get nodes
kubectl get pods -o wide
kubectl top nodes
kubectl top pods -A
```

The `kubectl top` commands require working resource metrics, typically provided by Metrics Server.

A successful Pod creation request does not necessarily mean the Pod has reached the `Running` state. Check actual Pod status and events when troubleshooting:

```bash
kubectl describe pod <POD_NAME>
```

## Evaluation

The project evaluates whether the ML Ranker reproduces the Best Fit baseline's decisions across synthetic scenarios and whether selected candidates satisfy resource-feasibility constraints.

A previously reported evaluation recorded:

- 1,000 complete synthetic scenarios.
- 1,000 feasible winner choices.
- 898 exact matches with Best Fit.
- An 89.80% Best Fit match rate.

These figures should be reported as verified results only after reproducing them with the supplied evaluation code. They measure agreement with the baseline on synthetic scenarios, not proven improvement in real-world resource utilisation.

Further evaluation is needed to establish scalability, generalisation to real workloads, and comparative performance under controlled conditions.

## Limitations

- The Kubernetes environment is a local Kind cluster with two worker nodes.
- The dataset is synthetic rather than collected from a production cluster.
- Training labels are derived from a Best Fit-style heuristic.
- Baseline agreement does not prove ML superiority.
- Production scalability, security, and reliability have not been established.
- Actual results depend on cluster state, resource metrics, configuration, and model version.

## Future Improvements

- Evaluate placement across larger clusters and more diverse workloads.
- Collect representative workload telemetry under an appropriate data-governance process.
- Compare strategies using controlled experiments and consistent metrics.
- Add automated unit, API, and Kubernetes integration tests.
- Improve persistent history storage and error handling.
- Introduce secure deployment configuration and authentication where required.
- Monitor model behaviour and validate retraining procedures.

## Screenshots

Add genuine screenshots of the running application here before publishing the final repository:

1. Main dashboard and worker-node status.
2. Workload submission form.
3. Best Fit placement result.
4. ML Ranker placement result.
5. Placement history.
6. Kubernetes Pod and node verification.

Do not include fabricated screenshots or screenshots containing credentials or other sensitive information.

## Security Notes

- Never commit `.env` files, passwords, tokens, private keys, or kubeconfig credentials.
- Keep virtual environments, dependency directories, caches, and personal configuration out of version control.
- Review `git status` before committing.
- Treat local Kubernetes configurations and logs as potentially sensitive until inspected.
- Do not use the local Metrics Server TLS workaround as a production security configuration.

## Academic Context

**Project:** Machine Learning-Based Container Placement for Efficient Resource Utilisation  
**Institution:** IILM University, Greater Noida, Uttar Pradesh, India  
**Programme:** B.Tech, Computer Science and Engineering  
**Specialisation:** Artificial Intelligence and Machine Learning

## Author

**Student:** Add your name  
**University Roll Number:** Add your roll number

## License

No open-source license has been selected yet. Add a suitable license only after deciding how you want others to use, modify, and distribute the project.

---

*This repository contains an academic prototype intended for learning, demonstration, and further experimentation.*
