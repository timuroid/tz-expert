"""
Скрипт подключается к PostgreSQL и выводит самую новую запись из таблицы `versions`
(сортировка по `updated_at` по убыванию). Результат печатается в JSON и
сохраняется в `out_json/latest_version.json`.

Примечание: параметры подключения заданы явно на основе данных пользователя.
Для продакшена лучше использовать переменные окружения.
"""

import json
import os
import sys
from datetime import datetime

import psycopg2
from psycopg2.extras import DictCursor


# --- Параметры подключения к БД (из запроса пользователя) ---
DB_CONFIG = {
    "host": "94.241.142.172",
    "port": 8002,
    "dbname": "technical_specs",
    "user": "aAKSHDVasvd",
    "password": "dbsaLSAGVDvadaj",
}


def fetch_latest_version():
    """Возвращает самую новую строку из `versions` как словарь."""
    query = """
        SELECT *
        FROM versions
        ORDER BY updated_at DESC
        LIMIT 1
    """

    # Подключаемся к БД с курсором, возвращающим dict-подобные записи
    with psycopg2.connect(cursor_factory=DictCursor, connect_timeout=10, **DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            if row is None:
                return None
            # Преобразуем в обычный словарь; даты переведём в ISO-строки
            result = {}
            for k, v in row.items():
                if isinstance(v, (datetime,)):
                    result[k] = v.isoformat()
                else:
                    result[k] = v
            return result


def main():
    try:
        latest = fetch_latest_version()
    except Exception as e:
        # Короткое сообщение об ошибке на русском
        print(f"Ошибка при выполнении запроса: {e}", file=sys.stderr)
        sys.exit(1)

    if latest is None:
        print("Таблица versions пуста или запись не найдена.")
        return

    # Печать результата в красивом JSON
    pretty = json.dumps(latest, ensure_ascii=False, indent=2)
    print(pretty)

    # Дополнительно сохраним в файл
    out_dir = os.path.join(os.path.dirname(__file__), "out_json")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "latest_version.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pretty + "\n")

    # Сообщение о расположении сохраненного файла
    print(f"\nСохранено в файл: {out_path}")


if __name__ == "__main__":
    main()
