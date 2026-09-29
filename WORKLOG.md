# WORKLOG

## Status

- Date: 2026-09-29
- New workshop repo: `packmate-rhoai-35-workshop`
- Reference repo inspected: `https://github.com/Lindagh1/packmate-agent`
- OpenShift authentication: active with provided sandbox token
- GitHub authentication: available as `Lindagh1`

## Phase 1 - Discovery

### Scope update

The original request required OpenShift AI 3.4 only. The live sandbox proved to be
OpenShift AI 3.5.1 on OpenShift 4.20.38. The workshop target is now explicitly
changed to the live validated environment:

- Validated on OpenShift `4.20.38`
- Validated on Red Hat OpenShift AI `3.5.1`

From this point onward, the live 3.5.1 sandbox and official 3.5 documentation are
the source of truth.

### Reference implementation audit

The existing `packmate-agent` repository is a more advanced, production-oriented workshop centered on:

- OpenShift AI project and Workbench
- Gen AI Playground
- shared Llama model in `my-first-model`
- FastAPI backend
- React frontend
- streamable HTTP MCP servers:
  - Weather MCP
  - Baggage Policy MCP
- deterministic evaluation logic
- Tekton / GHCR / PR / Argo CD productionization flow

The new workshop will reuse the strongest existing components while removing participant-facing GitOps and registry complexity from the core path.

### Useful existing components found

#### Application

- Backend entrypoint: `backend/app/main.py`
- React app shell and trip workflow: `frontend/src/App.tsx`
- Structured tool orchestration: `backend/app/agent/tools.py`
- MCP client with retry, timeout, and safe argument filtering:
  `backend/app/tools/mcp_client.py`

#### MCP servers

- Weather MCP:
  `mcp-servers/weather/src/weather_mcp/app.py`
- Baggage Policy MCP:
  `mcp-servers/baggage-policy/src/baggage_policy_mcp/app.py`
- Deterministic baggage rules:
  `backend/app/data/baggage_rules.json`

#### Evaluation

- Deterministic evaluator runner:
  `backend/evals/runner.py`
- Existing evaluation docs:
  `evaluations/README.md`

#### Deployment and automation patterns

- Existing preflight:
  `scripts/preflight-sandbox.sh`
- Existing MCP registration example:
  `deploy/examples/mcp-registration/gen-ai-aa-mcp-servers.yaml`
- Existing troubleshooting and architecture documentation patterns exist and are reusable.

### Important observations about the old workshop

- It is GitOps-heavy and not suitable as the beginner-first participant experience for this redesign.
- The local checkout is already dirty, so it must remain a read-only reference.
- The current participant journey in the old repo includes GitHub fork, GHCR, Tekton, promotion PR, and Argo CD. Those topics should move to optional advanced material in the new workshop.

### Official documentation findings

Source consulted:

- Historical 3.4-era documentation checked only for wording drift:
  `Experimenting with models in the gen AI playground`
- Red Hat OpenShift AI Self-Managed 3.5 documentation:
  - `Experimenting with models in the gen AI playground`
  - `Working with the MCP catalog`
  - `Build AI/Agentic Applications with OGX`
  - `Release notes -> Technology Preview features`

Verified documentation points re-checked for the live 3.5 target:

- The older docs and the live UI both use the navigation label:
  `Gen AI studio -> Playground`
- The older docs and the live UI both use:
  `Gen AI studio -> AI asset endpoints`
- MCP servers for the Playground are platform-configured by a cluster-level `ConfigMap` named:
  `gen-ai-aa-mcp-servers`
- That `ConfigMap` lives in namespace:
  `redhat-ods-applications`
- The docs explicitly describe:
  - Playground
  - Prompt/system instructions
  - Knowledge tab for RAG
  - MCP tab
  - Python code export as a template, not guaranteed runnable code
- The 3.5 Playground documentation still documents platform-level MCP registration
  through `gen-ai-aa-mcp-servers` in `redhat-ods-applications`.
