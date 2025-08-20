"""
services/default_schema.py
Дефолтная JSON Schema для Structured Output (GroupReportStructured).
Используется, если клиент не прислал schema в запросе.
"""

DEFAULT_GROUP_REPORT_SCHEMA = {
    "name": "GroupReport",
    "schema": {
        "$defs": {
            "ErrorAnalysisStructured": {
                "properties": {
                    "code": {
                        "description": "Код ошибки (E-код)",
                        "title": "Code",
                        "type": "string",
                    },
                    "process": {
                        "$ref": "#/$defs/ThoughtProcess",
                        "description": "Trace рассуждений",
                    },
                    "verdict": {
                        "description": "'error_present' или 'no_error'",
                        "enum": ["error_present", "no_error"],
                        "title": "Verdict",
                        "type": "string",
                    },
                    "instances": {
                        "description": "Список найденных/отсутствующих экземпляров",
                        "items": {"$ref": "#/$defs/ErrorInstance"},
                        "title": "Instances",
                        "type": "array",
                    },
                },
                "required": ["code", "process", "verdict", "instances"],
                "title": "ErrorAnalysisStructured",
                "type": "object",
            },
            "ErrorInstance": {
                "properties": {
                    "err_type": {
                        "description": "'invalid' или 'missing'",
                        "enum": ["invalid", "missing"],
                        "title": "Err Type",
                        "type": "string",
                    },
                    "snippet": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Короткая цитата из текста  (≤1 предложение, обычно 3-7 слов)",
                        "title": "Snippet",
                    },
                    "line_start": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "номер строки начала цитаты",
                        "title": "Line Start",
                    },
                    "line_end": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "номер строки окончания цитаты",
                        "title": "Line End",
                    },
                    "suggested_fix": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Рекомендация  ≤60 слов",
                        "title": "Suggested Fix",
                    },
                    "rationale": {
                        "description": "Обоснование решения",
                        "title": "Rationale",
                        "type": "string",
                    },
                },
                "required": ["err_type", "rationale"],
                "title": "ErrorInstance",
                "type": "object",
            },
            "RetrievalChunk": {
                "properties": {
                    "text": {
                        "description": "Фрагмент документа (≤120 слов)",
                        "title": "Text",
                        "type": "string",
                    },
                    "line_start": {
                        "description": "Номер начала фрагмента",
                        "minimum": 1,
                        "title": "Line Start",
                        "type": "integer",
                    },
                    "line_end": {
                        "description": "Номер конца фрагмента",
                        "minimum": 1,
                        "title": "Line End",
                        "type": "integer",
                    },
                },
                "required": ["text", "line_start", "line_end"],
                "title": "RetrievalChunk",
                "type": "object",
            },
            "ThoughtProcess": {
                "properties": {
                    "retrieval": {
                        "description": "1–5 ключевых фрагментов",
                        "items": {"$ref": "#/$defs/RetrievalChunk"},
                        "title": "Retrieval",
                        "type": "array",
                    },
                    "analysis": {
                        "description": "Почему это ошибка?",
                        "title": "Analysis",
                        "type": "string",
                    },
                    "critique": {
                        "description": "Самокритика рассуждений",
                        "title": "Critique",
                        "type": "string",
                    },
                    "verification": {
                        "description": "окончательная проверка и вывод",
                        "title": "Verification",
                        "type": "string",
                    },
                },
                "required": ["retrieval", "analysis", "critique", "verification"],
                "title": "ThoughtProcess",
                "type": "object",
            },
        },
        "properties": {
            "group_id": {
                "description": "ID группы (например, G03)",
                "title": "Group Id",
                "type": "string",
            },
            "preliminary_notes": {
                "description": "Краткий обзор документа в контексте группы (≤120 слов)",
                "title": "Preliminary Notes",
                "type": "string",
            },
            "errors": {
                "description": "Анализ по каждой ошибке группы",
                "items": {"$ref": "#/$defs/ErrorAnalysisStructured"},
                "title": "Errors",
                "type": "array",
            },
            "overall_critique": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "description": "Общее заключение / рекомендации",
                "title": "Overall Critique",
            },
        },
        "required": ["group_id", "preliminary_notes", "errors"],
        "title": "GroupReportStructured",
        "type": "object",
    },
}
