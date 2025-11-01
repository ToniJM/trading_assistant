# Runbook - Guía de Operación

Guía práctica para operar, monitorear y solucionar problemas del sistema AI Investment Manager.

## Configuración Inicial

### 1. Entorno Virtual

```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar (macOS/Linux)
source .venv/bin/activate

# Activar (Windows)
.venv\Scripts\activate
```

### 2. Instalación de Dependencias

```bash
# Instalar dependencias base
pip install -r requirements.txt

# Instalar dependencias de desarrollo (opcional)
pip install -r requirements.txt[dev]
```

### 3. Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```bash
# Logging
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=colored          # colored, json, plain

# Database (opcional)
DB_PATH=./candles.db        # Ruta a base de datos de velas

# Groq API (para agentes ADK - futuro)
GROQ_API_KEY=your_api_key   # API key de Groq
```

### 4. Preparar Datos de Mercado

El sistema necesita datos históricos de mercado. Ver `docs/market_data.md` para detalles.

La base de datos `candles.db` se creará automáticamente si no existe. El simulador cargará datos desde:
1. Base de datos local (`candles.db`)
2. API de Binance (fallback, si no hay suficientes datos locales)

## Comandos de Ejecución

### Ejecutar un Backtest

Usando el script de línea de comandos:

```bash
python scripts/run_backtest.py \
  --symbol BTCUSDT \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-31T23:59:59Z \
  --strategy carga_descarga \
  --initial-balance 2500 \
  --leverage 100 \
  --max-loss-percentage 0.5 \
  --stop-on-loss
```

**Parámetros**:
- `--symbol`: Símbolo de trading (ej: BTCUSDT, ETHUSDT)
- `--start-time`: Timestamp de inicio (ms) o formato ISO (ej: `2025-01-01T00:00:00Z`)
- `--end-time`: Timestamp de fin (ms) o formato ISO (opcional, default: actual)
- `--strategy`: Nombre de estrategia (`carga_descarga`, `default`)
- `--initial-balance`: Balance inicial (default: 2500)
- `--leverage`: Leverage (default: 100)
- `--max-notional`: Notional máximo (default: 50000)
- `--max-loss-percentage`: Porcentaje máximo de pérdida (default: 0.5 = 50%)
- `--stop-on-loss`: Detener backtest si se alcanza pérdida máxima

### Ejecutar Tests

```bash
# Todos los tests
pytest tests/

# Tests de una capa específica
pytest tests/domain/
pytest tests/infrastructure/

# Tests con cobertura
pytest tests/ --cov=src/trading --cov-report=html

# Tests en modo verbose
pytest tests/ -v

# Tests específicos
pytest tests/infrastructure/backtest/test_backtest_config.py
```

### Ejecutar Linting

```bash
# Verificar código
ruff check src/

# Formatear código
ruff format src/

# Type checking
mypy src/
```

## Monitoreo y Logs

### Estructura de Logs

El sistema genera logs estructurados en `logs/`:

```
logs/
├── app.log                      # Log diario (rotación diaria)
├── runs/
│   └── run_{run_id}.log         # Log por ejecución
└── backtests/
    └── backtest_{backtest_id}.log  # Log por backtest
```

### Visualizar Logs

```bash
# Ver log diario
tail -f logs/app.log

# Ver log de ejecución específica
cat logs/runs/run_{run_id}.log

# Ver log de backtest específico
cat logs/backtests/backtest_{backtest_id}.log

# Buscar errores en logs
grep -i error logs/app.log

