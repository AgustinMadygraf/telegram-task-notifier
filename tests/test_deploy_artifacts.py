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
    required_jobs = {
        "build_tests",
        "build_lint",
        "build_image",
        "build_gate",
        "deploy_prepare",
        "deploy_apply",
        "verify_local",
        "verify_public",
        "deploy_gate",
    }
    assert required_jobs.issubset(set(jobs.keys()))


def test_workflow_has_concurrency_control() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    concurrency = parsed.get("concurrency")
    assert isinstance(concurrency, dict)
    assert "deploy-api-${{ github.ref }}" == concurrency.get("group")
    assert concurrency.get("cancel-in-progress") is True


def test_workflow_build_and_deploy_dag_semantics() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})

    build_gate = jobs.get("build_gate", {})
    build_gate_needs = build_gate.get("needs", [])
    assert isinstance(build_gate_needs, list)
    assert set(build_gate_needs) == {"build_tests", "build_lint", "build_image"}

    deploy_prepare = jobs.get("deploy_prepare", {})
    assert deploy_prepare.get("needs") == "build_gate"
    assert deploy_prepare.get("if") == "github.ref == 'refs/heads/main'"

    deploy_apply = jobs.get("deploy_apply", {})
    assert deploy_apply.get("needs") == "deploy_prepare"
    assert deploy_apply.get("environment") == "production"
    assert deploy_apply.get("if") == "github.ref == 'refs/heads/main'"

    verify_local = jobs.get("verify_local", {})
    verify_public = jobs.get("verify_public", {})
    assert verify_local.get("needs") == "deploy_apply"
    assert verify_public.get("needs") == "deploy_apply"

    deploy_gate = jobs.get("deploy_gate", {})
    deploy_gate_needs = deploy_gate.get("needs", [])
    assert isinstance(deploy_gate_needs, list)
    assert set(deploy_gate_needs) == {"verify_local", "verify_public"}


def test_workflow_verify_local_contains_healthcheck_and_smokes() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    verify_local = jobs.get("verify_local", {})
    steps = verify_local.get("steps", [])
    assert isinstance(steps, list)

    verify_step = next((step for step in steps if step.get("name") == "Verify local deployment"), None)
    assert verify_step is not None, "Missing Verify local deployment step"

    run_script = verify_step.get("run", "")
    assert "for i in {1..20}; do" in run_script
    assert "curl -fsS http://127.0.0.1:8000/health >/dev/null" in run_script
    assert 'echo "Healthcheck OK"' in run_script
    assert 'echo "Healthcheck failed"' in run_script
    assert "docker compose logs --tail=200 api" in run_script
    assert "local_cors_status=$(curl -sS" in run_script
    assert "local_contact_status=$(curl -sS" in run_script


def test_workflow_verify_public_contains_healthcheck_and_smokes() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    verify_public = jobs.get("verify_public", {})
    steps = verify_public.get("steps", [])
    assert isinstance(steps, list)

    verify_step = next((step for step in steps if step.get("name") == "Verify public deployment"), None)
    assert verify_step is not None, "Missing Verify public deployment step"

    run_script = verify_step.get("run", "")
    assert "for i in {1..20}; do" in run_script
    assert "curl -fsS https://api.datamaq.com.ar/health >/dev/null" in run_script
    assert 'echo "Public healthcheck OK"' in run_script
    assert 'echo "Public healthcheck failed"' in run_script
    assert "public_cors_status=$(curl -sS" in run_script
    assert "public_contact_status=$(curl -sS" in run_script


def test_workflow_deploy_uses_ssh_agent_with_secret() -> None:
    parsed = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    jobs = parsed.get("jobs", {})
    deploy_apply = jobs.get("deploy_apply", {})
    steps = deploy_apply.get("steps", [])
    assert isinstance(steps, list)

    ssh_step = next((step for step in steps if step.get("name") == "Start ssh-agent"), None)
    assert ssh_step is not None, "Missing Start ssh-agent step"
    assert ssh_step.get("uses") == "webfactory/ssh-agent@v0.9.0"

    with_section = ssh_step.get("with", {})
    assert isinstance(with_section, dict)
    ssh_private_key = with_section.get("ssh-private-key", "")
    assert isinstance(ssh_private_key, str)
    assert "${{ secrets.VPS_SSH_KEY }}" in ssh_private_key
