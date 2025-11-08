# Arquitectura del Sistema - AI Investment Manager

## Visión General

Sistema multi-agente autónomo para ejecutar, evaluar y optimizar estrategias de inversión usando **Google ADK (Agent Development Kit)**. Diseñado con arquitectura hexagonal (Ports & Adapters) y mensajería A2A (Agent-to-Agent) con contratos formales.

## Principios Arquitectónicos

### ADK-First

Los agentes están definidos como:
- **Rol**: Función específica del agente en el sistema
- **Herramientas**: Capacidades y recursos disponibles
- **Memoria**: Almacenamiento episódico y vectorial
- **Políticas**: Reglas de negocio y límites de ejecución

### Hexagonal Architecture (Ports & Adapters)

- **Domain Layer**: Entidades puras, puertos (interfaces) y contratos A2A
- **Infrastructure Layer**: Adaptadores que implementan los puertos
- **Bajo acoplamiento**: El dominio no depende de infraestructura

### Contratos Fuertes (A2A)

- **Pydantic Models**: Validación y serialización de mensajes
- **Versionado**: Contratos versionados para compatibilidad
- **Idempotencia**: Mensajes y acciones re-ejecutables

### Observabilidad

- **Trazabilidad**: Cada acción trazada por `run_id`, `agent`, `flow`
- **Logging estructurado**: Logs en formato JSON y texto
- **Métricas**: Métricas por agente, flujo y ejecución

## Componentes Principales

### Agentes ADK

#### 1. OrchestratorAgent

**Rol**: Coordinar backtests, recibir resultados y disparar optimizaciones

**Herramientas**:
- `SimulatorAgent`: Para obtener datos de mercado
- `BacktestAgent`: Para ejecutar backtests
- `EvaluatorAgent`: Para evaluar resultados de backtests
- `OptimizerAgent`: Para optimizar parámetros usando IA

**Políticas**:
- `max_concurrent_backtests`: Límite de backtests simultáneos
- `max_backtests_per_run`: Límite de backtests por ejecución

**Memoria**:
- Estado de backtests activos
- Resultados de backtests completados
- Historial de decisiones

**Contratos A2A**:
- Recibe: `StartBacktestRequest`
- Envía: `BacktestResultsResponse`, `ErrorResponse`

#### 2. SimulatorAgent

**Rol**: Proveer velas e historial de precios para backtests

**Herramientas**:
- `MarketDataSimulator`: Simulador de datos de mercado
- `CandlesRepository`: Repositorio de velas históricas

**Memoria**:
- Estado de simulación (tiempos, símbolos, timeframes)
- Cache de velas procesadas

**Contratos A2A**:
- Expone datos de mercado vía `MarketDataPort`

#### 3. BacktestAgent

**Rol**: Ejecutar backtests de estrategias de trading

**Herramientas**:
- `BacktestRunner`: Ejecutor de backtests
- `BacktestExchangeAdapter`: Adaptador de exchange para backtests
- `BacktestMarketDataAdapter`: Adaptador de market data para backtests

**Memoria**:
- Configuración del backtest actual
- Métricas en tiempo real

**Contratos A2A**:
- Recibe: `StartBacktestRequest`
- Envía: `BacktestResultsResponse`, `BacktestStatusUpdate`

#### 4. EvaluatorAgent

**Rol**: Analizar métricas y generar reportes cuantitativos

**Herramientas**:
- Métricas: Sharpe Ratio, Calmar Ratio, Drawdown, Profit Factor, etc.
- Generación de reportes y recomendaciones

**Políticas**:
- KPIs por defecto: Sharpe Ratio ≥ 2.0, Max Drawdown ≤ 10%, Profit Factor ≥ 1.5
- KPIs configurables vía `EvaluationRequest.kpis`

**Memoria**:
- Historial de evaluaciones
- Métricas calculadas por run

