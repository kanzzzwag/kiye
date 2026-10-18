# Лицензии моделей и библиотек

Все компоненты допускают коммерческое использование. Код и веса с AGPL/GPL (в том числе Ultralytics YOLOv5/v8/v11)
не используются. Облачные API не вызываются: веса скачиваются один раз на `docker build`, при работе
включены `HF_HUB_OFFLINE=1` и `TRANSFORMERS_OFFLINE=1`.

## Модели

| Модель | Назначение | Лицензия кода | Лицензия весов | Источник |
|---|---|---|---|---|
| RT-DETR R18-vd (`PekingU/rtdetr_r18vd_coco_o365`, ревизия `386c4385`) | детекция людей и предметов (COCO 80 классов) | Apache-2.0 (реализация в `transformers`) | Apache-2.0 (карточка модели, поле `license: apache-2.0`) | https://huggingface.co/PekingU/rtdetr_r18vd_coco_o365 |
| Grounding DINO tiny (`IDEA-Research/grounding-dino-tiny`, ревизия `a2bb814d`) | open-vocabulary детекция на ключевых кадрах: стакан, пачки купюр, сумка, одежда, открытая дверца | Apache-2.0 (реализация в `transformers`) | Apache-2.0 (карточка модели, поле `license: apache-2.0`) | https://huggingface.co/IDEA-Research/grounding-dino-tiny |

Проверены и не используются (не по лицензии, а по результату или времени; все Apache-2.0):
OWLv2 `google/owlv2-base-patch16-ensemble` и OWL-ViT B/16 — 5–10 с на кадр на CPU;
OWL-ViT B/32 — быстрее (0,9 с), но не находит стакан и пачки;
ViTPose `usyd-community/vitpose-base-simple` — поза не отличает нарушение от нормы на этих ракурсах;
DINOv2-small `facebook/dinov2-small` — обучаемый скорер кадров на его признаках оказался на уровне случайного.
`openai/clip-vit-base-patch32` не рассматривался: в метаданных Hugging Face нет поля лицензии.

Обучающие данные весов: COCO 2017 (аннотации CC BY 4.0), предобучение Objects365. На лицензию весов это не влияет,
но в отчёте для заказчика стоит указать происхождение данных.

Собственные компоненты (трекер, поиск сцены, детекторы состояния стола, сейфа и двери, правила) написаны в проекте,
сторонних весов не используют.

## Python-библиотеки (образ `backend`)

| Пакет | Версия | Лицензия |
|---|---|---|
| torch (CPU wheel) | 2.5.1 | BSD-3-Clause |
| transformers | 4.46.3 | Apache-2.0 |
| huggingface_hub | 0.26.5 | Apache-2.0 |
| safetensors | 0.4.5 | Apache-2.0 |
| opencv-python-headless | 4.10.0.84 | Apache-2.0 (OpenCV 4.x), MIT (обвязка) |
| numpy | 1.26.4 | BSD-3-Clause |
| pillow | 11.0.0 | MIT-CMU (HPND) |
| pyyaml | 6.0.2 | MIT |
| fastapi | 0.115.6 | MIT |
| uvicorn | 0.34.0 | BSD-3-Clause |
| python-multipart | 0.0.20 | Apache-2.0 |
| pydantic-settings | 2.7.1 | MIT |
| sqlalchemy | 2.0.36 | MIT |
| alembic | 1.14.0 | MIT |
| pg8000 (драйвер PostgreSQL) | 1.31.2 | BSD-3-Clause |
| redis (клиент) | 5.2.1 | MIT |
| rq | 2.1.0 | BSD-2-Clause |

## Системные компоненты

| Компонент | Лицензия | Примечание |
|---|---|---|
| ffmpeg / ffprobe (пакет Debian) | LGPL-2.1+ (с GPL-частями в сборке Debian) | вызывается как отдельная программа (`subprocess`) только для проверки контейнера, с кодом не линкуется |
| FFmpeg внутри колеса opencv-python-headless | LGPL-2.1 | динамическая библиотека в составе OpenCV, не модифицируется |
| PostgreSQL 16 | PostgreSQL License | |
| Redis 7.2 (`redis:7.2-alpine`) | BSD-3-Clause | версия закреплена: начиная с 7.4 Redis распространяется под RSALv2/SSPLv1 |

## Проверка

- `pip-audit` в CI проверяет известные уязвимости зависимостей (`.github/workflows/ci.yml`).
- Лицензию новой модели или библиотеки вносить сюда до добавления в `requirements.txt`.
