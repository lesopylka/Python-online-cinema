## Python: продвинутый уровень
### Кейс: онлайн кинотеатр
Онлайн-кинотеатр с каталогом фильмов, актерами, видеостримингом, override-описаниями и наблюдаемостью.

### Команда:
- [**Ваня**](https://github.com/Chigatu) — в рамках задания разрабатывает архитектуру решения, описывает и обосновывает методы взаимодействия элементов системы между собой.
-  [**Катя**](https://github.com/Ekaterina3002) — организует ETL-пайплайн для переноса описаний фильмов в соответствующее хранилище.
-  [**Мадина**](https://github.com/lesopylka/Python-online-cinema/tree/madina-001) — организует сбор пользовательской активности и потоковое получение файлов из соответствующего хранилища.
- [**Алина**](https://github.com/lesopylka/Python-online-cinema/tree/observability) — организует сбор логов и метрик, а также (в случае выбора микросервисной архитектуры) настраивает распределённый трейсинг.


### Архитектура 

Система состоит из:

- PostgreSQL — фильмы, актёры, связи, override-описания
- ETL — загружает фильмы и актёров из partner_movies.json и CMS
- FastAPI backend — каталог, актёры, overrides, видеостриминг
- Frontend (Vite + JS) — UI каталога и плеер
- MinIO — CMS-хранилище
- Kafka — события активности
- Jaeger + OpenTelemetry — трассировка
- Docker Compose — окружение

### Сбор пользовательской активности

Типы событий

Во время взаимодействия пользователя с видеоплеером формируются следующие события:

- **play** — начало просмотра фильма;
- **progress** — прогресс просмотра (периодическое событие);
- **pause / stop** — остановка просмотра;
- **heartbeat** — периодическое подтверждение активности пользователя;
- **error** — ошибки воспроизведения или сети.

Видео хранятся в объектном хранилище (MinIO)

### Установка зависимостей

```bash
pip install -r requirements.txt --upgrade
cd frontend
npm install
```

### БД:

Инициализация схемы: `db/init.sql`

Таблицы:
- `movies` — финальная витрина фильмов после ETL
- `movie_description_overrides` — ручные override-описания 

### Запуск проекта

**Полезные порты:**
- Backend: http://localhost:8002
- Frontend: http://localhost:5173 
- Frontend ходит в backend по http://localhost:8002
- Jaeger UI: http://localhost:16686
- OTLP gRPC: localhost:4317
- OTLP HTTP: localhost:4318


**Запуск бекенда**
``` bash
uvicorn app.main:app --reload
```

**Запуск фронта**
``` bash
npm run dev
```

### Запуск Docker

```bash
docker compose down
docker compose up -d --build
```
### Загрузка фильмов (ETL)
Если в базе `movies` пусто — ребуется запустить ETL.
``` bash
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
``` bash
docker compose exec postgres psql -U cinema -d cinema -c "select count(*) from movies;"
docker compose exec postgres psql -U cinema -d cinema -c "select movie_id,title,source_used from movies limit 10;"
```

### Интерфейс:
![photo_2026-01-03_17-21-47 (2)](https://github.com/user-attachments/assets/3599dfe7-eb22-40d2-877a-149c8729d56c)
![photo_2026-01-03_17-21-47 (3)](https://github.com/user-attachments/assets/55a4ef8b-7d96-4cfc-88fb-bba4afab2fc5)
![photo_2026-01-03_17-21-47](https://github.com/user-attachments/assets/447b4270-42b3-4967-8bfe-7e3884a49746)
![photo_2026-01-03_19-53-54](https://github.com/user-attachments/assets/facae749-00f3-4611-94f4-caa7b893b10e)
