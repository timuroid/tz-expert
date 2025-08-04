#!/usr/bin/env python3
"""
md2json.py

Считывает Markdown-файл и выводит его содержимое как JSON-строку.
Использование:
    python md2json.py path/to/file.md
Результат можно прямо вставить в JSON:
{
  "markdown": <вывод скрипта>,
  "groups": ["G02","G03"],
  "model": "openrouter/openai/gpt-4o-mini"
}
"""
import sys
import json
from pathlib import Path

def md_to_json_str(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # json.dumps захочет выводить ASCII-экранированные символы, но ensure_ascii=False
    # сохранит русский текст корректно
    return json.dumps(text, ensure_ascii=False)

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path/to/file.md>", file=sys.stderr)
        sys.exit(1)

    md_path = Path(sys.argv[1])
    if not md_path.is_file():
        print(f"Error: File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    json_str = md_to_json_str(md_path)
    print(json_str)

if __name__ == "__main__":
    main()
