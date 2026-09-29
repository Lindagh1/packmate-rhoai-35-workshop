# Packmate Architecture

This workshop is validated on:

- OpenShift `4.20.38`
- Red Hat OpenShift AI `3.5.1`

## Beginner summary

Participants do not deploy a new LLM.

They reuse a shared model that already exists in the sandbox and learn how OpenShift AI helps them:

- develop in a Workbench
- experiment in Playground
- add tools with MCP
- call the same model from Python
- connect that capability to an application

## Participant workflow

```mermaid
flowchart TD
  A[Open OpenShift AI] --> B[Create or open project]
  B --> C[Create or open Workbench]
  C --> D[Create or open model endpoint view]
  D --> E[Use Gen AI Playground]
  E --> F[Add system instructions]
  F --> G[Enable MCP tools]
  G --> H[Run Python example]
  H --> I[Open Packmate application]
  I --> J[Run evaluation]
```

## Actual serving architecture

The live sandbox uses:

- `InferenceService`: `llama-32-3b-instruct`
- `ServingRuntime`: `llama-32-3b-instruct`
- inference engine: `vLLM`
- serving layer: `KServe`

```mermaid
flowchart TD
  UserCode[Workbench / Python / Playground / Packmate] --> Endpoint[Shared model endpoint]
  Endpoint --> KS[KServe InferenceService]
  KS --> SR[ServingRuntime]
  SR --> V[vLLM runtime]
  V --> L[Llama 3.2 3B Instruct model]
```

### What KServe does

KServe manages the model-serving workload on OpenShift.

### What vLLM does

vLLM loads the model and generates tokens for requests.

## MCP request flow

```mermaid
sequenceDiagram
  participant U as User
  participant P as Playground or Packmate
  participant M as Shared model
  participant T as MCP server

  U->>P: Ask a question
  P->>M: Send prompt and tool definitions
  M->>P: Choose a tool call
  P->>T: Execute MCP tool
  T-->>P: Return tool result
  P->>M: Provide tool result
  M-->>P: Final answer
```

## Weather and baggage MCP architecture

```mermaid
flowchart LR
  Playground --> MCPConfig[gen-ai-aa-mcp-servers]
  MCPConfig --> Weather[Weather MCP route]
  MCPConfig --> Baggage[Baggage Policy MCP route]
  App[Packmate backend] --> Weather
  App --> Baggage
  Weather --> OpenMeteo[Open-Meteo API]
  Baggage --> Rules[Deterministic workshop rules]
```

## RAG architecture

Use this section only if the live Playground RAG flow is validated during rehearsal.

```mermaid
flowchart TD
  Doc[Packmate baggage policy file] --> KB[Knowledge upload in Playground]
  KB --> VS[Inline vector store resources]
  VS --> Model[Shared model]
  Model --> Answer[Grounded answer with cited context]
```

Important:

- RAG is not training
- RAG retrieves relevant context at request time

## OGX in this workshop

OpenShift AI `3.5` introduces OGX terminology, but the live sandbox used for this workshop does **not** have the `ogx` component enabled.

That means:

- OGX is relevant conceptually for `3.5`
- OGX is **not** the validated hands-on runtime path in this sandbox

Beginner-level conceptual picture:

```mermaid
flowchart TD
  UX[Workbench / Python / Playground] --> OGX[OGX concept]
  OGX --> Infer[Inference]
  OGX --> Tools[Tools]
  OGX --> Retrieval[Retrieval]
  Infer --> ModelEndpoint[Model endpoint]
  Tools --> MCP[MCP]
  Retrieval --> RAG[RAG]
```

Use this as a concept map only. It does not replace the actual live serving path documented above.

## Packmate application architecture

```mermaid
flowchart LR
  UI[React frontend] --> API[FastAPI backend]
  API --> SharedModel[Shared llama-32-3b-instruct]
  API --> WeatherMCP[Weather MCP]
  API --> BaggageMCP[Baggage Policy MCP]
```

## Prototype to production

```mermaid
flowchart LR
  Prototype[Playground prototype] --> Code[Python and app code]
  Code --> Eval[Regression evaluation]
  Eval --> Image[Container image]
  Image --> CI[CI/CD]
  CI --> GitOps[GitOps and promotion]
  GitOps --> Prod[Production]
```

Productionization is intentionally outside the core beginner hands-on path.