- Gen AI Playground is a Technology Preview feature in OpenShift AI 3.5.
- Custom endpoints are a Technology Preview feature in OpenShift AI 3.5.
- MCP Lifecycle Operator and MCP Catalog are separate OpenShift AI 3.5 features.
- MCP Lifecycle Operator is a Technology Preview feature in OpenShift AI 3.5.
- OGX integration is a Technology Preview feature in OpenShift AI 3.5.

### Preliminary design direction

Current intended workshop flow, subject to live sandbox validation:

1. Meet Packmate
2. Create/open Data Science Project and CPU Workbench
3. Reuse the shared model from the sandbox
4. Use Gen AI Playground
5. Add system instructions
6. Add MCP tools
7. Add RAG only if the live 3.5.1 sandbox supports it reliably without extra heavy infrastructure
8. Move to Python
9. Use integrated Packmate app
10. Run deterministic AI application regression evaluation
11. Close with a short productionization explanation

### Live sandbox discovery

#### Exact platform versions

- `oc version` reports:
  - OpenShift client `4.22.3`
  - OpenShift server `4.20.38`
  - Kubernetes `v1.33.13`
- `oc get clusterversion` reports cluster version:
  `4.20.38`
- `oc whoami` reports current identity:
  `admin`
- `oc auth can-i --list` shows effectively cluster-admin level access for the current token.

#### Exact OpenShift AI version

- `oc get csv -A | rg 'rhods-operator'` shows installed operator version:
  `rhods-operator.3.5.1`
- `oc get datasciencecluster default-dsc -n redhat-ods-applications -o yaml`
  reports:
  - `status.release.version: 3.5.1`
  - `status.release.name: OpenShift AI Self-Managed`
- `oc get dscinitialization default-dsci -n redhat-ods-applications -o yaml`
  also reports:
  - `status.release.version: 3.5.1`

#### Namespaces and major platform components

Relevant namespaces present:

- `redhat-ods-applications`
- `redhat-ods-monitoring`
- `redhat-ods-operator`
- `rhods-notebooks`
- `rhoai-model-registries`
- `my-first-model`
- `nvidia-gpu-operator`

`DataScienceCluster` / `DSCInitialization` status:

- `default-dsc` is `Ready`
- `default-dsci` is `Ready`

Managed components enabled in `default-dsc` include:

- dashboard
- workbenches
- kserve
- modelregistry
- trustyai
- ray
- trainingoperator
- trainer
- feastoperator
- llamastackoperator

Removed / disabled items include:

- aigateway
- mcplifecycleoperator
- mlflowoperator
- modelsAsAService
- kueue
- ogx

Explicit management-state observations from the DSC:

- `llamastackoperator`: `Managed`
- `mcplifecycleoperator`: `Removed`
- `ogx`: `Removed`

#### Dashboard and Gen AI Studio state

`oc get odhdashboardconfig -A -o yaml` confirms:

- `dashboardConfig.genAiStudio: true`
- `dashboardConfig.modelAsService: true`
- `dashboardConfig.disableLMEval: false`
- `dashboardConfig.disableModelCatalog: false`
- `dashboardConfig.disableModelRegistry: false`
- notebook controller enabled with default PVC size `20Gi`

Routes and entry points discovered:

- Dashboard route:
  `https://rhods-dashboard-redhat-ods-applications.apps.ocp.zs8cm.sandbox1073.opentlc.com`
- Data science gateway route:
  `https://data-science-gateway.apps.ocp.zs8cm.sandbox1073.opentlc.com`
- Gen AI related dashboard URL in config:
  `https://rh-ai.apps.ocp.zs8cm.sandbox1073.opentlc.com/`

Running dashboard-adjacent services include:

- `gen-ai-ui`
- `autorag-ui`
- `eval-hub-ui`
- `agent-ops-ui`
- `maas-ui`
- `model-registry-ui`

#### Llama Stack, serving, and shared model architecture

The live sandbox confirms the shared model is served with **KServe plus vLLM**.

Evidence:

- `default-dsc.status.components.kserve.releases` includes:
  - `KServe v0.19.0`
  - `vLLM v0.24.0`
- `llmisvc-controller-manager` pod is running in
  `redhat-ods-applications`
