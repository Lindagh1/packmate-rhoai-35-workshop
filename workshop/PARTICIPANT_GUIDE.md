# Participant Guide

## How to use this guide

This guide is written for a data scientist or AI developer who may be using
OpenShift AI for the first time.

For each module, focus on three questions:

1. Where do I click?
2. What does this screen or action mean?
3. How does this connect to the final application?

## Your role in this workshop

You are acting as a data scientist or AI developer.

Your job in this workshop is not to administer the OpenShift AI platform.
Your job is to:

- discover the prepared project, workbench, and shared model
- prototype behavior in Playground
- enable prepared MCP tools
- understand how tool-assisted AI responses work
- inspect the application code in Code Server
- connect the UI experience to the backend mechanism

The platform team has already prepared the heavy infrastructure for you:

- the shared model
- the serving stack
- OGX
- the MCP servers

Your learning goal is to understand how to build with those prepared
capabilities, not how to install them from scratch.

## Module 0 - Meet Packmate

**WHAT YOU WILL DO**

Understand the workshop story and the Packmate travel assistant.

**WHY THIS MATTERS**

You will improve one continuous AI application instead of learning isolated features.

**TIME**

5 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. Open Red Hat OpenShift AI.
2. Keep this goal in mind: Packmate helps a traveler decide what to pack.
3. Example questions:
   - What should I pack for Rome?
   - Can I take a 150 ml liquid in cabin baggage?
   - Can I put a power bank in checked baggage?

**SCREENSHOT**

![OpenShift AI](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/01-open-openshift-ai.png)

**EXPECTED RESULT**

You understand the workshop goal.

**WHAT JUST HAPPENED?**

Packmate is the story that connects Playground, Python, MCP, and the final application.

As a first-time OpenShift AI user, this matters because the platform can feel
like many separate menus at first. The workshop gives you one continuous thread:

- OpenShift AI gives you a project and a workbench
- the platform team has already prepared a shared model
- Playground helps you prototype
- MCP adds live tools
- Code Server helps you inspect the actual application
- the Packmate app shows the same idea in a user-facing product

**CHECKPOINT**

- [ ] I know what Packmate does

**IF IT DOESN'T WORK**

Ask the instructor to confirm that the OpenShift AI dashboard is available.

## Module 1 - Create your AI workspace

**WHAT YOU WILL DO**

Create the `packmate-lab` project and create a CPU Code Server Workbench.

**WHY THIS MATTERS**

The project groups your AI resources. The Code Server Workbench is your browser-based coding environment.

**TIME**

10 to 15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the left navigation, select **Projects**.
2. Click **Create project**.
3. Enter the name `packmate-lab`.
4. Open the new project.
5. Open the **Workbenches** tab.
6. Click **Create workbench**.
7. Choose the image **Code Server | Data Science | CPU | Python 3.12**.
8. Enter the name `packmate-workbench`.
9. Create the workbench.
10. Wait until the Workbench status is **Running**.
11. Open the Workbench.

**SCREENSHOTS**

![Projects](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/02-data-science-projects.png)
![Create Project](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/03-create-project.png)
![Create Workbench](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/04-create-workbench.png)
![Workbench Running](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/05-workbench-running.png)
![Open Workbench](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/06-open-workbench.png)

**EXPECTED RESULT**

The Code Server Workbench opens successfully.

**WHAT JUST HAPPENED?**

You created the browser-based development environment where you will clone the repo and run Python code without needing local tools.

If you are new to OpenShift AI, the key idea is:

- a **project** is your working space
- a **workbench** is your interactive development environment
- **Code Server** gives you an in-browser editor and terminal

In other words, this is the place where the data scientist writes or inspects
application code, not just experiments in a chat UI.

**CHECKPOINT**

- [ ] I created `packmate-lab`
- [ ] I created the Workbench
- [ ] the Workbench is `Running`
- [ ] the Workbench opens

**IF IT DOESN'T WORK**

See `workshop/TROUBLESHOOTING.md` for Workbench and PVC issues.

## Module 2 - Meet the shared model

**WHAT YOU WILL DO**

Inspect the shared Llama model that the platform team already deployed.

