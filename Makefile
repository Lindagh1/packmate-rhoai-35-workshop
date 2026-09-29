ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SHELL := /bin/bash

.PHONY: preflight prepare-workshop verify-workshop diagnose reset-participant cleanup workshop-ready test

preflight:
	@bash "$(ROOT)/scripts/preflight.sh"

prepare-workshop:
	@bash "$(ROOT)/scripts/prepare-workshop.sh"

verify-workshop:
	@bash "$(ROOT)/scripts/verify-workshop.sh"

diagnose:
	@bash "$(ROOT)/scripts/diagnose.sh"

reset-participant:
	@bash "$(ROOT)/scripts/reset-participant.sh"

cleanup:
	@bash "$(ROOT)/scripts/cleanup.sh"

workshop-ready: preflight prepare-workshop verify-workshop

test:
	@set -euo pipefail; \
	  cd "$(ROOT)/app/backend" && python3 -m venv .venv && .venv/bin/pip -q install -U pip && .venv/bin/pip -q install -r requirements-dev.txt && PYTHONPATH=. .venv/bin/pytest -q; \
	  cd "$(ROOT)/mcp/weather" && python3 -m venv .venv && .venv/bin/pip -q install -U pip && .venv/bin/pip -q install -r requirements-dev.txt && PYTHONPATH=src .venv/bin/pytest -q; \
	  cd "$(ROOT)/mcp/baggage" && python3 -m venv .venv && .venv/bin/pip -q install -U pip && .venv/bin/pip -q install -r requirements-dev.txt && PYTHONPATH=src .venv/bin/pytest -q
