# Instructor Guide

## Purpose

This workshop teaches beginners how to build and test a Gen AI application with Red Hat OpenShift AI from the user perspective.

## Audience

- Data Scientists
- AI Developers
- Application Developers
- technical beginners exploring OpenShift AI

## Duration

Target duration: `120` to `150` minutes.

## Validated environment

Validated on:

- OpenShift `4.20.38`
- Red Hat OpenShift AI `3.5.1`

## Important support status

- Gen AI Playground: Technology Preview
- custom endpoints: Technology Preview
- MCP Lifecycle Operator / MCP Catalog: Technology Preview
- OGX: Technology Preview

This workshop uses only the parts that are actually present and validated in the live sandbox.

## Shared model assumptions

- shared model namespace: `my-first-model`
- shared model name: `llama-32-3b-instruct`
- serving path: `KServe -> ServingRuntime -> vLLM`
- no duplicate LLM deployment
- no extra GPU allocation

## Resource-saving strategy

The workshop reuses the shared platform model and adds only lightweight services in `packmate-lab`:

- React frontend
- FastAPI backend
- Weather MCP
- Baggage Policy MCP

## Setup commands

```bash
make preflight
make prepare-workshop
make verify-workshop
```

Or:

```bash
make workshop-ready
```

## Cleanup command

```bash
make cleanup
```

## Reset command

```bash
make reset-participant
```

## Namespace strategy

This workshop is validated on a dedicated sandbox-style cluster, so the default participant namespace is:

- `packmate-lab`

## Validated workbench image

- `Code Server | Data Science | CPU | Python 3.12`

## Evaluation path

The participant-facing evaluation path now uses OpenShift AI Pipelines.

Use:

- `pipelines/packmate-evaluation.pipeline.yaml`

The pipeline downloads the published repository archive, installs the backend
evaluation dependencies, and runs the deterministic Packmate evaluation.

## MCP preparation

The live `3.5` participant path uses the documented Playground MCP registration mechanism:

- `ConfigMap/gen-ai-aa-mcp-servers`
- namespace: `redhat-ods-applications`

The workshop does **not** require the MCP Lifecycle Operator or MCP Catalog.

## OGX status

OGX is enabled in the live `3.5.1` sandbox because the Playground depends on it here.

Keep the explanation beginner-level:

- OGX is part of the platform plumbing behind the Gen AI experience
- the platform team prepares it
- workshop participants consume the prepared Playground, model, and MCP capabilities
- the Packmate backend also uses OGX as its primary agentic runtime path
- participants do **not** create or administer OGX resources in this workshop

Support-status note for instructors:

- Gen AI Playground: Technology Preview in RHOAI `3.5`
- custom endpoints: Technology Preview in RHOAI `3.5`
- OGX remote provider / SDK compatibility used for MCP HTTP streaming: Developer Preview in this workshop architecture

## 15 minutes before the workshop

Run:

```bash
make preflight
make prepare-workshop
make verify-workshop
```

Verify:

- [ ] shared model Ready
- [ ] model endpoint works
- [ ] Playground available
- [ ] Playground exits `Loading`
- [ ] Workbench image available
- [ ] Weather MCP works
- [ ] Baggage MCP works
- [ ] Packmate Route works
- [ ] evaluation pipeline YAML is present in the repository
- [ ] evaluation passes
- [ ] screenshots/documentation match UI
- [ ] no participant resource conflict

## Common failure areas

- shared model not Ready
- Gen AI Studio disabled
- OGX not enabled or not Ready
- missing Playground MCP registration
- route not reachable
- build failed in `packmate-lab`
- custom endpoint entry wrong in the UI
- participant cannot upload or run the pipeline in the project

See `workshop/TROUBLESHOOTING.md` for recovery guidance.

## Optional advanced appendix

Productionization topics such as CI/CD, immutable images, GitOps, and promotion flow should stay outside the main beginner path.