**WHY THIS MATTERS**

AI developers often reuse a platform-provided model instead of deploying their own.

**TIME**

15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the left navigation, select **Gen AI studio**.
2. Select **AI asset endpoints**.
3. In **Project**, choose `my-first-model` if it is not already selected.
4. Confirm that the shared model `llama-32-3b-instruct` is available.
5. In the Workbench terminal, run:

```bash
python examples/01_call_model.py
```

**SCREENSHOTS**

![AI asset endpoints](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/07-ai-asset-endpoints.png)
![Shared model endpoint](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/08-packmate-model-endpoint.png)
![Python model call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/17-workbench-python-call.png)

**EXPECTED RESULT**

You see a model response in the terminal.

**WHAT JUST HAPPENED?**

You reused the shared OpenShift AI model endpoint without deploying another model.

This is an important platform habit to learn:

- you do not always deploy your own model
- sometimes the platform team exposes a shared model for many users
- as a data scientist, you mainly need to know where to find it and how to call it

In this workshop, `my-first-model` is the project that exposes the shared model.

**CHECKPOINT**

- [ ] I can find `llama-32-3b-instruct`
- [ ] the Python example returns a response

**IF IT DOESN'T WORK**

Confirm that the shared model in `my-first-model` is `Ready`.

## Module 3 - Prototype in Playground

**WHAT YOU WILL DO**

Chat with the shared model in Playground and add Packmate system instructions.

**WHY THIS MATTERS**

Playground is the fastest place to experiment before you write application code.

**TIME**

20 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the left navigation, select **Gen AI studio**.
2. Select **Playground**.
3. In **Project**, choose `my-first-model`.
4. If needed, click **Create playground**.
5. Select the `llama-32-3b-instruct` model.
6. Ask:
   `I am going to Rome for four days. What should I pack?`
7. Open the **Prompt** tab.
8. Paste the contents of `workshop/assets/system-instructions.md`.
9. Ask the same question again and compare the result.

**SCREENSHOTS**

![Playground model selected](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/09-playground-model-selected.png)
![System prompt](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/10-playground-system-prompt.png)

**EXPECTED RESULT**

The second answer behaves more like Packmate.

**WHAT JUST HAPPENED?**

System instructions changed how the assistant behaves without retraining the model.

This is one of the most important beginner lessons:

- the **model** stayed the same
- the **system prompt** changed the behavior
- this is often the first step before writing application code

Playground is useful because it lets you learn prompt behavior quickly before
you commit anything to the application.

**CHECKPOINT**

- [ ] the model responds
- [ ] the system instructions are active
- [ ] I understand the difference between system instructions and a user question

**IF IT DOESN'T WORK**

Re-open the Playground and confirm the selected project and model.

## Module 4 - Give Packmate tools with MCP

**WHAT YOU WILL DO**

Enable the prepared Weather and Baggage Policy MCP servers in Playground and inspect how tool calls work.

**WHY THIS MATTERS**

MCP gives the model live capabilities instead of only static knowledge.

**TIME**

20 to 25 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In Playground, open the **MCP** tab.
2. Enable the Packmate Weather MCP server.
3. Ask:
   `I am travelling to Rome next week. Check the weather and recommend what I should pack.`
4. Inspect the tool call details. Notice:
   - which tool the model selected
   - which arguments were sent
   - what the tool returned
5. Enable the Packmate Baggage Policy MCP server.
6. Ask:
   `Can I take a 150 ml liquid in cabin baggage?`
7. Ask:
   `Can I put my power bank in checked baggage?`
8. Inspect the tool calls.
9. Optionally disable one MCP server and retry a related question to see how the assistant falls back when a tool is unavailable.

**SCREENSHOTS**

![Weather MCP enabled](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/13-weather-mcp-enabled.png)
![Weather tool call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/14-weather-tool-call.png)
![Baggage MCP enabled](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/15-baggage-mcp-enabled.png)
![Baggage tool call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/16-baggage-tool-call.png)

**EXPECTED RESULT**

You see the tools being invoked and then used in the final answer.

**WHAT JUST HAPPENED?**

MCP stands for Model Context Protocol. In this workshop:

