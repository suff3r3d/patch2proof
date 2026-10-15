.PHONY: compile test lint demo verify

compile:
	python3 -m compileall -q src tests

verify:
	PYTHONPATH=src python scripts/verify_scaffold.py

test:
	pytest

lint:
	ruff check src tests

demo:
	PYTHONPATH=src python -m patch2proof.cli run examples/demo_case.yaml --dry-run --auto-approve
