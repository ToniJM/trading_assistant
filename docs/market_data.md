# Market Data Setup

## Database Location

El simulador de mercado usa una base de datos SQLite llamada `candles.db` en el directorio raíz del proyecto.

## Loading Candles

El `CandlesRepository` puede cargar candles desde:

1. **Base de datos local (`candles.db`)**: Si existen candles en la base de datos para el símbolo y timeframe solicitado, los carga directamente.

2. **API de Binance (fallback)**: Si no hay suficientes candles en la base de datos, el simulador intentará obtenerlos desde la API de Binance y los guardará en la base de datos para uso futuro.

## Verificación de Datos

Para verificar que tienes datos de mercado:

```bash
# Verificar si existe la base de datos
ls -lh candles.db

# Verificar tablas (requiere sqlite3)
sqlite3 candles.db ".tables"
```

## Cargar Datos Manualmente

Si necesitas cargar datos históricos manualmente, puedes usar el adaptador de Binance directamente o escribir un script que use `MarketDataAdapter`.

## Base de Datos por Defecto

- **Archivo**: `candles.db` (directorio raíz del proyecto)
- **Formato**: SQLite
- **Tablas**: `{symbol}_kline` (ej: `btcusdt_kline`)
- **Columnas**: timeframe, timestamp, open_price, high_price, low_price, close_price, volume

## Optimización para Backtests

Cuando se ejecuta en modo backtest (`is_backtest=True`), el repositorio se configura con:
- `PRAGMA synchronous=OFF`
- `PRAGMA journal_mode=MEMORY`
- `PRAGMA temp_store=MEMORY`
- `PRAGMA locking_mode=EXCLUSIVE`
- `PRAGMA cache_size=50000`

Esto maximiza el rendimiento durante los backtests.

