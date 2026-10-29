PYTHON := .venv/bin/python
export PYTHONPATH := src
.PHONY: test validate app run ingest build-data train alerts rank pipeline snapshot check ci compile snapshot-verify

test:
	$(PYTHON) -m pytest -q

validate:
	$(PYTHON) -m pytest -q tests/test_contracts.py

compile:
	$(PYTHON) -m compileall src app tests -q

snapshot-verify:
	$(PYTHON) -m fundflow.cli snapshot --verify

check: compile validate snapshot-verify test

ci: check

app:
	$(PYTHON) -m streamlit run app/Home.py

run:
	$(PYTHON) -m fundflow.cli --offline all

ingest:
	$(PYTHON) -m fundflow.cli ingest

build-data:
	$(PYTHON) -m fundflow.cli build-data

train:
	$(PYTHON) -m fundflow.cli train

alerts:
	$(PYTHON) -m fundflow.cli alerts

rank:
	$(PYTHON) -m fundflow.cli rank

pipeline:
	$(PYTHON) -m fundflow.cli --offline all

snapshot:
	$(PYTHON) -m fundflow.cli snapshot