**Contratos A2A**:
- Recibe: `EvaluationRequest` y `BacktestResultsResponse`
- Envía: `EvaluationResponse` con métricas, cumplimiento de KPIs y recomendación

#### 5. OptimizerAgent

**Rol**: Ajustar parámetros de estrategias usando IA (Groq LLM)

**Herramientas**:
- Cliente Groq LLM para análisis inteligente
- Acceso a memoria episódica (historial de backtests)
- Validación de parámetros sugeridos

**Memoria**:
- Historial de optimizaciones
- Contexto de backtests previos

**Políticas**:
- `max_optimization_iterations`: Límite de iteraciones (default: 5)
- `min_confidence_threshold`: Confianza mínima para aplicar cambios (default: 0.5)

**Contratos A2A**:
- Recibe: `OptimizationRequest` con parámetros actuales y espacio de búsqueda
- Envía: `OptimizationResult` con parámetros optimizados, razonamiento, confianza y mejoras esperadas

**Funcionalidad**:
- Analiza métricas históricas usando LLM
- Sugiere ajustes de parámetros basados en patrones
- Proporciona razonamiento explicativo de los cambios
- Fallback a optimización determinística si LLM no disponible

#### 6. RegistryAgent (Futuro)

**Rol**: Almacenar resultados, métricas y decisiones

**Herramientas**:
- Base de datos de resultados
- Vector store para embeddings de métricas

**Memoria**:
- Historial completo de ejecuciones
- Métricas consolidadas

## Capa de Dominio

### Entidades (`domain/entities.py`)

- **Candle**: Vela de precio OHLCV
- **Order**: Orden de trading
- **Trade**: Trade ejecutado
- **Position**: Posición abierta
- **Cycle**: Ciclo de trading completo
- **SymbolInfo**: Información del símbolo

### Puertos (`domain/ports.py`)

Interfaces que definen contratos entre capas:

- **ExchangePort**: Operaciones de exchange (place_order, cancel_order, get_account)
- **MarketDataPort**: Datos de mercado (get_candles, subscribe_to_updates)
- **OperationsStatusRepositoryPort**: Repositorio de estado de operaciones
- **CycleListenerPort**: Listener para ciclos de trading

### Mensajes A2A (`domain/messages.py`)

Contratos Pydantic para comunicación entre agentes:

- **StartBacktestRequest**: Solicitud de backtest
- **BacktestResultsResponse**: Resultados del backtest
- **BacktestStatusUpdate**: Actualización de estado durante backtest
- **OptimizationRequest**: Solicitud de optimización con espacio de parámetros
- **OptimizationResult**: Resultado de optimización con parámetros sugeridos y razonamiento
- **ErrorResponse**: Respuesta de error

## Capa de Infraestructura

### Backtest (`infrastructure/backtest/`)

- **BacktestRunner**: Ejecutor principal de backtests
- **BacktestConfig**: Configuración del backtest
- **BacktestResults**: Resultados con métricas
- **BacktestExchangeAdapter**: Adaptador de exchange para backtests
- **BacktestMarketDataAdapter**: Adaptador de market data para backtests
- **CyclesRepository**: Persistencia de ciclos de trading
- **EventDispatcher**: Dispatcher de eventos de ciclos

### Exchange (`infrastructure/exchange/`)

- **Exchange**: Simulador de exchange para backtests
- **AccountRepository**: Repositorio de cuenta
- **OrdersRepository**: Repositorio de órdenes
- **TradesRepository**: Repositorio de trades

### Simulator (`infrastructure/simulator/`)

- **MarketDataSimulator**: Simulador de datos de mercado
- **CandlesRepository**: Repositorio de velas históricas
- **MarketDataAdapter**: Adaptador de market data

### Evaluation (`infrastructure/evaluation/`)

- **metrics.py**: Cálculo de métricas avanzadas (Sharpe Ratio, Calmar Ratio)
- **extract_metrics_from_results()**: Extracción de métricas desde `BacktestResultsResponse`

