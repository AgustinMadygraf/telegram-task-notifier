from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "deploy-api.yml"
DEPLOY_DOC = ROOT / "docs" / "deploy-fastapi-telegram-vps.md"
GHA_DOC = ROOT / "docs" / "github-actions-fastapi-vps.md"
README_FILE = ROOT / "README.md"


def test_workflow_file_exists() -> None:
    assert WORKFLOW_FILE.exists(), "Missing .github/workflows/deploy-api.yml"


def test_deploy_doc_exists() -> None:
    assert DEPLOY_DOC.exists(), "Missing docs/deploy-fastapi-telegram-vps.md"


def test_github_actions_doc_exists() -> None:
    assert GHA_DOC.exists(), "Missing docs/github-actions-fastapi-vps.md"


def test_readme_references_deploy_docs() -> None:
    content = README_FILE.read_text(encoding="utf-8")
    assert "docs/deploy-fastapi-telegram-vps.md" in content
    assert "docs/github-actions-fastapi-vps.md" in content


def test_workflow_is_valid_yaml() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), "Workflow YAML must parse to mapping"


def test_workflow_structure_and_triggers() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))

    # Some YAML parsers may coerce "on" into boolean True.
    on_section = parsed.get("on", parsed.get(True, {}))
    assert isinstance(on_section, dict), "Workflow on: section missing or invalid"
    assert "pull_request" in on_section
    assert "workflow_dispatch" in on_section

    push_section = on_section.get("push")
    assert isinstance(push_section, dict), "Workflow push: section missing or invalid"
    branches = push_section.get("branches")
    assert isinstance(branches, list), "Workflow push.branches must be a list"
    assert "main" in branches

    jobs = parsed.get("jobs")
    assert isinstance(jobs, dict), "Workflow jobs: section missing or invalid"
    assert "ci" in jobs
    assert "deploy" in jobs


def test_workflow_deploy_semantics() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    deploy = jobs.get("deploy", {})

    assert deploy.get("needs") == "ci"
    assert deploy.get("environment") == "production"
    assert deploy.get("if") == "github.ref == 'refs/heads/main'"


def test_workflow_deploy_contains_healthcheck() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    deploy = jobs.get("deploy", {})
    steps = deploy.get("steps", [])
    assert isinstance(steps, list)

    deploy_step = next((step for step in steps if step.get("name") == "Deploy on VPS"), None)
    assert deploy_step is not None, "Missing Deploy on VPS step"

    run_script = deploy_step.get("run", "")
    assert "curl -fsS http://127.0.0.1:8000/telegram/last_chat >/dev/null" in run_script


def test_workflow_deploy_uses_ssh_agent_with_secret() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    deploy = jobs.get("deploy", {})
    steps = deploy.get("steps", [])
    assert isinstance(steps, list)

    ssh_step = next((step for step in steps if step.get("name") == "Start ssh-agent"), None)
    assert ssh_step is not None, "Missing Start ssh-agent step"
    assert ssh_step.get("uses") == "webfactory/ssh-agent@v0.9.0"

    with_section = ssh_step.get("with", {})
    assert isinstance(with_section, dict)
    assert with_section.get("ssh-private-key") == "${{ secrets.VPS_SSH_KEY }}"
