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

## MCP preparation

The live `3.5` participant path uses the documented Playground MCP registration mechanism:

- `ConfigMap/gen-ai-aa-mcp-servers`
- namespace: `redhat-ods-applications`

The workshop does **not** require the MCP Lifecycle Operator or MCP Catalog.

## OGX status

OGX is relevant to OpenShift AI `3.5`, but the validated hands-on path in this sandbox does not depend on OGX because the `ogx` component is removed in the live `DataScienceCluster`.

## RAG status

RAG remains conditional until the live Playground flow is validated during rehearsal.

If the sandbox RAG flow proves reliable without adding heavy infrastructure, include it.
Otherwise, keep it conceptual and optional.

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
- [ ] Workbench image available
- [ ] Weather MCP works
- [ ] Baggage MCP works
- [ ] Packmate Route works
- [ ] evaluation passes
- [ ] screenshots/documentation match UI
- [ ] no participant resource conflict

## Common failure areas

- shared model not Ready
- Gen AI Studio disabled
- missing Playground MCP registration
- route not reachable
- build failed in `packmate-lab`
- custom endpoint entry wrong in the UI

See `workshop/TROUBLESHOOTING.md` for recovery guidance.

## Optional advanced appendix

Productionization topics such as CI/CD, immutable images, GitOps, and promotion flow should stay outside the main beginner path.
