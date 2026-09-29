# Participant Guide

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

**CHECKPOINT**

- [ ] I know what Packmate does

**IF IT DOESN'T WORK**

Ask the instructor to confirm that the OpenShift AI dashboard is available.

## Module 1 - Create your AI workspace

**WHAT YOU WILL DO**

Create or open the `packmate-lab` project and open a CPU Workbench.

**WHY THIS MATTERS**

The project groups your AI resources. The Workbench is your browser-based coding environment.

**TIME**

10 to 15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the left navigation, select **Data Science Projects**.
2. Create or open the project `packmate-lab`.
3. Open the **Workbenches** tab.
4. Create or open a CPU Workbench by using the validated generic data science image.
5. Wait until the Workbench status is **Running**.
6. Open the Workbench.

**SCREENSHOTS**

![Projects](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/02-data-science-projects.png)
![Create Project](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/03-create-project.png)
![Create Workbench](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/04-create-workbench.png)
![Workbench Running](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/05-workbench-running.png)
![Open Workbench](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/06-open-workbench.png)

**EXPECTED RESULT**

The Workbench opens successfully.

**WHAT JUST HAPPENED?**

You created the place where you will run Python code without needing local tools.

**CHECKPOINT**

- [ ] `packmate-lab` exists
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
3. In **Project**, choose `my-first-model`.
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

**CHECKPOINT**

- [ ] the model responds
- [ ] the system instructions are active
- [ ] I understand the difference between system instructions and a user question

**IF IT DOESN'T WORK**

Re-open the Playground and confirm the selected project and model.

## Module 4 - Ground the model with RAG

**WHAT YOU WILL DO**

Optionally test Retrieval-Augmented Generation (RAG) with the Packmate baggage policy document.

**WHY THIS MATTERS**

RAG gives the model relevant document context at request time.

**TIME**

15 to 20 minutes if enabled

**STEP-BY-STEP INSTRUCTIONS**

1. Only continue if the instructor confirms that the live sandbox RAG flow is enabled for this workshop.
2. Open the **Knowledge** tab in Playground.
3. Upload `workshop/assets/packmate-baggage-policy.pdf`.
4. Ask a question about a fictional Packmate policy.
5. Compare the answer before and after the document is available.

**SCREENSHOTS**

![RAG upload](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/11-rag-knowledge-upload.png)
![RAG answer](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/12-rag-grounded-answer.png)

**EXPECTED RESULT**

If enabled, the model uses the workshop document as context.

**WHAT JUST HAPPENED?**

RAG is not training. The model retrieves relevant text from a document and uses it while answering.

**CHECKPOINT**

- [ ] I understand that RAG is retrieval, not training

**IF IT DOESN'T WORK**

Treat RAG as optional for this sandbox and continue with the next module.

## Module 5 - Give Packmate tools with MCP

**WHAT YOU WILL DO**

Enable the prepared Weather and Baggage Policy MCP servers in Playground.

**WHY THIS MATTERS**

MCP gives the model live capabilities instead of only static knowledge.

**TIME**

20 to 25 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In Playground, open the **MCP** tab.
2. Enable the Packmate Weather MCP server.
3. Ask:
   `I am travelling to Rome next week. Check the weather and recommend what I should pack.`
4. Inspect the tool call.
5. Enable the Packmate Baggage Policy MCP server.
6. Ask:
   `Can I take a 150 ml liquid in cabin baggage?`
7. Ask:
   `Can I put my power bank in checked baggage?`
8. Inspect the tool calls.

**SCREENSHOTS**

![Weather MCP enabled](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/13-weather-mcp-enabled.png)
![Weather tool call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/14-weather-tool-call.png)
![Baggage MCP enabled](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/15-baggage-mcp-enabled.png)
![Baggage tool call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/16-baggage-tool-call.png)

**EXPECTED RESULT**

You see the tools being invoked and then used in the final answer.

**WHAT JUST HAPPENED?**

The model chose a tool, the MCP server executed it, and the model used the returned result.

**CHECKPOINT**

- [ ] Weather MCP is enabled
- [ ] baggage MCP is enabled
- [ ] I can explain the difference between MCP and RAG

**IF IT DOESN'T WORK**

Ask the instructor to run `make verify-workshop`.

## Module 6 - From Playground to Python

**WHAT YOU WILL DO**

Run the Python examples from the Workbench.

**WHY THIS MATTERS**

This is the bridge from experimentation to application code.

**TIME**

15 minutes

**STEP-BY-STEP INSTRUCTIONS**

1. In the Workbench terminal, run:

```bash
python examples/01_call_model.py
python examples/02_packmate_with_tools.py
```

**SCREENSHOT**

![Workbench Python call](/home/lgheziel/Projects/packmate-rhoai-35-workshop/workshop/images/17-workbench-python-call.png)

**EXPECTED RESULT**

The first script calls the shared model. The second script calls the deployed Packmate application.

**WHAT JUST HAPPENED?**

You moved from UI experimentation to readable Python code.

**CHECKPOINT**

- [ ] I can run the model example
- [ ] I can run the Packmate application example

**IF IT DOESN'T WORK**

Verify that the Workbench can reach in-cluster services and that the workshop preparation completed successfully.

## Module 7 - Open the integrated Packmate application

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

The frontend called the Packmate backend, and the backend used the shared model plus MCP-backed capabilities.

**CHECKPOINT**

- [ ] I opened the application
- [ ] I received a structured answer

**IF IT DOESN'T WORK**

Ask the instructor to run `make diagnose`.

## Module 8 - Evaluate the application

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

## Module 9 - Understand the architecture

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

You can explain the role of Workbench, Playground, KServe, vLLM, MCP, and evaluation.

**CHECKPOINT**

- [ ] I can explain the high-level architecture

## Module 10 - From prototype to production

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
