# ICT3113 Assignment 1 -- Group P2-9
# Team number 9 -> dataset rows 9000-9999.
SHELL := /bin/bash
TEAM  ?= 9
SRC   ?= $(HOME)/Downloads/ict3113_tickets.csv
BASE  ?= http://localhost:8000
MODEL ?= llama3.2:1b

.PHONY: help slice golden sheets agree merge feed up down reset logs accuracy freeze check

help:
	@echo "Step 1 -- golden set"
	@echo "  make slice       extract rows $$(( $(TEAM) * 1000 ))-$$(( $(TEAM) * 1000 + 999 ))"
	@echo "  make golden      sample 175 candidates (labels hidden from annotators)"
	@echo "  make sheets      generate blank label sheets A and B"
	@echo "  make agree       kappa + disagreement worklist"
	@echo "  make merge       build frozen golden_set.csv"
	@echo "  make freeze      pre-flight checks before committing the freeze"
	@echo ""
	@echo "Step 2 -- service"
	@echo "  make up          docker compose up (OLLAMA_MODEL=$(MODEL))"
	@echo "  make down        stop"
	@echo "  make reset       stop AND wipe stored tickets (service must start empty)"
	@echo "  make check       smoke test the three endpoints"
	@echo ""
	@echo "Step 5 -- measure"
	@echo "  make feed        build JMeter feed files"
	@echo "  make accuracy    run the golden set through the service"

slice:
	python3 tools/extract_slice.py --source "$(SRC)" --team $(TEAM)

golden:
	python3 tools/sample_golden.py --n 175

sheets:
	python3 tools/make_label_sheets.py

# Picks up whatever annotator sheets exist, whatever they are named.
SHEETS ?= $(wildcard golden/labels_*.csv)

agree:
	@test -n "$(SHEETS)" || { echo "no golden/labels_*.csv sheets found -- run 'make sheets'"; exit 1; }
	@echo "sheets: $(SHEETS)"
	python3 tools/agreement.py --sheets $(SHEETS)

merge:
	@test -n "$(SHEETS)" || { echo "no golden/labels_*.csv sheets found"; exit 1; }
	python3 tools/merge_golden.py --sheets $(SHEETS)

feed:
	python3 tools/prepare_jmeter_data.py

up:
	OLLAMA_MODEL=$(MODEL) TEAM_NUMBER=$(TEAM) docker compose up -d --build
	@echo "waiting for service..."
	@until curl -sf $(BASE)/healthz >/dev/null; do sleep 2; done
	@curl -s $(BASE)/healthz; echo
	@echo "pull the model if needed:  docker exec triage-ollama ollama pull $(MODEL)"

down:
	docker compose down

reset:
	docker compose down -v
	rm -f results/logs/requests.jsonl
	@echo "storage and logs cleared -- the service will start empty"

logs:
	tail -f results/logs/requests.jsonl

check:
	@echo "--- POST /tickets ---"
	@curl -s -X POST $(BASE)/tickets -H 'Content-Type: application/json' \
	  -d '{"narrative":"My mortgage servicer applied my payment to escrow instead of principal and now reports me late.","row_id":"smoke"}' | python3 -m json.tool
	@echo "--- GET /search?q=mortgage ---"
	@curl -s "$(BASE)/search?q=mortgage&limit=3" | python3 -m json.tool
	@echo "--- GET /stats ---"
	@curl -s $(BASE)/stats | python3 -m json.tool

accuracy:
	python3 tools/accuracy_harness.py --base $(BASE) --model $(MODEL)

freeze:
	@bash tools/freeze_check.sh
