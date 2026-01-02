from fastapi import FastAPI


# Инициализация FastAPI
app = FastAPI(title="Online Cinema")

# Инициализация Kafka producer
kafka = KafkaProducer(settings.kafka_bootstrap_servers)


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
