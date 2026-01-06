from __future__ import annotations
import logging
import sys
import time
from contextvars import ContextVar
from typing import Callable
from collections import deque
from typing import Any
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
import json
import secrets
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import get_current_span


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None) #создаем контекстную переменную для хранения request_id


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", #имя метрики количества HTTP-запросов
    "Total HTTP requests", #описание метрики
    ["method", "path", "status"], #лейблы для агрегации метрик
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", #имя метрики времени выполнения запроса
    "HTTP request duration", #описание метрики
    ["method", "path"], #лейблы для агрегации метрик
)

LOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=500) #буфер для хранения последних логов в памяти (для UI)


class JsonFormatter(logging.Formatter):
    """
    Форматтер для структурированного логирования в JSON.
    Используется для унифицированного представления логов приложения.
    """

    def to_dict(self, record: logging.LogRecord) -> dict:
        """
        Преобразует объект LogRecord в словарь.
        Используется и для stdout-логов, и для буфера /logs.
        """

        #словарь с данными лога
        msg = {
            "ts": int(record.created * 1000), #время события в миллисекундах
            "level": record.levelname, #уровень логирования
            "logger": record.name, #имя логгера
            "msg": record.getMessage(), #текст сообщения
            "module": record.module, #модуль вызова
            "func": record.funcName, #имя функции
            "line": record.lineno, #номер строки
            "request_id": _request_id.get(), #подтягиваеем request_id из контекста
        }

        span = get_current_span()  # получаем текущий span
        ctx = span.get_span_context()  # получаем контекст span

        if ctx.is_valid:
            msg["trace_id"] = format(ctx.trace_id, "032x")  # добавляем trace_id

        if record.exc_info: #проверяем наличие исключения
            msg["exc_info"] = self.formatException(record.exc_info) #добавляем стек исключения в лог

        return msg

    def format(self, record: logging.LogRecord) -> str:
        """
        Преобразует объект LogRecord в JSON-строку.

        :param record: объект лог-записи logging
        :return: строка в формате JSON
        """

        return json.dumps(self.to_dict(record), ensure_ascii=False, separators=(",", ":")) #cловарь сериализуем в JSON-строку


class BufferHandler(logging.Handler):
    """
    Хендлер для записи структурированных логов в память.
    Нужен чтобы UI мог показать последние N логов через endpoint /logs.
    """

    def __init__(self, buf: deque):
        super().__init__()
        self.buf = buf

    def emit(self, record: logging.LogRecord) -> None:
        fmt = self.formatter
        if not isinstance(fmt, JsonFormatter):
            return
        try:
            self.buf.append(fmt.to_dict(record))
        except Exception:
            pass


def setup_logging(level: str) -> None:
    """
    Инициализирует глобальную систему логирования приложения.
    Настраивает уровень логирования и формат вывода логов.
    """

    root = logging.getLogger() #получаем корневой логгер
    root.handlers.clear() #очищаем ранее добавленные хендлеры
    root.setLevel(level.upper()) #устанавливаем уровень логирования

    handler = logging.StreamHandler(sys.stdout) #создаем хендлер вывода логов в stdout
    handler.setFormatter(JsonFormatter()) #к хендлеру привязываем JSON-форматтер
    root.addHandler(handler) #хендлер добавляется к корневому логгеру

    buf_handler = BufferHandler(LOG_BUFFER) #создаем хендлер для буфера логов
    buf_handler.setFormatter(JsonFormatter()) #к нему тоже привязываем JSON-форматтер
    root.addHandler(buf_handler) #добавляем хендлер в корневой логгер

    logging.getLogger("uvicorn.access").setLevel("WARNING") #отключаем access-логи uvicorn


def _normalize_path(path: str) -> str:
    """
    Приводит URL-путь к обобщенному виду для метрик.

    Пример: /movies/123 -> /movies/{id}
    """
 
    parts = [p for p in path.split("/") if p] 
    return "/" + "/".join("{id}" if p.isdigit() else p for p in parts)


def attach_observability(app: FastAPI, config: dict) -> None:
    """
    Подключает сбор логов и метрик к FastAPI-приложению
    с использованием параметров из конфигурационного файла.
    """
    setup_tracing(config)
    setup_logging(config["logging"]["level"]) #инициализируем логирование с уровнем из конфига

    @app.get("/logs")
    def logs(limit: int = 100):
        """
        HTTP-endpoint для отдачи последних логов в JSON.
        Используется фронтом на странице "Наблюдаемость".
        """
        limit = max(1, min(int(limit), 500))
        items = list(LOG_BUFFER)[-limit:]
        return {"items": items}

    if config["metrics"]["enabled"]: #проверка включены ли метрики

        @app.middleware("http")
        async def metrics_middleware(
            request: Request,
            call_next: Callable,
        ):
            """
            Middleware для логирования HTTP-запросов
            и сбора метрик времени выполнения.
            """

            rid = request.headers.get("x-request-id") or _gen_request_id() #берем request_id из заголовка или генерируем новый
            token = _request_id.set(rid) #request_id сохраняем в контекст

            start = time.perf_counter() #фиксируем время начала запроса
            status = 500 #задаем статус по умолчанию

            log = logging.getLogger("app")

            try:
                response: Response = await call_next(request) #управление передаем следующему обработчику
                status = response.status_code #сохраняем HTTP-статус ответа
                response.headers["x-request-id"] = rid #request_id добавляем в заголовок ответа
                log.info("request processed")

                span = get_current_span()
                ctx = span.get_span_context()

                item = {
                    "ts": int(time.time() * 1000),
                    "level": "INFO",
                    "logger": "app",
                    "msg": "request processed",
                    "module": "observability",
                    "func": "metrics_middleware",
                    "line": 135,
                    "request_id": rid,
                }

                if ctx.is_valid:
                    item["trace_id"] = format(ctx.trace_id, "032x")

                LOG_BUFFER.append(item)

                return response


            finally:
                elapsed = time.perf_counter() - start #длительность обработки запроса
                path = _normalize_path(request.url.path) #нормализуем путь запроса

                HTTP_REQUESTS_TOTAL.labels(
                    method=request.method, #указываем HTTP-метод
                    path=path, #путь запроса
                    status=str(status), #статус ответа
                ).inc()
                #увеличиваем счетчик запросов

                HTTP_REQUEST_DURATION.labels(
                    method=request.method, #HTTP-метод
                    path=path, #путь запроса
                ).observe(elapsed) #время выполнения запроса

                _request_id.reset(token) #очищается контекст request_id 

        @app.get("/metrics")
        def metrics():
            """
            HTTP-endpoint для отдачи метрик в формате Prometheus.
            """
            return Response(
                content=generate_latest(), #формируются актуальные метрики Prometheus
                media_type=CONTENT_TYPE_LATEST, #тип контента ответа
            )
        
    FastAPIInstrumentor.instrument_app(app)


def _gen_request_id() -> str:

    """
    Генерирует уникальный идентификатор запроса.
    Используется для корреляции логов.
    """

    return secrets.token_hex(16) #генерируется случайный request_id


def setup_tracing(config: dict) -> None:
    """
    Инициализирует distributed tracing через OpenTelemetry.
    Используется только при включенном трейcинге в конфиге.
    """

    if not config.get("tracing", {}).get("enabled"):
        return

    resource = Resource.create(
        {
            "service.name": config["app"]["name"],
            "service.version": "1.0.0",
            "deployment.environment": config["app"]["env"],
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=config["tracing"]["endpoint"],
        insecure=True,
    )

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    LoggingInstrumentor().instrument(set_logging_format=False)