# Buscar por run_id
grep "run_id=my_run_001" logs/app.log
```

### Formato de Logs

Los logs incluyen contexto ADK:

```
[2025-11-01 10:30:45.123] [INFO] [run_id=abc123] [agent=orchestrator] [flow=run_backtest] Mensaje del log
```

Campos:
- `run_id`: Identificador único de ejecución
- `agent`: Nombre del agente (orchestrator, simulator, backtest)
- `flow`: Flujo de orquestación actual (run_backtest, init, etc.)

### Logs en Modo JSON

Si `LOG_FORMAT=json`, los logs se generan en formato JSON:

```json
{
  "timestamp": "2025-11-01T10:30:45.123Z",
  "level": "INFO",
  "run_id": "abc123",
  "agent": "orchestrator",
  "flow": "run_backtest",
  "message": "Iniciando backtest"
}
```

## Troubleshooting

### Problema: Backtest no inicia

**Síntomas**: El backtest no se ejecuta o falla inmediatamente.

**Diagnóstico**:

1. Verificar que los datos de mercado estén disponibles:
```bash
ls -lh candles.db
sqlite3 candles.db ".tables"
```

2. Verificar logs:
```bash
grep -i error logs/app.log
tail -n 50 logs/app.log
```

3. Verificar que el símbolo esté configurado:
```python
from trading.infrastructure.simulator.simulator import MarketDataSimulator
simulator = MarketDataSimulator(is_backtest=True)
simulator.add_symbol("BTCUSDT")
```

**Soluciones**:
- Asegurar que `candles.db` existe y tiene datos
- Verificar que el símbolo esté en formato correcto (ej: `BTCUSDT`)
- Verificar que los timestamps sean válidos (en milisegundos)
- Revisar logs para errores específicos

### Problema: Backtest muy lento

**Síntomas**: El backtest tarda mucho tiempo en ejecutarse.

**Diagnóstico**:

1. Verificar número de velas:
```bash
sqlite3 candles.db "SELECT COUNT(*) FROM btcusdt_kline WHERE timeframe='1m';"
```

2. Verificar configuración de logging:
```bash
grep LOG_LEVEL .env
```

3. Verificar rendimiento de base de datos:
```bash
sqlite3 candles.db "PRAGMA journal_mode;"
sqlite3 candles.db "PRAGMA synchronous;"
```

**Soluciones**:
- Reducir rango de tiempo del backtest
- Configurar `LOG_LEVEL=WARNING` durante backtests
- Verificar que la base de datos tenga índices apropiados
- Usar modo backtest optimizado (configuración automática)

### Problema: Error de memoria

**Síntomas**: El sistema se queda sin memoria durante backtests largos.

**Diagnóstico**:

1. Verificar uso de memoria:
```bash
ps aux | grep python
```

2. Verificar tamaño de datos:
```bash
du -sh candles.db
du -sh logs/
```

**Soluciones**:
- Reducir rango de tiempo del backtest
- Procesar datos en chunks más pequeños
- Limpiar logs antiguos:
```bash
find logs/ -type f -name "*.log" -mtime +30 -delete
```

### Problema: Datos de mercado faltantes

**Síntomas**: El backtest falla porque no hay suficientes datos históricos.

**Diagnóstico**:

1. Verificar datos disponibles:
```bash
sqlite3 candles.db "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM btcusdt_kline WHERE timeframe='1m';"
```

2. Verificar que el simulador pueda cargar desde API:
```python
from trading.infrastructure.simulator.adapters.candles_repository import CandlesRepository
repo = CandlesRepository(is_backtest=False)
candles = repo.get_candles("BTCUSDT", "1m", limit=100, start_time=1704067200000)
```

**Soluciones**:
- Cargar datos manualmente desde API de Binance
- Verificar conexión a internet
- Verificar que el símbolo y timeframe sean correctos
- Crear script de carga de datos históricos

### Problema: Estrategia no encontrada

**Síntomas**: Error al intentar usar una estrategia.

**Diagnóstico**:

1. Verificar estrategias disponibles:
```bash
python -c "from trading.strategies.factory import get_available_strategies; print(get_available_strategies())"
```

2. Verificar que la estrategia esté registrada:
```bash
ls -la src/trading/strategies/
```

**Soluciones**:
- Usar una estrategia disponible: `carga_descarga` o `default`
- Verificar que la estrategia esté implementada en `strategies/`
- Verificar que la estrategia esté registrada en `factory.py`

### Problema: Tests fallan

**Síntomas**: Los tests no pasan.

**Diagnóstico**:

1. Ejecutar tests con más detalle:
```bash
pytest tests/ -v --tb=short
```

2. Verificar configuración de pytest:
```bash
cat pytest.ini
```

3. Verificar que las dependencias estén instaladas:
```bash
pip list | grep pytest
```

**Soluciones**:
- Instalar dependencias de desarrollo: `pip install -r requirements.txt[dev]`
- Verificar que el entorno virtual esté activado
- Ejecutar tests individualmente para identificar el problema
- Revisar logs de errores específicos

## KPIs y Métricas

### Métricas de Backtest

El sistema calcula automáticamente:

- **Retorno total**: Porcentaje de ganancia/pérdida
- **Win rate**: Porcentaje de trades ganadores
- **Profit factor**: Ratio de ganancias/pérdidas
- **Max drawdown**: Máxima caída desde el pico
- **Sharpe Ratio**: Ratio de retorno ajustado por riesgo
- **Ciclos**: Métricas de ciclos de trading completos

### Verificar KPIs

```python
from trading.agents import OrchestratorAgent
from trading.domain.messages import StartBacktestRequest

