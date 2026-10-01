# Demo: kör evalen mot boten före (körning 1) och efter fixarna (körning 2).

# Falsk nyckel, bara för demot. Fast värde så att bot och eval alltid får samma.
export CHATBOT_SECRET ?= sk-demo-4f9c2a7e81d3b6c05e9a1f72
OLLAMA_URL ?= http://127.0.0.1:11434
OLLAMA_MODEL ?= qwen3.8:latest

BEFORE_REF := 02c820a
AFTER_REF := aadad23
BEFORE_PORT := 8001
AFTER_PORT := 8000
DEMO_DIR := .demo
PYTHON := .venv/bin/python
REPEAT ?= 3
REPORT ?= resultat.md

.PHONY: help warmup before after diff stop test

help:
	@echo "make warmup  ladda modellen i Ollama (undvik kallstart)"
	@echo "make before  starta boten från körning 1 på :$(BEFORE_PORT) och kör evalen"
	@echo "make after   starta nuvarande boten på :$(AFTER_PORT) och kör evalen"
	@echo "make diff    visa fixarna mellan körning 1 och 2"
	@echo "make stop    stäng av båda botarna"
	@echo "make test    kör enhetstesterna"

$(PYTHON): pyproject.toml uv.lock
	uv sync --quiet
	@touch $@

warmup:
	@curl -sf $(OLLAMA_URL)/api/generate -d '{"model": "$(OLLAMA_MODEL)", "keep_alive": "60m"}' >/dev/null \
		&& echo "$(OLLAMA_MODEL) laddad" \
		|| { echo "Kan inte nå Ollama på $(OLLAMA_URL)"; exit 1; }

before: $(PYTHON)
	@rm -rf $(DEMO_DIR)/before && mkdir -p $(DEMO_DIR)/before
	@git archive $(BEFORE_REF) bot | tar -x -C $(DEMO_DIR)/before
	@$(MAKE) --no-print-directory _start NAME=before APP=$(DEMO_DIR)/before/bot/app.py PORT=$(BEFORE_PORT)
	-$(PYTHON) run_evals.py --repeat $(REPEAT) --report $(REPORT) --bot-ref $(BEFORE_REF) --title "Demo – före fixarna" --url http://localhost:$(BEFORE_PORT)/chat
	@echo "Boten från körning 1 kör på http://localhost:$(BEFORE_PORT)"

after: $(PYTHON)
	@$(MAKE) --no-print-directory _start NAME=after APP=bot/app.py PORT=$(AFTER_PORT)
	-$(PYTHON) run_evals.py --repeat $(REPEAT) --report $(REPORT) --title "Demo – efter fixarna" --url http://localhost:$(AFTER_PORT)/chat
	@echo "Nuvarande boten kör på http://localhost:$(AFTER_PORT)"

diff:
	@git --no-pager diff $(BEFORE_REF) $(AFTER_REF) -- bot/

stop:
	@for name in before after; do \
		pidfile=$(DEMO_DIR)/$$name.pid; \
		if [ -f $$pidfile ]; then kill $$(cat $$pidfile) 2>/dev/null; rm -f $$pidfile; echo "stoppade $$name"; fi; \
	done

test: $(PYTHON)
	$(PYTHON) -m unittest discover tests

# Startar en bot i bakgrunden om den inte redan kör. Evalen väntar själv tills den svarar.
_start:
	@mkdir -p $(DEMO_DIR)
	@if [ -f $(DEMO_DIR)/$(NAME).pid ] && kill -0 $$(cat $(DEMO_DIR)/$(NAME).pid) 2>/dev/null; then \
		echo "$(NAME)-boten kör redan"; \
	else \
		PORT=$(PORT) OLLAMA_URL=$(OLLAMA_URL) OLLAMA_MODEL=$(OLLAMA_MODEL) \
			nohup $(PYTHON) $(APP) > $(DEMO_DIR)/$(NAME).log 2>&1 & echo $$! > $(DEMO_DIR)/$(NAME).pid; \
		echo "startade $(NAME)-boten på :$(PORT) (logg: $(DEMO_DIR)/$(NAME).log)"; \
	fi