- `llamastackoperator` is set to `Managed` in the DSC spec

Shared model resources in `my-first-model`:

- `InferenceService`:
  `llama-32-3b-instruct`
- `ServingRuntime`:
  `llama-32-3b-instruct`

Live model details from the `InferenceService` and pod spec:

- Model identifier:
  `llama-32-3b-instruct`
- Model artifact:
  `oci://quay.io/redhat-ai-services/modelcar-catalog:llama-3.2-3b-instruct`
- Runtime image:
  `registry.redhat.io/rhaiis/vllm-cuda-rhel9:3.2.4`
- Runtime command:
  `python -m vllm.entrypoints.openai.api_server`
- Tool-calling flags are enabled:
  - `--enable-auto-tool-choice`
  - `--tool-call-parser=llama3_json`
  - llama 3.2 chat template path
- Deployment mode:
  `Standard`
- Resources:
  - requests: `1 CPU`, `6Gi`, `1 GPU`
  - limits: `4 CPU`, `16Gi`, `1 GPU`
- Service endpoints:
  - predictor service:
    `http://llama-32-3b-instruct-predictor.my-first-model.svc.cluster.local`
  - metrics service:
    `llama-32-3b-instruct-metrics`

Actual architecture conclusion:

1. Namespaced `ServingRuntime` runs vLLM.
2. `InferenceService` points to a modelcar OCI artifact for Llama 3.2 3B
   Instruct.
3. Predictor pod contains:
   - vLLM serving container
   - kube-rbac-proxy sidecar
   - modelcar sidecar
   - modelcar init container
4. This is **KServe/vLLM**, not a custom standalone deployment.

#### MCP state

The live sandbox does **not** currently have the Playground MCP
configuration object populated.

Evidence:

- `oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml`
  returns `NotFound`
- however, the platform still created RBAC expecting that object:
  - Role: `gen-ai-aa-mcp-servers-reader`
  - RoleBinding: `gen-ai-aa-mcp-servers-reader-rolebinding`
- the Role grants read access specifically to a ConfigMap named
  `gen-ai-aa-mcp-servers`

Official 3.5 documentation confirms that the supported Playground MCP
registration mechanism is still this same ConfigMap in 3.5.

Additional 3.5.1 discovery:

- No `MCPServer` CRD is installed.
- No MCP Lifecycle Operator pods are running.
- No MCP Catalog-specific dashboard feature flag was found in the live
  `OdhDashboardConfig`.
- No platform `MCPServer` resources exist because the operator is removed.

Conclusion:

- For this sandbox, the simplest supported participant path is:
  1. deploy Packmate MCP servers as ordinary services/routes in the workshop
     namespace
  2. register them for Playground use with the documented 3.5 platform-level
     `gen-ai-aa-mcp-servers` ConfigMap
- MCP Catalog is **not** the chosen path because:
  - it depends on the MCP Lifecycle Operator
  - that operator is disabled in this sandbox
  - enabling it would introduce extra Technology Preview infrastructure that the
    workshop does not need

#### OGX state

Official 3.5 documentation says OGX is relevant in 3.5, but the live sandbox
does not currently expose OGX as an active participant-facing path.

Live findings:

- `ogx` component is `Removed` in the `DataScienceCluster`
- no `OGXServer` CRD is installed
- no OGX operator CSV or pods were discovered
- the shared Llama model is independently served by KServe + ServingRuntime + vLLM

Workshop implication:

- The workshop may include a short conceptual OGX explanation for OpenShift AI 3.5
  terminology alignment
- but the validated hands-on path must **not** depend on deploying or administering
  OGX in this sandbox
- documentation must clearly distinguish:
  - actual validated sandbox path: KServe + vLLM + shared model + Playground
    + MCP ConfigMap registration
  - optional broader 3.5 conceptual architecture where OGX can sit above
    inference, tool, and retrieval providers

#### RAG / knowledge capability state

Live RBAC for `odh-dashboard-gen-ai` shows the Gen AI module can create
namespace-scoped resources for an inline vector database workflow:

- secrets
- services
- persistentvolumeclaims
- configmaps
- deployments
- networkpolicies