orchestrator = OrchestratorAgent()
orchestrator.initialize()

results = orchestrator.run_backtest(request, strategy_factory)

# Verificar KPIs
assert results.return_percentage > 0
assert results.win_rate >= 50.0
assert results.profit_factor >= 1.5
assert results.max_drawdown <= 10.0
```

### KPIs del Sistema

- **Sharpe Ratio**: ≥ 2.0
- **Max Drawdown**: ≤ 10%
- **Profit Factor**: ≥ 1.5
- **Coverage de tests**: ≥ 80%
- **Runtime por ciclo**: ≤ 5 min
- **Reproducibilidad**: 100% determinista con semilla fija

## Políticas de Riesgo

### Límites Configurables

```python
# Políticas del OrchestratorAgent
policies = {
    "max_concurrent_backtests": {"max": 1},
    "max_backtests_per_run": {"max": 10},
}

# Configuración de backtest
config = BacktestConfig(
    stop_on_loss=True,
    max_loss_percentage=0.5,  # 50% máximo de pérdida
    max_notional=50000,        # Notional máximo
)
```

### Fail Fast

El sistema aborta ejecución si:
- Drawdown > threshold configurado
- Pérdida máxima alcanzada (si `stop_on_loss=True`)
- Límites de backtests concurrentes alcanzados

### Data Policy

- Usar solo datasets aprobados (fuentes verificadas)
- Validar datos antes de ejecutar backtests
- Verificar integridad de datos históricos

## Mantenimiento

### Limpieza de Logs

```bash
# Eliminar logs antiguos (más de 30 días)
find logs/ -type f -name "*.log" -mtime +30 -delete

# Limpiar logs de ejecuciones antiguas
find logs/runs/ -type f -mtime +7 -delete
```

### Limpieza de Base de Datos

```bash
# Backup antes de limpiar
cp candles.db candles.db.backup

# Vaciar tablas antiguas (si es necesario)
sqlite3 candles.db "DELETE FROM btcusdt_kline WHERE timestamp < 1609459200000;"
```

### Actualizar Dependencias

```bash
# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Verificar vulnerabilidades (si pip-audit está instalado)
pip-audit
```

## Escalabilidad

### Optimización de Rendimiento

- **Modo backtest**: Configuración automática optimizada
- **Base de datos**: PRAGMA optimizado para backtests
- **Logging**: Reducción de verbosidad durante backtests
- **Procesamiento**: Procesamiento por chunks

### Paralelización (Futuro)

- Ejecutar múltiples backtests concurrentes
- Procesar múltiples símbolos en paralelo
- Optimización paralela de parámetros

## Recursos Adicionales

- **Arquitectura**: Ver `docs/architecture.md`
- **Market Data**: Ver `docs/market_data.md`
- **Tests**: Ver `tests/README.md`

## Soporte

Para reportar problemas o solicitar ayuda:

1. Revisar logs: `logs/app.log`, `logs/runs/`, `logs/backtests/`
2. Verificar configuración: `.env`, `pyproject.toml`
3. Ejecutar tests: `pytest tests/ -v`
4. Documentar el problema con logs y configuración

