"""Logger decorator for strategy methods"""
import functools
import logging

from trading.infrastructure.backtest.config import is_backtest_mode
from trading.infrastructure.logging import get_logger


def method_logger(nivel: int = logging.DEBUG):
    """
    Decorador para loggear automáticamente entrada, salida y errores de una función.
    En modo backtest, retorna la función sin decorar para máximo rendimiento.
    :param nivel: Nivel de logging (DEBUG por defecto)
    """
    logger = get_logger(__name__)

    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # En modo backtest, retornar la función sin decorar para máximo rendimiento
            if is_backtest_mode():
                return func(*args, **kwargs)

            # Usar self.logger si existe (para métodos de instancia)
            instancia = args[0] if args else None
            if hasattr(instancia, "logger") and isinstance(instancia.logger, logging.Logger):
                log = instancia.logger
            else:
                log = logger or get_logger(func.__module__)

            log.log(
                nivel,
                f"{func.__name__}{args[1:] if hasattr(instancia, '__class__') else args}, kwargs={kwargs}",
            )
            try:
                resultado = func(*args, **kwargs)
                if resultado is not None:
                    log.log(nivel, f"{func.__name__} = {resultado}")
                return resultado
            except Exception:
                log.exception(f"{func.__name__}")
                raise

        return wrapper

    return decorador