- an MCP server exposes one or more tools
- the Playground sends the model the tool definitions
- the model decides whether it needs a tool
- the tool runs outside the model
- the tool result is returned to the model
- the model uses that result in its final answer

When you open the tool details, try to read them like an AI developer:

- what question did I ask?
- which tool did the model choose?
- what arguments did it send?
- what raw result came back?
- how did the final answer change because of that result?

That is the core mental model of agentic AI in this workshop.

**CHECKPOINT**

- [ ] Weather MCP is enabled
- [ ] baggage MCP is enabled
- [ ] I can explain what an MCP server and a tool are
- [ ] I can explain how the model used the tool result

**IF IT DOESN'T WORK**

Ask the instructor to run `make verify-workshop`.

## Module 5 - From Playground to Code Server and Python

**WHAT YOU WILL DO**

Open the Packmate repository in Code Server and run the Python examples from the Workbench terminal.

**WHY THIS MATTERS**

This is the bridge from experimentation to application code.

**HOW TO THINK ABOUT THIS STEP**

At this point, you switch from "Playground user" to "AI developer".

In this workshop, Code Server is where you develop and inspect the project:

- `app/frontend` contains the React frontend
- `app/backend` contains the FastAPI backend
- `mcp/weather` contains the Weather MCP server
- `mcp/baggage` contains the Baggage Policy MCP server
- `examples/01_call_model.py` calls the shared model directly
- `examples/02_packmate_with_tools.py` calls the deployed Packmate application
- `examples/03_evaluate_packmate.py` runs the deterministic evaluation

**HOW PACKMATE USES OGX**

This workshop now follows the OpenShift AI `3.5` agentic path more closely:

That means:

- the platform team prepares OGX
- the shared model is still served by `KServe + ServingRuntime + vLLM`
- Packmate keeps a simple application stack: `React frontend -> FastAPI backend -> OGX`
- OGX is the agent runtime that gives the model access to the prepared MCP servers
- you do **not** create OGX resources in this workshop

So the story is:

- in Playground, you see model + MCP behavior from the OpenShift AI UI
- in Code Server, you inspect the same idea in application code
- the backend does not call the MCP servers directly in the main runtime path
- instead, the backend sends one agentic request to OGX
- OGX reaches the shared model and the MCP servers for you

This is the moment where many first-time users ask:

"If Playground already works, why do I need Code Server?"

The answer is:

- Playground helps you learn and prototype
- Code Server is where you understand the stack
- the repository shows you where the frontend, backend, prompts, and MCP servers live
- the application code shows how the same idea becomes a repeatable product

If you want to inspect the code path, look at:

- `app/backend/app/main.py`
- `app/backend/app/agent/runtime.py`
- `app/backend/app/agent/ogx_service.py`

**TIME**

15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. Open the terminal in Code Server.
2. Clone the repository:

```bash
git clone https://github.com/Lindagh1/packmate-rhoai-35-workshop.git
cd packmate-rhoai-35-workshop
```

3. In the Code Server file explorer, open the cloned repository and inspect:

- `app/frontend`
- `app/backend`
- `mcp/weather`
- `mcp/baggage`

Also inspect these files if you want to understand the runtime path:

- `app/backend/app/agent/ogx_service.py`
- `app/backend/app/agent/prompts.py`
- `examples/01_call_model.py`
- `examples/02_packmate_with_tools.py`

4. In the Code Server terminal, run:

```bash
python examples/01_call_model.py
python examples/02_packmate_with_tools.py
```

**SCREENSHOT**

![Workbench Python call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/17-workbench-python-call.png)

**EXPECTED RESULT**

The first script calls the shared model directly so that you can see the base model behavior.

The second script calls the deployed Packmate application. Inside the application:

- the React frontend talks to the FastAPI backend
- the FastAPI backend sends the request to OGX
- OGX uses the shared model plus the prepared MCP servers
- the final structured answer comes back to Packmate

**WHAT JUST HAPPENED?**

You moved from UI experimentation to readable application code.

As a data scientist or AI developer, this is the key mental model:

