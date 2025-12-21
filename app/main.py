from fastapi import FastAPI
import logging
from app.config import load_config
from app.observability import attach_observability
from fastapi.middleware.cors import CORSMiddleware


config = load_config("config.yaml") #загружаем конфигурация из yaml

print(config)

log = logging.getLogger("app") #создаётся логгер приложения

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
