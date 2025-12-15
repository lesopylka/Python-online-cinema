"""
Основной файл для запуска всех сервисов онлайн-кинотеатра.
Поддерживает запуск отдельных сервисов или всех вместе.
"""

import sys
import os
import argparse
import logging
from multiprocessing import Process
import uvicorn
from dotenv import load_dotenv

# Добавляем src в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные окружения
load_dotenv()

# Настройка базового логирования до импорта других модулей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_api_gateway(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Запуск API Gateway."""
    from src.config.settings import settings
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("api-gateway")
    
    logger.info(f"Starting API Gateway on {host}:{port}")
    
    uvicorn.run(
        "src.api_gateway.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_user_service(host: str = "0.0.0.0", port: int = 8001, reload: bool = False):
    """Запуск User Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("user-service")
    
    logger.info(f"Starting User Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.user_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_catalog_service(host: str = "0.0.0.0", port: int = 8002, reload: bool = False):
    """Запуск Catalog Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("catalog-service")
    
    logger.info(f"Starting Catalog Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.catalog_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_search_service(host: str = "0.0.0.0", port: int = 8003, reload: bool = False):
    """Запуск Search Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("search-service")
    
    logger.info(f"Starting Search Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.search_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_streaming_service(host: str = "0.0.0.0", port: int = 8004, reload: bool = False):
    """Запуск Streaming Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("streaming-service")
    
    logger.info(f"Starting Streaming Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.streaming_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_analytics_service(host: str = "0.0.0.0", port: int = 8005, reload: bool = False):
    """Запуск Analytics Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("analytics-service")
    
    logger.info(f"Starting Analytics Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.analytics_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_notification_service(host: str = "0.0.0.0", port: int = 8006, reload: bool = False):
    """Запуск Notification Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("notification-service")
    
    logger.info(f"Starting Notification Service on {host}:{port}")
    
    uvicorn.run(
        "src.services.notification_service.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
        access_log=True
    )


def run_all_services():
    """Запуск всех сервисов в отдельных процессах."""
    services = [
        ("api-gateway", run_api_gateway, ("0.0.0.0", 8000, False)),
        ("user-service", run_user_service, ("0.0.0.0", 8001, False)),
        ("catalog-service", run_catalog_service, ("0.0.0.0", 8002, False)),
        ("search-service", run_search_service, ("0.0.0.0", 8003, False)),
        ("streaming-service", run_streaming_service, ("0.0.0.0", 8004, False)),
        ("analytics-service", run_analytics_service, ("0.0.0.0", 8005, False)),
        ("notification-service", run_notification_service, ("0.0.0.0", 8006, False)),
    ]
    
    processes = []
    
    for service_name, service_func, args in services:
        logger.info(f"Starting {service_name}...")
        p = Process(target=service_func, args=args, daemon=True)
        p.start()
        processes.append((service_name, p))
        logger.info(f"{service_name} started with PID {p.pid}")
    
    # Ожидание завершения
    try:
        for service_name, p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down services...")
        for service_name, p in processes:
            if p.is_alive():
                p.terminate()
                p.join()
                logger.info(f"{service_name} terminated")
    
    logger.info("All services stopped")


def run_etl_service():
    """Запуск ETL Service."""
    from src.monitoring.logging_config import setup_logging
    
    setup_logging("etl-service")
    
    logger.info("Starting ETL Service...")
    
    # Импортируем и запускаем ETL service
    try:
        from src.etl.pipeline import run_etl_pipeline
        run_etl_pipeline()
    except ImportError as e:
        logger.error(f"Failed to import ETL module: {e}")
        logger.info("ETL module not implemented yet")
    except Exception as e:
        logger.error(f"ETL service failed: {e}")


def parse_arguments():
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Online Cinema - микросервисная система онлайн-кинотеатра"
    )
    
    parser.add_argument(
        "--service",
        type=str,
        choices=[
            "all", "api-gateway", "user-service", "catalog-service",
            "search-service", "streaming-service", "analytics-service",
            "notification-service", "etl-service"
        ],
        default="all",
        help="Сервис для запуска (по умолчанию: все)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Хост для запуска сервиса"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        help="Порт для запуска сервиса"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Включить автоматическую перезагрузку при изменении кода"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Путь к файлу конфигурации (.env)"
    )
    
    return parser.parse_args()


def main():
    """Основная функция запуска."""
    args = parse_arguments()
    
    # Загружаем конфигурацию если указана
    if args.config:
        load_dotenv(args.config)
        logger.info(f"Loaded configuration from {args.config}")
    
    # Порт по умолчанию для каждого сервиса
    default_ports = {
        "api-gateway": 8000,
        "user-service": 8001,
        "catalog-service": 8002,
        "search-service": 8003,
        "streaming-service": 8004,
        "analytics-service": 8005,
        "notification-service": 8006,
    }
    
    # Запуск выбранного сервиса
    if args.service == "all":
        run_all_services()
    
    elif args.service == "api-gateway":
        port = args.port or default_ports["api-gateway"]
        run_api_gateway(args.host, port, args.reload)
    
    elif args.service == "user-service":
        port = args.port or default_ports["user-service"]
        run_user_service(args.host, port, args.reload)
    
    elif args.service == "catalog-service":
        port = args.port or default_ports["catalog-service"]
        run_catalog_service(args.host, port, args.reload)
    
    elif args.service == "search-service":
        port = args.port or default_ports["search-service"]
        run_search_service(args.host, port, args.reload)
    
    elif args.service == "streaming-service":
        port = args.port or default_ports["streaming-service"]
        run_streaming_service(args.host, port, args.reload)
    
    elif args.service == "analytics-service":
        port = args.port or default_ports["analytics-service"]
        run_analytics_service(args.host, port, args.reload)
    
    elif args.service == "notification-service":
        port = args.port or default_ports["notification-service"]
        run_notification_service(args.host, port, args.reload)
    
    elif args.service == "etl-service":
        run_etl_service()
    
    else:
        logger.error(f"Unknown service: {args.service}")
        sys.exit(1)


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║      Online Cinema - Микросервисная система       ║
    ║                                                   ║
    ║  Запуск: python src/main.py --service <название>  ║
    ║  Доступные сервисы:                               ║
    ║    • all (все)                                    ║
    ║    • api-gateway                                  ║
    ║    • user-service                                 ║
    ║    • catalog-service                              ║
    ║    • search-service                               ║
    ║    • streaming-service                            ║
    ║    • analytics-service                            ║
    ║    • notification-service                         ║
    ║    • etl-service                                  ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        sys.exit(1)