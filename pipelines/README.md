# Packmate Pipelines

This directory contains the OpenShift AI Pipelines assets used by the workshop.

## Files

- `packmate_evaluation_pipeline.py`: KFP source used to generate the pipeline definition
- `packmate-evaluation.pipeline.yaml`: compiled pipeline YAML that participants can upload in the `Pipelines` section of the `packmate-lab` project

## What the evaluation pipeline does

The pipeline:

1. downloads the workshop repository archive from GitHub
2. installs the backend evaluation dependencies
3. runs the deterministic Packmate evaluation
4. stores a JSON report as a pipeline artifact

The pipeline intentionally does not claim universal model accuracy. It is a
workshop regression check for the Packmate application design.
