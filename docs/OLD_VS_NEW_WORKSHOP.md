# Old vs New Packmate Workshop

## Previous workshop

The previous Packmate workshop focused on a production-style delivery path:

`RHDP/OpenShift AI -> GitHub fork -> Workbench -> bootstrap -> Playground -> DEV -> Tekton -> GHCR -> PR -> Argo CD -> PROD`

That workshop was useful, but it asked beginners to spend significant time on:

- Git forks and remotes
- image publication
- registry credentials
- pipelines
- promotion pull requests
- GitOps synchronization

Those topics are valuable for platform and DevOps teams, but they distract from the beginner OpenShift AI learning journey.

## New workshop

The redesigned workshop focuses on the AI developer and data scientist experience:

`OpenShift AI -> Project -> Workbench -> shared model -> Playground -> RAG if reliable -> MCP -> Python -> Packmate app -> evaluation -> production overview`

## Why the redesign matters

The new workshop changes the center of gravity:

- from Kubernetes and delivery mechanics
- to building, testing, and understanding a Gen AI application on OpenShift AI

The participant now learns:

- what a Data Science Project is
- what a Workbench is
- how to reuse a shared model
- how Playground helps experimentation
- what system instructions do
- how MCP tools extend a model
- how Python connects to the same model endpoint
- how evaluation helps catch regressions

## What stayed useful

The redesign still reuses important technical pieces from the older project:

- FastAPI backend
- React frontend
- Weather MCP server
- Baggage Policy MCP server
- deterministic evaluation runner
- troubleshooting patterns
- model-serving discovery logic

## What moved out of the main path

The following topics are no longer core participant hands-on steps:

- GitHub forks
- GHCR
- Tekton pipelines
- promotion PRs
- Argo CD sync
- production rollout mechanics

They can still appear as optional or instructor-only productionization material.
