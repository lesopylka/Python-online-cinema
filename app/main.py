from fastapi import FastAPI
import logging
from app.config import load_config
from app.observability import attach_observability

config = load_config("config.yaml") #загружаем конфигурация из yaml

print(config)

log = logging.getLogger("app") #создаётся логгер приложения

app = FastAPI(title=config["app"]["name"]) #создаётся FastAPI-приложение

attach_observability(app, config) #подключаются логи и метрики

@app.get("/ping")
def ping():
    log.info("ping called")
    return {"pong": True}