### LLM (`infrastructure/llm/`)

- **groq_client.py**: Cliente Groq para integración con LLM
- **GroqClient**: Cliente con métodos `chat()` y `chat_json()` para llamadas estructuradas
- **get_groq_client()**: Singleton para obtener instancia del cliente
- Configuración desde `.env`: `GROQ_API_KEY`, `GROQ_MODEL` (default: llama-3.3-70b-versatile)

### Logging (`infrastructure/logging/`)

- **get_logger()**: Logger principal con contexto ADK
- **get_run_logger()**: Logger por ejecución
- **get_backtest_logger()**: Logger por backtest
- **LoggingContext**: Contexto thread-local (run_id, agent, flow)
- **ADKFormatter**: Formateador con información ADK
- **ColoredADKFormatter**: Formateador con colores
- **JSONFormatter**: Formateador JSON estructurado

### Strategies (`strategies/`)

- **CargaDescargaStrategy**: Estrategia carga-descarga
- **Factory**: Factory para crear estrategias

## Flujos de Orquestación

### 1. Backtest & Evaluation Flow

```
Orchestrator → SimulatorAgent (get market data)
            → BacktestAgent (execute backtest)
            → BacktestResultsResponse
            → EvaluatorAgent (analyze metrics)
            → (If recommendation == "optimize") OptimizerAgent (optimize parameters)
            → (Futuro) RegistryAgent (store results)
```

**Pasos**:
1. `Orchestrator` recibe `StartBacktestRequest`
2. `Orchestrator` configura `SimulatorAgent` con tiempos y símbolos
3. `Orchestrator` ejecuta backtest vía `BacktestAgent`
4. `BacktestAgent` ejecuta backtest usando `BacktestRunner`
5. `Orchestrator` recibe `BacktestResultsResponse`
6. `Orchestrator` envía resultados a `EvaluatorAgent` (vía `evaluate_backtest()`)
7. `EvaluatorAgent` calcula métricas avanzadas y verifica KPIs
8. `EvaluatorAgent` retorna `EvaluationResponse` con recomendación
9. (Futuro) `Orchestrator` almacena resultados en `RegistryAgent`

### 2. Optimization Flow

```
Orchestrator → OptimizerAgent (optimize parameters using AI)
            → OptimizationResult (with reasoning and confidence)
            → Orchestrator (run new backtest with optimized params)
            → (Loop until convergence or max iterations)
```

**Pasos**:
1. `Orchestrator` detecta necesidad de optimización (evaluación recomienda "optimize")
2. `Orchestrator` recopila backtests previos de la estrategia
3. `Orchestrator` llama a `optimize_strategy()` que crea `OptimizationRequest`
4. `OptimizerAgent` construye prompt estructurado con:
   - Métricas históricas de backtests previos
   - Parámetros actuales y espacio de búsqueda
   - Objetivo de optimización (sharpe_ratio, profit_factor, etc.)
5. `OptimizerAgent` llama a Groq LLM con el prompt
6. LLM analiza patrones y sugiere parámetros optimizados con razonamiento
7. `OptimizerAgent` valida parámetros sugeridos contra espacio de búsqueda
8. `OptimizerAgent` retorna `OptimizationResult` con:
   - Parámetros optimizados validados
   - Razonamiento explicativo del LLM
   - Nivel de confianza (0.0-1.0)
   - Mejoras esperadas en métricas
9. `Orchestrator` ejecuta nuevo backtest con parámetros optimizados
10. Ciclo continúa hasta convergencia, KPIs cumplidos, o límite de iteraciones

**Fallback**: Si LLM no disponible, usa optimización determinística básica basada en heurísticas.

### 3. Promotion Flow (Futuro)

```
Orchestrator → (Check KPIs)
            → EvaluatorAgent (validate performance)
            → RegistryAgent (mark as prod-ready)
            → Generate deployable artifact
```

