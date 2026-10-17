# ForteGuard

Локальный сервис для ForteBank: загружаете видео с камеры над кассой (.mov/.mp4) и получаете возможные нарушения
кассовой дисциплины: тип, таймкод, 1–3 кадра-доказательства, описание того, что видно, и ссылку на норму НБРК.
Всё работает офлайн на CPU: облачные ИИ и внешние API не используются, веса модели лежат в образе.

Документация: [архитектура](docs/architecture.md) · [типы нарушений](docs/violation-types.md) ·
[нормы](docs/legal-sources.md) · [ограничения](docs/limitations.md) · [лицензии](docs/LICENSES.md) ·
[метрики](docs/eval-latest.md) · [устойчивость к ракурсу](docs/eval-augment.md)

## Качество на открытых данных (42 видео)

| Recall | Precision | Точность вердикта | Ошибка таймкода | Тип верный | Время ролика 145 с (4 ядра) |
|---|---|---|---|---|---|
| 68% (15/22) | 88% (15/17) | 79% | 2,7 с в среднем, 12/15 в пределах ±3 с | 13/15 | ~106 с |

Подробно по каждому видео: [docs/eval-latest.md](docs/eval-latest.md). Что не находится и почему:
[docs/limitations.md](docs/limitations.md).

## Установка и запуск (Docker, основной способ)

Нужен Docker с Compose v2; GPU не нужен. Сборка скачивает CPU-версию torch (~200 МБ) и веса RT-DETR (~80 МБ),
после сборки интернет не нужен.

```bash
cp .env.example .env        # задайте API_KEY (не короче 16 символов) и POSTGRES_PASSWORD
docker compose up -d --build
```

- Сайт: http://localhost:8000 (работает и с телефона в той же сети: http://<IP-ноутбука>:8000)
- Документация API: http://localhost:8000/docs

Если PyPI отвечает медленно, в `.env` можно указать зеркало только для сборки: `PIP_INDEX_URL=https://...`.

Контейнеры: `api` (FastAPI и сайт, миграции Alembic и сид при старте), `worker` (анализ видео, один ролик
за раз, лимиты CPU и памяти), `db` (PostgreSQL 16), `redis` (очередь и rate limit).

## API-ключ

Ключ задаётся только в `.env` (`API_KEY`), сервис не запустится с пустым или примерным ключом.
Все запросы к `/api/*` передают заголовок `X-API-Key`. На сайте ключ вводится один раз и хранится в браузере.

## API (как у жюри)

```
POST /api/v1/analyze        multipart: file=<video.mov>   (+ необязательно desk_id, recorded_at для журнала)
     -> {"job_id": "..."}
GET  /api/v1/jobs/{job_id}  -> {"job_id", "status": "processing|done|failed", "verdict": "violation|no_violation",
                                "violations": [{"type", "timecode_sec", "description", "evidence_frames":
                                                [{"timestamp_sec", "image_base64"}]}]}
```

Формат ответа не меняется (`backend/app/schemas.py`). Отдельного поля для нормы в схеме нет, поэтому норма стоит
в конце `description`: «Норма: <документ>, <пункт>.». Если пункт требует проверки человеком, добавлено
«(требует проверки)».

Ограничения на входе: .mov/.mp4, контейнер проверяется ffprobe, до 500 МБ и 10 минут видео,
не больше 20 запросов на анализ в минуту на пару «ключ + IP» (`RATE_LIMIT_PER_MIN`).

Внутренние эндпоинты сайта (`/api/internal/*`): прогресс задачи, журнал с фильтрами по дате, типу и статусу,
экспорт CSV, смена статуса проверки. Жюри они не нужны.

## Проверка как у жюри

```bash
pip install httpx
python scripts/jury_check.py http://localhost:8000 <API_KEY> путь/к/видео.mov
```

## Оценка качества

Данные кейса кладутся в `data/open/` (`videos/*.mov`, `open_labels.xlsx`), в git они не попадают.

```bash
docker compose run --rm -v "$PWD:/work" -w /work worker python ml/eval.py            # таблица и docs/eval-latest.md
docker compose run --rm -v "$PWD:/work" -w /work worker python ml/eval.py --augment  # docs/eval-augment.md
docker compose run --rm -v "$PWD:/work" -w /work worker python ml/inspect.py         # контактные листы кадров
```

## Журнал и кассиры

При первом старте загружаются типы нарушений и нормы из `backend/app/seed/legal_rules.json`, а также демо-кассы,
вымышленные сотрудники и смены на ±60 дней (`SEED_DEMO=false`, чтобы отключить). Если при загрузке указать
номер кассы и время начала записи, нарушение получает кассира по смене автоматически.
Ручной запуск сида: `docker compose exec api python -m app.seed`.

## Запуск без Docker (запасной вариант)

Нужен Python 3.12 и ffmpeg в PATH.

```bash
cd backend
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
MODELS_DIR=./models python app/ml/download_models.py
set API_KEY=...длинный-ключ...      # Linux/macOS: export API_KEY=...
set MODELS_DIR=./models
python -m uvicorn app.main:app --port 8000
```

Без `DATABASE_URL` используется SQLite (`backend/data/forte.db`), без Redis задачи выполняются внутри процесса
(`QUEUE_MODE=thread`).

## Тесты

```bash
cd backend && API_KEY=test-key-0123456789abcdef python -m pytest -q tests
```

CI (`.github/workflows/ci.yml`): pytest (правила на синтетических событиях, контракт схемы ответа),
`pip-audit`, сборка стека и `jury_check.py` на трёх синтетических клипах.

## Где что лежит

- `backend/app/ml/` — пайплайн: `video.py` (декодирование), `detector.py` (RT-DETR), `tracker.py`,
  `scene.py` (автопоиск стола, двери, сейфа), `rules.py` + `rules.yaml` (правила и пороги), `legal.py` (нормы).
- `backend/app/analyzer.py` — точка входа анализа для воркера.
- `backend/app/tasks.py` — задача воркера: анализ, кадры, запись в БД, кассир по смене.
- `backend/migrations/` — миграции Alembic.
- `ml/` — `inspect.py`, `eval.py`, `extract.py` (кэш признаков для подбора порогов).
- `frontend/` — сайт.