Specific resource names granted for lifecycle operations include:

- `genai-pgvector`
- `genai-pgvector-credentials`
- `genai-pgvector-init`
- `genai-pgvector-storage`

This strongly suggests the current live platform RAG path uses a temporary or
participant-namespace `pgvector` deployment rather than a zero-infra shared
RAG backend.

Current cluster state does not show any existing `genai-pgvector` resources,
so RAG is not pre-provisioned for participants.

#### Workbench and image findings

- No participant notebooks currently exist.
- `Workbenches` component is `Ready`.
- Available workbench image streams live in `redhat-ods-applications`, including:
  - `s2i-minimal-notebook`
  - `s2i-generic-data-science-notebook`
  - `pytorch`
  - `tensorflow`
  - `jupyter-pytorch-llmcompressor`
- Several images carry both `3.4` and `3.5` tags, but the installed platform is
  still 3.5.1.

#### Quotas, storage, and GPU observations

- No meaningful participant namespace quotas were discovered from the current
  global quota scan.
- Existing PVCs observed were for platform components, not participant
  workbenches or RAG.
- The shared model consumes `nvidia.com/gpu: 1`, confirming GPUs are active and
  already in use by the shared model.

## Immediate next actions

1. Rename the local repository and docs from `rhoai-34` to `rhoai-35`.
2. Implement workshop preparation using the live 3.5.1 model-serving and
   Playground MCP path.
3. Validate RAG in the live Playground and keep it optional if it requires extra
   infrastructure or proves unreliable.
4. Build docs and screenshots against the actual 3.5.1 UI.

## Phase 2 - Implementation and validation

### Workshop automation status

- Added `Makefile` targets for:
  - `preflight`
  - `prepare-workshop`
  - `verify-workshop`
  - `diagnose`
  - `reset-participant`
  - `cleanup`
- Added live-cluster automation under `scripts/`.
- `make preflight` passes against the current live sandbox.
- `make prepare-workshop` now:
  - builds and deploys the frontend, backend, Weather MCP, and Baggage Policy MCP
  - writes workshop metadata into `packmate-lab`
  - registers both MCP servers into `ConfigMap/gen-ai-aa-mcp-servers`
  - creates edge-terminated TLS routes so Playground and participants can use
    HTTPS endpoints directly

### Verification status

- `make test` passes:
  - backend: `132 passed`
  - weather MCP: `6 passed`
  - baggage MCP: `9 passed`
- `make verify-workshop` now passes every automated check except screenshots.
- Verified live checks now include:
  - shared model endpoint reachability from the deployed backend pod
  - HTTPS reachability for the Packmate frontend route
  - HTTPS reachability for both MCP routes
  - in-cluster Python smoke calls for the model and Packmate app
  - public Packmate SSE route smoke test
  - deterministic evaluator execution from inside the backend container image

### Live behavior adjustments

- The Packmate frontend route now uses edge TLS plus a longer router timeout.
- Public synchronous `/api/v1/chat` calls can still be slower than ideal for a
  browser curl smoke test, but the participant-facing streaming path works and is
  the validated route behavior.
- The deterministic evaluator is now treated as the default beginner exercise.
- The optional live evaluator path now uses the SSE endpoint instead of the
  synchronous endpoint.

### Security and dependency scan

- Tightened the repository secret scan to reduce false positives while still
  failing on obvious credential patterns.
- Ran `pip-audit` after upgrading inherited 3.4-era pins.
- Updated validated Python dependency pins to:
  - `mcp==1.28.1`
  - `json-repair==0.60.1`
- Rebuilt the deployed backend and MCP images after the dependency updates.
- Current Python dependency audit result:
  - backend: no known vulnerabilities
  - weather MCP: no known vulnerabilities
  - baggage MCP: no known vulnerabilities

### Remaining blocker

- Real screenshots and a full browser-based beginner rehearsal remain blocked by
  browser-side authentication to the OpenShift AI web UI.
- CLI-side preparation, deployment, MCP registration, model access, Packmate
  route validation, and deterministic evaluation are all completed.
