#!/usr/bin/env python3
"""Kubeflow Pipelines definition for the Packmate workshop evaluation."""

from kfp import compiler, dsl


@dsl.component(base_image="python:3.12-slim")
def run_packmate_workshop_evaluation(
    report_path: dsl.OutputPath(str),
    threshold: float = 0.90,
    repo_zip_url: str = "https://github.com/Lindagh1/packmate-rhoai-35-workshop/archive/refs/heads/main.zip",
) -> None:
    import os
    import shutil
    import subprocess
    import sys
    import tempfile
    import urllib.request
    import zipfile
    from pathlib import Path

    workspace = Path(tempfile.mkdtemp(prefix="packmate-eval-"))
    archive_path = workspace / "repo.zip"
    extract_root = workspace / "repo"

    urllib.request.urlretrieve(repo_zip_url, archive_path)

    with zipfile.ZipFile(archive_path) as zip_file:
        zip_file.extractall(extract_root)

    extracted_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
    if not extracted_dirs:
        raise RuntimeError("The repository archive did not contain a source directory")
    repo_root = extracted_dirs[0]
    backend_root = repo_root / "app" / "backend"

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(backend_root / "requirements.txt")],
        check=True,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(backend_root)

    subprocess.run(
        [
            sys.executable,
            "evals/runner.py",
            "--mode",
            "deterministic",
            "--threshold",
            str(threshold),
            "--report-json",
            report_path,
        ],
        cwd=backend_root,
        env=env,
        check=True,
    )

    shutil.rmtree(workspace, ignore_errors=True)


@dsl.pipeline(
    name="packmate-workshop-evaluation",
    description="Run the deterministic Packmate workshop evaluation and store a JSON report.",
)
def packmate_workshop_evaluation_pipeline(
    threshold: float = 0.90,
    repo_zip_url: str = "https://github.com/Lindagh1/packmate-rhoai-35-workshop/archive/refs/heads/main.zip",
) -> None:
    run_packmate_workshop_evaluation(
        threshold=threshold,
        repo_zip_url=repo_zip_url,
    )


if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=packmate_workshop_evaluation_pipeline,
        package_path="pipelines/packmate-evaluation.pipeline.yaml",
    )
