from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Online Cinema"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_events: str = "user-events"

    class Config:
        env_file = ".env"


settings = Settings()
