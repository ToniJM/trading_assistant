# AI Investment Manager - Multi-Agent ADK System

Sistema multi-agente autónomo para ejecutar, evaluar y optimizar estrategias de inversión usando Google ADK (Agent Development Kit).

## Descripción

Sistema de trading algorítmico basado en arquitectura multi-agente que ejecuta backtests, evalúa métricas y optimiza estrategias de forma autónoma. Diseñado con principios ADK-first, arquitectura hexagonal (Ports & Adapters) y contratos A2A formales.

## Requisitos

- **Python**: 3.11 o superior
- **Entorno virtual**: `.venv` (recomendado)
- **Dependencias**: Ver `requirements.txt`

## Instalación

1. Clonar el repositorio (cuando esté disponible)
2. Crear y activar entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# o
.venv\Scripts\activate  # Windows
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno (opcional):

Crear archivo `.env` con:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=colored  # colored, json, plain
```

## Estructura del Proyecto

```
trading/
├── src/trading/              # Código fuente principal
│   ├── agents/               # Agentes ADK
│   │   ├── base_agent.py     # BaseAgent (clase base)
│   │   ├── orchestrator_agent.py  # OrchestratorAgent
│   │   ├── simulator_agent.py     # SimulatorAgent
│   │   └── backtest_agent.py      # BacktestAgent
│   ├── domain/               # Capa de dominio (Hexagonal)
│   │   ├── entities.py       # Entidades: Candle, Order, Trade, Position, Cycle
│   │   ├── messages.py       # Contratos Pydantic para mensajería A2A
│   │   ├── ports.py          # Interfaces/Ports: ExchangePort, MarketDataPort
│   │   └── types.py          # Tipos del dominio
│   ├── infrastructure/       # Capa de infraestructura
│   │   ├── backtest/         # Sistema de backtest
│   │   ├── exchange/         # Simulador de exchange
│   │   ├── simulator/        # Simulador de mercado
│   │   └── logging/          # Sistema de logging estructurado
│   └── strategies/           # Estrategias de trading
│       └── carga_descarga/   # Estrategia carga-descarga
├── tests/                    # Suite de tests
├── scripts/                  # Scripts de utilidad
│   └── run_backtest.py      # Script para ejecutar backtests
├── docs/                     # Documentación
│   ├── architecture.md       # Arquitectura del sistema
│   ├── runbook.md            # Guía de operación
│   └── market_data.md        # Configuración de datos de mercado
├── logs/                     # Logs del sistema (gitignored)
├── pyproject.toml            # Configuración del proyecto
├── requirements.txt          # Dependencias
└── pytest.ini                # Configuración de pytest
```

## Uso Básico

### Ejecutar un Backtest

Usando el script de línea de comandos:

```bash
python scripts/run_backtest.py \
  --symbol BTCUSDT \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-31T23:59:59Z \
  --strategy carga_descarga \
  --initial-balance 2500 \
  --leverage 100
```

### Usar los Agentes Programáticamente

```python
from trading.agents import OrchestratorAgent
from trading.domain.messages import StartBacktestRequest
from trading.strategies.factory import create_strategy_factory

# Crear orquestador
orchestrator = OrchestratorAgent(run_id="my_run_001")
orchestrator.initialize()

# Crear request de backtest
request = StartBacktestRequest(
    symbol="BTCUSDT",
    start_time=1704067200000,  # timestamp en ms
    end_time=None,  # None = hasta el momento actual
    strategy_name="carga_descarga",
    initial_balance=Decimal("2500"),
    leverage=Decimal("100"),
)

# Ejecutar backtest
strategy_factory = create_strategy_factory(strategy_name="carga_descarga")
results = orchestrator.run_backtest(request, strategy_factory=strategy_factory)

print(f"Retorno: {results.return_percentage:.2f}%")
print(f"Win rate: {results.win_rate:.2f}%")
print(f"Profit factor: {results.profit_factor:.2f}")

orchestrator.close()
```

## Agentes del Sistema

- **OrchestratorAgent**: Coordina backtests, recibe resultados y dispara optimizaciones
- **SimulatorAgent**: Provee velas e historial de precios para backtests
- **BacktestAgent**: Ejecuta backtests de estrategias
- **EvaluatorAgent** (futuro): Analiza métricas y genera reportes
- **OptimizerAgent** (futuro): Ajusta parámetros de estrategias
- **RegistryAgent** (futuro): Almacena resultados y métricas

## Tests

Ejecutar todos los tests:

```bash
pytest tests/
```

Ejecutar tests con cobertura:

```bash
pytest tests/ --cov=src/trading --cov-report=html
```

Ver estructura de tests en `tests/README.md`.

## Logging

El sistema genera logs estructurados:

- **Log diario**: `logs/app.log` (rotación diaria)
- **Log por ejecución**: `logs/runs/run_{run_id}.log`
- **Log por backtest**: `logs/backtests/backtest_{backtest_id}.log`

Los logs incluyen contexto ADK: `run_id`, `agent`, `flow` para trazabilidad completa.

## Documentación

- **[Arquitectura](docs/architecture.md)**: Diseño del sistema multi-agente
- **[Runbook](docs/runbook.md)**: Guía de operación y troubleshooting
- **[Market Data](docs/market_data.md)**: Configuración de datos de mercado

## Desarrollo

### Linting

```bash
ruff check src/
ruff format src/
```

### Type Checking

```bash
mypy src/
```

### Convenciones

- **Arquitectura**: ADK-first, Hexagonal (Ports & Adapters)
- **Contratos**: Pydantic para mensajes A2A
- **Testing**: pytest con fixtures deterministas
- **Logging**: Estructurado con contexto ADK

## KPIs del Sistema

- **Sharpe Ratio**: ≥ 2.0
- **Max Drawdown**: ≤ 10%
- **Profit Factor**: ≥ 1.5
- **Cobertura de tests**: ≥ 80%
- **Runtime por ciclo**: ≤ 5 min
- **Reproducibilidad**: 100% determinista con semilla fija

## Estado del Proyecto

El proyecto está en desarrollo activo. Ver `REVIEW.md` para el estado actual de componentes implementados.

## Licencia

[Por definir]

## Contribuciones

[Por definir]