- Playground helps you prototype prompts and tool behavior
- Code Server is where you inspect and evolve the application
- the frontend is a React UI
- the backend is a FastAPI service
- the MCP servers are separate tool services
- the shared model endpoint is reused instead of deployed by the participant
- the backend uses OGX as the standard agentic runtime path
- OGX does not replace `KServe` or `vLLM`; it sits in front of them for this workflow
- the Weather and Baggage MCP servers are still normal tool services that OGX can call

If you want to explain the coding mechanism simply:

- `app/frontend` is the user interface
- `app/backend` is the application API
- `app/backend/app/agent/ogx_service.py` is where the OGX-backed AI logic lives
- `mcp/weather` and `mcp/baggage` are the tool servers
- `examples/01_call_model.py` shows a simple model call
- `examples/02_packmate_with_tools.py` shows the application path
- `examples/03_evaluate_packmate.py` shows regression evaluation

**CHECKPOINT**

- [ ] I can run the model example
- [ ] I can run the Packmate application example
- [ ] I can explain where the frontend, backend, and MCP servers live in the repo
- [ ] I can explain that Packmate uses OGX without requiring the participant to administer OGX

**IF IT DOESN'T WORK**

Verify that the Workbench can reach in-cluster services and that the workshop preparation completed successfully.

## Module 6 - Open the integrated Packmate application

**WHAT YOU WILL DO**

Open the deployed Packmate web application and compare it with Playground behavior.

**WHY THIS MATTERS**

This shows how prototype behavior becomes part of an application with extra controls.

**TIME**

15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. Open the Packmate Route provided by the instructor.
2. Submit the same scenario that you used in Playground.
3. Compare the result.

**SCREENSHOT**

![Packmate application](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/18-packmate-application.png)

**EXPECTED RESULT**

The application returns a structured response.

**WHAT JUST HAPPENED?**

The frontend called the Packmate backend, and the backend sent an OGX request that used the shared model plus MCP-backed capabilities.

This is the final beginner connection to make:

- in Playground, you manually explore the behavior
- in the app, the same mechanism is wrapped in a product flow
- the user does not need to know MCP or OGX internals
- the AI developer does need to understand how those layers connect

**CHECKPOINT**

- [ ] I opened the application
- [ ] I received a structured answer

**IF IT DOESN'T WORK**

Ask the instructor to run `make diagnose`.

## Module 7 - Evaluate the application

**WHAT YOU WILL DO**

Run the deterministic Packmate regression evaluation.

**WHY THIS MATTERS**

Evaluation helps you detect regressions in application behavior.

**TIME**

10 to 15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the Workbench terminal, run:

```bash
python examples/03_evaluate_packmate.py
```

**SCREENSHOT**

![Evaluation result](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/19-evaluation-result.png)

**EXPECTED RESULT**

You get a PASS/FAIL score for the deterministic workshop regression checks.

**WHAT JUST HAPPENED?**

This is an AI application regression evaluation. It is not a claim that the model is universally accurate.

**CHECKPOINT**

- [ ] I ran the evaluation
- [ ] I understand why this is not a universal accuracy score

**IF IT DOESN'T WORK**

For the optional live route-based evaluation, ask the instructor for the Packmate Route and run:

```bash
python examples/03_evaluate_packmate.py --mode live --base-url https://<your-packmate-route>
```

## Module 8 - Understand the architecture

**WHAT YOU WILL DO**

Review the beginner-level architecture.

**WHY THIS MATTERS**

You should leave the workshop understanding what OpenShift AI provided for you.

**TIME**

10 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. Open `workshop/ARCHITECTURE.md`.
2. Review the participant flow, serving architecture, and MCP sequence.

**EXPECTED RESULT**

You can explain the role of Workbench, Playground, OGX, KServe, vLLM, MCP, and evaluation.

**CHECKPOINT**

- [ ] I can explain the high-level architecture

## Module 9 - From prototype to production

**WHAT YOU WILL DO**

Review the short productionization overview.

**WHY THIS MATTERS**

A useful prototype still needs more work before production.

**TIME**

5 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. Review the optional productionization discussion from the instructor.

**EXPECTED RESULT**

You understand that application packaging, CI/CD, promotion, and operational controls come after prototype validation.
