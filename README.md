## Python: продвинутый уровень  
### Кейс: онлайн кинотеатр

Онлайн-кинотеатр с каталогом фильмов и актёров, видеостримингом (из MinIO), override-описаниями и наблюдаемостью.


## Команда

- [**Ваня**](https://github.com/Chigatu) — архитектура и взаимодействие компонентов.
- [**Катя**](https://github.com/Ekaterina3002) — ETL-пайплайн загрузки данных о фильмах.
- [**Мадина**](https://github.com/lesopylka/Python-online-cinema/tree/madina-001) — сбор пользовательской активности и потоковая выдача файлов.
- [**Алина**](https://github.com/lesopylka/Python-online-cinema/tree/observability) — логи/метрики и распределённый трейсинг.


## Архитектура

Компоненты проекта:

- **PostgreSQL** — фильмы, актёры, связи, override-описания  
- **ETL** — загружает данные из `partner_movies.json` + (опционально) из CMS (`/overrides`)  
- **FastAPI backend** — каталог, актёры, overrides, стриминг видео  
- **Frontend (Vite + JS)** — UI каталога и видеоплеер  
- **MinIO** — объектное хранилище (видео лежат там)  
- **Kafka** — события пользовательской активности  
- **Jaeger + OpenTelemetry** — трассировка  
- **Docker Compose** — поднимает всё окружение  

## Видео

Видео хранятся в **MinIO** в бакете `cinema`. Имена файлов совпадают с `movie_id`. 
Backend отдаёт видео через `GET /stream/{movie_id}.mp4`.

## Пользовательская активность

Во время работы с плеером фиксируются события:

- **play** — старт просмотра  
- **progress** — прогресс (периодически)  
- **pause / stop** — остановка  
- **heartbeat** — подтверждение активности  
- **error** — ошибки воспроизведения/сети  

## Запуск

### Полезные порты

- Backend: http://localhost:8002  
- Frontend: http://localhost:5173  
- Jaeger UI: http://localhost:16686  
- MinIO Console: http://localhost:9001  
- OTLP gRPC: localhost:4317  
- OTLP HTTP: localhost:4318  

### Установка зависимостей

``` bash
pip install -r requirements.txt --upgrade  
cd frontend  
npm install 
```

### Запуск через Docker

```bash
docker compose down  
docker compose up -d --build  
```

### Запуск локально

Backend
```bash
uvicorn app.main:app --reload  
```

Frontend
```bash
npm run dev  
```

## ETL: загрузка фильмов

Если таблица movies пустая запускаем ETL

```bash
docker run --rm ^
  --network python-online-cinema_default ^
  -v "%cd%\etl\etl.py:/app/etl.py" ^
  -v "%cd%\etl\partner_movies.json:/app/partner_movies.json" ^
  -w /app ^
  -e DATABASE_URL=postgresql://cinema:cinema@postgres:5432/cinema ^
  -e CMS_URL=http://backend:8000 ^
  python:3.11-slim bash -lc "pip install --no-cache-dir psycopg[binary]==3.2.1 requests && python etl.py"
```

Проверка:
```bash
docker compose exec postgres psql -U cinema -d cinema -c "select count(*) from movies;"  
docker compose exec postgres psql -U cinema -d cinema -c "select movie_id,title,source_used from movies limit 10;"  
```

## Интерфейс: