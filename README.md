# ForteGuard

Локальный сервис: загружаешь видео с камеры кассы и получаешь возможные нарушения кассовой дисциплины с таймкодом, кадрами и нормой. Облачные ИИ-сервисы не используются.

**Статус:** каркас. API, очередь, база, сайт и журнал работают, но анализатор пока заглушка: всегда возвращает тестовое нарушение около 10-й секунды.

## Запуск с Docker (основной способ)

```bash
cp .env.example .env        # поменять API_KEY и POSTGRES_PASSWORD
docker compose up -d --build
```

Сайт открывается на http://localhost:8000, документация API на http://localhost:8000/docs.

Контейнеры: `api` (FastAPI и сайт), `worker` (анализ видео из очереди), `db` (PostgreSQL), `redis` (очередь).

## Запуск без Docker (запасной вариант)

Нужен Python 3.11+ и ffmpeg в PATH.

```bash
cd backend
pip install -r requirements.txt
set API_KEY=testkey          # в Linux/macOS: export API_KEY=testkey
python -m uvicorn app.main:app --port 8000
```

Вместо PostgreSQL используется файл SQLite (`backend/data/forte.db`), очередь работает внутри программы. Код тот же, переключение через `DATABASE_URL` и `QUEUE_MODE`.

## Проверка как у жюри

```bash
pip install httpx
python scripts/jury_check.py http://localhost:8000 <API_KEY> путь/к/видео.mov
```

Скрипт проверяет, что запрос без ключа отклоняется, формат ответа строго как в кейсе и обработка укладывается в 5 минут.

## API

- `POST /api/v1/analyze`: multipart-поле `file`, заголовок `X-API-Key`, возвращает `{"job_id": ...}`. Необязательные поля `desk_id` и `recorded_at` нужны для журнала, на ответ жюри они не влияют.
- `GET /api/v1/jobs/{job_id}`: ответ строго по схеме кейса (`app/schemas.py`).
- `/api/internal/*`: журнал нарушений для нашего сайта, жюри это не использует.

## Где что лежит

- `backend/app/analyzer.py`: анализ видео. **Сюда подключается модель.**
- `backend/app/tasks.py`: задача воркера: анализ, кадры, запись в БД, поиск кассира по смене.
- `backend/app/models.py`: таблицы БД (кассы, сотрудники, смены, нормы, нарушения, аудит).
- `frontend/`: сайт (загрузка, результат с плеером, журнал).
