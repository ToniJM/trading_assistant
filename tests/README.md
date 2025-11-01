# Test Suite

Estructura de tests organizada por capas, reflejando la arquitectura del código fuente.

## Estructura

```
tests/
├── __init__.py
├── conftest.py                 # Configuración global de pytest
├── domain/                     # Tests de la capa de dominio
│   ├── __init__.py
│   ├── test_domain_entities.py  # Entities: Candle, Order, Position, Cycle, Trade
│   ├── test_domain_types.py     # Types: SIDE_TYPE, ORDER_SIDE_TYPE, etc.
│   └── test_messages.py         # Contratos Pydantic para mensajería A2A
└── infrastructure/             # Tests de la capa de infraestructura
    ├── __init__.py
    ├── backtest/
    │   ├── __init__.py
    │   └── test_backtest_config.py  # BacktestConfig, BacktestResults
    ├── exchange/
    │   ├── __init__.py
    │   └── test_exchange_repositories.py  # AccountRepository, OrdersRepository, TradesRepository
    ├── logging/
    │   ├── __init__.py
    │   └── test_logging.py  # Sistema de logging con contexto ADK
    └── simulator/
        ├── __init__.py
        └── test_simulator.py  # MarketDataSimulator y constantes
```

## Ejecutar Tests

```bash
# Todos los tests
pytest tests/

# Tests de una capa específica
pytest tests/domain/
pytest tests/infrastructure/

# Tests de un módulo específico
pytest tests/infrastructure/backtest/
pytest tests/infrastructure/exchange/
pytest tests/infrastructure/logging/
pytest tests/infrastructure/simulator/

# Tests de un archivo específico
pytest tests/domain/test_messages.py

# Con cobertura
pytest tests/ --cov=src/trading --cov-report=html
```

## Cobertura Actual

- **Domain**: 21 tests (entities, types, messages)
- **Infrastructure - Backtest**: 5 tests (config)
- **Infrastructure - Exchange**: 4 tests (repositories)
- **Infrastructure - Logging**: 5 tests (logging system)
- **Infrastructure - Simulator**: 5 tests (simulator)

**Total: 40 tests**

## Convenciones

1. **Naming**: `test_<module>_<feature>.py`
2. **Structure**: Reflejar estructura de `src/trading/`
3. **Fixtures**: Colocar en `conftest.py` según alcance necesario
4. **Imports**: Usar imports absolutos desde `trading.*`

