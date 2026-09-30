# Troubleshooting

## `oc whoami` shows a ServiceAccount

**SYMPTOM**

`oc whoami` starts with `system:serviceaccount:`

**WHAT IT MEANS**

You are not authenticated as a human workshop user.

**HOW TO CHECK**

```bash
oc whoami
```

**RECOVERY**

Run `oc logout` and authenticate again with your human sandbox account.

## The shared model is not Ready

**SYMPTOM**

The shared `llama-32-3b-instruct` model does not respond.

**WHAT IT MEANS**

The platform-provided model-serving stack is not healthy yet.

**HOW TO CHECK**

```bash
oc get inferenceservice llama-32-3b-instruct -n my-first-model
```

**RECOVERY**

Wait for the shared model to become `Ready`. Do not deploy another LLM for this workshop.

## Gen AI Playground is missing

**SYMPTOM**

The OpenShift AI left navigation does not show **Gen AI studio**.

**WHAT IT MEANS**

The dashboard feature is disabled or the UI is not healthy.

**HOW TO CHECK**

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
oc get deploy gen-ai-ui -n redhat-ods-applications
```

**RECOVERY**

Verify that `genAiStudio: true` and that `gen-ai-ui` is available.

## MCP servers do not appear in Playground

**SYMPTOM**

The **MCP** tab does not list the Packmate Weather or Packmate Baggage servers.

**WHAT IT MEANS**

The workshop MCP registration is missing or stale.

**HOW TO CHECK**

```bash
oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml
```

**RECOVERY**

Run:

```bash
make prepare-workshop
```

## Playground stays on Loading

**SYMPTOM**

The Playground page opens but never leaves `Loading`.

**WHAT IT MEANS**

In the validated `3.5.1` sandbox, this usually means the required OGX platform plumbing is not enabled or not Ready yet.

**HOW TO CHECK**

```bash
oc get datasciencecluster
oc get datasciencecluster <dsc-name> -o jsonpath='{.spec.components.ogx.managementState}{"\n"}'
oc get datasciencecluster <dsc-name> -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
oc get pods -n redhat-ods-applications | grep ogx
```

**RECOVERY**

Run `make preflight` first.

If OGX is not managed or not Ready, apply the supported instructor recovery action documented by the preflight output, then wait for OpenShift AI reconciliation to complete before retesting Playground.

## Weather MCP or Baggage MCP route fails

**SYMPTOM**

One of the workshop MCP routes returns an error.

**WHAT IT MEANS**

The deployment is not healthy or the route is not serving traffic yet.

**HOW TO CHECK**

```bash
oc get pods -n packmate-lab
oc get route -n packmate-lab
```

**RECOVERY**

Run:

```bash
make diagnose
```

Then inspect the failing deployment logs.

## The Workbench is Pending

**SYMPTOM**

The Workbench never reaches `Running`.

**WHAT IT MEANS**

The project may still be provisioning storage or the selected image may be unavailable.

**HOW TO CHECK**

Check the Workbench details in OpenShift AI and inspect the related pod and PVC in the project.

**RECOVERY**

Wait for storage provisioning. If it does not recover, recreate the Workbench with the validated `Code Server | Data Science | CPU | Python 3.12` image.

## The custom endpoint cannot verify

**SYMPTOM**

The AI asset endpoint verification step fails.

**WHAT IT MEANS**

The endpoint URL, model ID, or project selection is wrong, or the feature state in the UI changed.

**HOW TO CHECK**

Verify:

- project selection
- URL
- model ID
- no extra spaces

**RECOVERY**

Use the shared model values discovered by the workshop scripts and try again.

## Packmate application route is unavailable

**SYMPTOM**

The Packmate frontend route does not open.

**WHAT IT MEANS**

The frontend deployment, service, or route is not healthy.

**HOW TO CHECK**

```bash
oc get deploy,svc,route -n packmate-lab
```

**RECOVERY**

Run:

```bash
make verify-workshop
make diagnose
```

## Evaluation fails

**SYMPTOM**

The evaluation pipeline run fails in the project **Pipelines** UI, or the
report shows `FAIL`.

**WHAT IT MEANS**

The deployed Packmate application regressed against the workshop checks.

**HOW TO CHECK**

Review:

- the pipeline task logs
- the generated report artifact
- the application response for the failed scenarios
- whether the uploaded YAML matches `pipelines/packmate-evaluation.pipeline.yaml`

**RECOVERY**

Check:

- shared model connectivity
- MCP server availability
- backend logs
- recent application changes

For local debugging, you can still run the equivalent script in Code Server:

```bash
python examples/03_evaluate_packmate.py
```

## The pipeline YAML cannot be uploaded

**SYMPTOM**

The participant cannot import `pipelines/packmate-evaluation.pipeline.yaml` in
the project **Pipelines** tab.

**WHAT IT MEANS**

The file was not downloaded correctly from Code Server, or the project pipeline
UI is not ready.

**HOW TO CHECK**

- confirm the file exists in the repo clone
- confirm the **Pipelines** tab is available in the project
- retry the upload with the compiled YAML file, not the Python source

**RECOVERY**

Use:

- `pipelines/packmate-evaluation.pipeline.yaml`

Do not upload:

- `pipelines/packmate_evaluation_pipeline.py`

If the UI still asks the participant to enter S3 credentials manually, the
project pipeline server was not prepared correctly. Ask the instructor to rerun:

```bash
make prepare-workshop
make verify-workshop
```

## Authentication expired

**SYMPTOM**

Cluster commands start failing after previously working.

**WHAT IT MEANS**

Your OpenShift session expired.

**HOW TO CHECK**

```bash
oc whoami
```

**RECOVERY**

Authenticate again with the current sandbox login command.
