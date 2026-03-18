# Sachin Kolige Premier League — Dev Shortcuts
# Usage: make <command>

.PHONY: reset test check migrate shell logs clean fresh help

## Wipe DB, re-migrate, recreate superuser (full dev reset)
reset:
	.venv/bin/python dev_reset.py

## Run migrations only
migrate:
	.venv/bin/python manage.py migrate

## Run all tests (dev only — skipped on Render/production)
test:
	@if [ "$$RENDER" != "true" ]; then \
		.venv/bin/pytest auction/tests/ -v; \
	else \
		echo "Skipping tests on production (RENDER=true)"; \
	fi

## Quick Django system check — no tests, just config validation
check:
	.venv/bin/python manage.py check

## Open Django shell
shell:
	.venv/bin/python manage.py shell

## Tail all three log files live
logs:
	@mkdir -p logs
	@touch logs/auction.log logs/system.log logs/error.log
	tail -f logs/auction.log logs/system.log logs/error.log

## Delete all .pyc files and __pycache__ folders
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

## Full fresh start: clean → reset (run make test separately if needed)
fresh:
	@echo "==> Cleaning..."
	@$(MAKE) clean
	@echo "==> Resetting DB..."
	@$(MAKE) reset
	@echo "==> Done! Now run: .venv/bin/python manage.py runserver (and make logs in another terminal)"

## Show available commands
help:
	@echo ""
	@echo "  make reset    — wipe DB and re-migrate (dev only)"
	@echo "  make migrate  — run migrations"
	@echo "  make test     — run pytest (skipped on production)"
	@echo "  make check    — Django config check"
	@echo "  make shell    — Django shell"
	@echo "  make logs     — tail all log files"
	@echo "  make clean    — remove .pyc and __pycache__"
	@echo "  make fresh    — clean + reset (wipe DB, regenerate migrations)"
	@echo ""
