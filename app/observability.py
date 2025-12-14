from __future__ import annotations
import logging
import sys
import time
from contextvars import ContextVar
from typing import Callable
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
import json
import secrets

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


class JsonFormatter(logging.Formatter):
    """
    Форматтер для структурированного логирования в JSON.
    Используется для унифицированного представления логов приложения.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Преобразует объект LogRecord в JSON-строку.

        :param record: объект лог-записи logging
        :return: строка в формате JSON
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

        if record.exc_info: #проверяем наличие исключения
            msg["exc_info"] = self.formatException(record.exc_info) #добавляем стек исключения в лог

        return json.dumps(msg, ensure_ascii=False, separators=(",", ":")) #cловарь сериализуем в JSON-строку


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

    setup_logging(config["logging"]["level"]) #инициализируем логирование с уровнем из конфига

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

            try:
                response: Response = await call_next(request) #управление передаем следующему обработчику
                status = response.status_code #сохраняем HTTP-статус ответа
                response.headers["x-request-id"] = rid #request_id добавляем в заголовок ответа
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


def _gen_request_id() -> str:

    """
    Генерирует уникальный идентификатор запроса.
    Используется для корреляции логов.
    """

    return secrets.token_hex(16) #генерируется случайный request_id