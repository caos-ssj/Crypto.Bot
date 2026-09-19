VENV := venv/bin

.PHONY: check test lint format format-check coverage

## Ejecuta el gate completo de QA local (mismos chequeos que el CI + cobertura)
check: lint format-check coverage

## Tests unitarios
test:
	$(VENV)/python -m pytest tests/ -q

## Análisis estático (ruff)
lint:
	$(VENV)/ruff check src/ tests/

## Formatea el código con black (no toca dashboard.py)
format:
	$(VENV)/black src/ tests/

## Verifica formato sin modificar (igual que el CI)
format-check:
	$(VENV)/black --check src/ tests/

## Cobertura con umbral bloqueante
coverage:
	$(VENV)/python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=60