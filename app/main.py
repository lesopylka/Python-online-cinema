from fastapi import FastAPI
import logging
from app.config import load_config
from app.observability import attach_observability
from fastapi.middleware.cors import CORSMiddleware


# Инициализация FastAPI
app = FastAPI(title="Online Cinema")
config = load_config("config.yaml") #загружаем конфигурация из yaml

# Инициализация Kafka producer
kafka = KafkaProducer(settings.kafka_bootstrap_servers)
print(config)

log = logging.getLogger("app") #создаётся логгер приложения

@app.on_event("startup")
async def startup_event():
    """
    При старте приложения пытаемся подключиться к Kafka.
    Если Kafka недоступна — приложение всё равно стартует.
    """
    try:
        await kafka.start()
        print("Kafka producer started successfully")
    except Exception as e:
        print(f"Kafka is not available, continuing without it: {e}")
app = FastAPI(title=config["app"]["name"]) #создаётся FastAPI-приложение

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

attach_observability(app, config) #подключаются логи и метрики

@app.get("/ping")
def ping():
    log.info("ping called")
    return {"pong": True}
@app.on_event("shutdown")
async def shutdown_event():
    """
    Корректно останавливаем Kafka producer при завершении приложения.
    """
    try:
        await kafka.stop()
        print("Kafka producer stopped")
    except Exception:
        pass