**Pasos**:
1. `Orchestrator` verifica KPIs mínimos
2. `Orchestrator` solicita validación a `EvaluatorAgent`
3. `EvaluatorAgent` valida rendimiento histórico y forward-test
4. `RegistryAgent` marca modelo como "prod-ready"
5. Se genera artefacto desplegable (parámetros, versión, logs)

## Sistema de Memoria

### Memoria Episódica

Cada agente almacena:
- Contexto de ejecuciones (`run_id`)
- Parámetros y configuraciones
- Resultados y decisiones
- Estado interno del agente

### Memoria Vectorial (Futuro)

- Embeddings de métricas y resultados
- Recuperación semántica de ejecuciones pasadas
- Análisis de patrones y tendencias

## Sistema de Logging

### Estructura de Logs

1. **Log diario**: `logs/app.log` (rotación diaria)
2. **Log por ejecución**: `logs/runs/run_{run_id}.log`
3. **Log por backtest**: `logs/backtests/backtest_{backtest_id}.log`

### Contexto ADK

Todos los logs incluyen:
- `run_id`: Identificador único de ejecución
- `agent`: Nombre del agente
- `flow`: Flujo de orquestación actual

### Formateadores

- **ADKFormatter**: Texto con información ADK
- **ColoredADKFormatter**: Texto con colores
- **JSONFormatter**: JSON estructurado para análisis

## Políticas y Límites

### Políticas del Sistema

- **Budget per run**: Máximo X backtests simultáneos
- **Execution limits**: 1 flujo de optimización concurrente por estrategia
- **Data policy**: Usar solo datasets aprobados (fuentes verificadas)
- **Fail fast**: Abortar ejecución si drawdown > threshold configurado

### KPIs del Sistema

- **Sharpe Ratio**: ≥ 2.0
- **Max Drawdown**: ≤ 10%
- **Profit Factor**: ≥ 1.5
- **Coverage de tests**: ≥ 80%
- **Runtime por ciclo**: ≤ 5 min
- **Reproducibilidad**: 100% determinista con semilla fija

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────┐
│                    OrchestratorAgent                    │
│  (Coordina backtests, resultados y optimizaciones)      │
└──────────────┬──────────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼───────┐
│Simulator   │    │ BacktestAgent │
│Agent       │    │ (Ejecuta      │
│(Datos      │    │  backtests)   │
│ mercado)   │    └───────┬───────┘
└───┬────────┘            │
    │                     │
┌───▼─────────────────────▼───┐
│   MarketDataSimulator        │
│   BacktestRunner            │
│   Exchange (simulado)       │
└──────────────────────────────┘
```

## Integración con Google ADK

El sistema está diseñado para integrarse con Google ADK:

- **Agentes**: Wrapped como agentes ADK con herramientas, memoria y políticas
- **Graph Runtime**: Flujos reproducibles usando ADK Graph Runtime
- **Memoria**: Memoria episódica y vectorial compatible con ADK
- **Trazabilidad**: Logs y eventos compatibles con ADK telemetry

## Extensibilidad

El sistema está diseñado para crecer:

1. **Nuevos agentes**: Implementar `BaseAgent` y definir rol/herramientas/memoria
2. **Nuevas estrategias**: Implementar interfaz de estrategia y registrar en factory
3. **Nuevos adaptadores**: Implementar puertos del dominio
4. **Nuevos contratos A2A**: Definir modelos Pydantic en `domain/messages.py`

## Seguridad y Confiabilidad

- **Idempotencia**: Todas las operaciones son re-ejecutables
- **Validación**: Contratos Pydantic validan todos los mensajes
- **Error handling**: Manejo robusto de errores con `ErrorResponse`
- **Políticas de límites**: Límites configurables para prevenir abusos
- **Reproducibilidad**: Backtests deterministas con semillas fijas

