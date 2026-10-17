# Оценка на открытых данных

Дата: 2026-10-17 19:24 UTC. Допуск таймкода ±3 с.

| Метрика | Значение |
|---|---|
| Recall | 68% (15/22) |
| Precision | 88% (15/17) |
| Точность вердикта | 79% |
| TP / FP / FN / TN | 15 / 2 / 7 / 18 |
| Средняя ошибка таймкода | 2.7 с |
| Таймкод в допуске | 12/15 |
| Тип верный | 13/15 |
| Макс. время на видео | 169 с |
| Макс. время на минуту видео | 140 с |

Время обработки берётся из кэша признаков и включает нагрузку, которая шла на машине во время его построения; для честного замера end-to-end используйте `--full` на свободной машине (ролик 145 с на 4 ядрах: ~106 с).

| Видео | Длит., с | Разметка | Вердикт | Ошибка t, с | Ожид. тип | Найдено | Тип | Время, с |
|---|---|---|---|---|---|---|---|---|
| X-1 | 26 | 22 | FN |  | CASH_CONCEALMENT | - |  | 34 |
| X-2 | 17 | 10 | FN |  | COUNT_PROCEDURE | - |  | 22 |
| X-3 | 20 | нет | TN |  | - | - |  | 25 |
| X-4 | 73 | 57 | TP | 1.8 | CASH_EXPOSED | CASH_EXPOSED | да | 97 |
| X-5 | 72 | нет | TN |  | - | - |  | 140 |
| X-8 | 38 | нет | TN |  | - | - |  | 68 |
| X-10 | 16 | нет | TN |  | - | - |  | 17 |
| X-11 | 26 | 18 | TP | 0.4 | WORKPLACE_LEFT | WORKPLACE_LEFT | да | 33 |
| X-12 | 42 | нет | TN |  | - | - |  | 56 |
| X-13 | 65 | 47 | TP | 11.0 | CIT_PROCEDURE | CASH_UNATTENDED | нет | 85 |
| X-14 | 143 | нет | TN |  | - | - |  | 108 |
| X-15 | 21 | 15 | FN |  | CASH_UNATTENDED | - |  | 27 |
| X-16 | 23 | нет | TN |  | - | - |  | 31 |
| X-17 | 15 | 7 | TP | 0.2 | CIT_PROCEDURE | CIT_PROCEDURE | да | 17 |
| X-18 | 23 | 20 | TP | 4.3 | UNAUTHORIZED_PERSON | UNAUTHORIZED_PERSON | да | 30 |
| X-19 | 57 | нет | TN |  | - | - |  | 73 |
| X-20 | 12 | 5 | FN |  | SAFE_OPEN | - |  | 13 |
| X-21 | 20 | нет | TN |  | - | - |  | 24 |
| X-22 | 21 | 14 | TP | 0.3 | SAFE_OPEN | CASH_UNATTENDED | нет | 26 |
| X-23 | 18 | нет | TN |  | - | - |  | 23 |
| X-24 | 15 | 8 | TP | 1.2 | CASH_UNATTENDED | CASH_UNATTENDED | да | 16 |
| X-25 | 32 | нет | FP |  | - | CASH_UNATTENDED |  | 41 |
| X-26 | 20 | 9 | TP | 2.1 | CASH_UNATTENDED | CASH_UNATTENDED | да | 27 |
| X-27 | 26 | нет | TN |  | - | - |  | 32 |
| X-28 | 17 | 7 | TP | 2.3 | WORKPLACE_LEFT | WORKPLACE_LEFT | да | 20 |
| X-29 | 17 | нет | FP |  | - | CASH_UNATTENDED |  | 20 |
| X-30 | 19 | 13 | TP | 0.4 | UNAUTHORIZED_PERSON | DOOR_OPEN,UNAUTHORIZED_PERSON | да | 23 |
| X-31 | 24 | нет | TN |  | - | - |  | 28 |
| X-32 | 21 | 5 | TP | 1.1 | DOOR_OPEN | CASH_EXPOSED,DOOR_OPEN | да | 26 |
| X-33 | 14 | 6 | TP | 0.1 | DOOR_OPEN | DOOR_OPEN | да | 16 |
| X-34 | 18 | 13 | TP | 0.4 | COUNT_PROCEDURE | COUNT_PROCEDURE | да | 22 |
| X-35 | 57 | нет | TN |  | - | - |  | 70 |
| X-37 | 16 | нет | TN |  | - | - |  | 20 |
| X-38 | 59 | 33 | TP | 2.4 | CASH_EXPOSED | CASH_EXPOSED | да | 74 |
| X-39 | 79 | нет | TN |  | - | - |  | 102 |
| X-40 | 25 | 17 | FN |  | PERSONAL_ITEMS | - |  | 33 |
| X-43 | 23 | нет | TN |  | - | - |  | 32 |
| X-44 | 20 | 16 | FN |  | CASH_CONCEALMENT | - |  | 26 |
| X-45 | 33 | нет | TN |  | - | - |  | 44 |
| X-46 | 19 | 11 | FN |  | FOOD_DRINK | - |  | 25 |
| X-47 | 73 | 68 | TP | 12.8 | CASH_EXPOSED | CASH_EXPOSED | да | 169 |
| X-48 | 72 | нет | TN |  | - | - |  | 167 |
