# Оценка на открытых данных

Дата: 2026-10-17 22:46 UTC. Допуск таймкода ±3 с.

| Метрика | Значение |
|---|---|
| Recall | 73% (16/22) |
| Precision | 89% (16/18) |
| Точность вердикта | 81% |
| TP / FP / FN / TN | 16 / 2 / 6 / 18 |
| Средняя ошибка таймкода | 2.6 с |
| Таймкод в допуске | 13/16 |
| Тип верный | 14/16 |
| Макс. время на видео | 165 с |
| Макс. время на минуту видео | 137 с |

Время обработки берётся из кэша признаков и включает нагрузку, которая шла на машине во время его построения; для честного замера end-to-end используйте `--full` на свободной машине (ролик 145 с на 4 ядрах: ~106 с).

| Видео | Длит., с | Разметка | Вердикт | Ошибка t, с | Ожид. тип | Найдено | Тип | Время, с |
|---|---|---|---|---|---|---|---|---|
| X-1 | 26 | 22 | FN |  | CASH_CONCEALMENT | - |  | 33 |
| X-2 | 17 | 10 | FN |  | COUNT_PROCEDURE | - |  | 21 |
| X-3 | 20 | нет | TN |  | - | - |  | 24 |
| X-4 | 73 | 57 | TP | 1.8 | CASH_EXPOSED | CASH_EXPOSED | да | 94 |
| X-5 | 72 | нет | TN |  | - | - |  | 137 |
| X-8 | 38 | нет | TN |  | - | - |  | 67 |
| X-10 | 16 | нет | TN |  | - | - |  | 16 |
| X-11 | 26 | 18 | TP | 0.4 | WORKPLACE_LEFT | WORKPLACE_LEFT | да | 33 |
| X-12 | 42 | нет | TN |  | - | - |  | 55 |
| X-13 | 65 | 47 | TP | 11.0 | CIT_PROCEDURE | CASH_UNATTENDED | нет | 82 |
| X-14 | 143 | нет | TN |  | - | - |  | 104 |
| X-15 | 21 | 15 | FN |  | CASH_UNATTENDED | - |  | 26 |
| X-16 | 23 | нет | TN |  | - | - |  | 29 |
| X-17 | 15 | 7 | TP | 0.2 | CIT_PROCEDURE | CIT_PROCEDURE | да | 16 |
| X-18 | 23 | 20 | TP | 4.3 | UNAUTHORIZED_PERSON | UNAUTHORIZED_PERSON | да | 28 |
| X-19 | 57 | нет | TN |  | - | - |  | 71 |
| X-20 | 12 | 5 | FN |  | SAFE_OPEN | - |  | 12 |
| X-21 | 20 | нет | TN |  | - | - |  | 23 |
| X-22 | 21 | 14 | TP | 0.3 | SAFE_OPEN | CASH_UNATTENDED | нет | 26 |
| X-23 | 18 | нет | TN |  | - | - |  | 22 |
| X-24 | 15 | 8 | TP | 1.2 | CASH_UNATTENDED | CASH_UNATTENDED | да | 16 |
| X-25 | 32 | нет | FP |  | - | CASH_UNATTENDED |  | 40 |
| X-26 | 20 | 9 | TP | 2.1 | CASH_UNATTENDED | CASH_UNATTENDED | да | 26 |
| X-27 | 26 | нет | TN |  | - | - |  | 31 |
| X-28 | 17 | 7 | TP | 2.3 | WORKPLACE_LEFT | WORKPLACE_LEFT | да | 19 |
| X-29 | 17 | нет | FP |  | - | CASH_UNATTENDED |  | 20 |
| X-30 | 19 | 13 | TP | 0.4 | UNAUTHORIZED_PERSON | DOOR_OPEN,UNAUTHORIZED_PERSON | да | 22 |
| X-31 | 24 | нет | TN |  | - | - |  | 27 |
| X-32 | 21 | 5 | TP | 0.8 | DOOR_OPEN | DOOR_OPEN | да | 25 |
| X-33 | 14 | 6 | TP | 0.1 | DOOR_OPEN | DOOR_OPEN | да | 15 |
| X-34 | 18 | 13 | TP | 0.4 | COUNT_PROCEDURE | COUNT_PROCEDURE | да | 21 |
| X-35 | 57 | нет | TN |  | - | - |  | 67 |
| X-37 | 16 | нет | TN |  | - | - |  | 19 |
| X-38 | 59 | 33 | TP | 2.4 | CASH_EXPOSED | CASH_EXPOSED | да | 71 |
| X-39 | 79 | нет | TN |  | - | - |  | 98 |
| X-40 | 25 | 17 | FN |  | PERSONAL_ITEMS | - |  | 32 |
| X-43 | 23 | нет | TN |  | - | - |  | 31 |
| X-44 | 20 | 16 | FN |  | CASH_CONCEALMENT | - |  | 26 |
| X-45 | 33 | нет | TN |  | - | - |  | 43 |
| X-46 | 19 | 11 | TP | 0.5 | FOOD_DRINK | FOOD_DRINK | да | 25 |
| X-47 | 73 | 68 | TP | 12.8 | CASH_EXPOSED | CASH_EXPOSED | да | 165 |
| X-48 | 72 | нет | TN |  | - | - |  | 163 |
