"""Default JSON schema for legacy structured-output experiments."""

DEFAULT_GROUP_REPORT_SCHEMA = {
    "name": "GroupReport",
    "schema": {
        "$defs": {
            "ErrorAnalysisStructured": {
                "properties": {
                    "code": {"description": "Error code (E##)", "title": "Code", "type": "string"},
                    "process": {"$ref": "#/$defs/ThoughtProcess", "description": "Trace of reasoning"},
                    "verdict": {
                        "description": "error_present | no_error",
                        "enum": ["error_present", "no_error"],
                        "title": "Verdict",
                        "type": "string",
                    },
                    "instances": {
                        "description": "List of detected instances",
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
                        "description": "invalid | missing",
                        "enum": ["invalid", "missing"],
                        "title": "Err Type",
                        "type": "string",
                    },
                    "snippet": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Optional text snippet",
                        "title": "Snippet",
                    },
                    "line_start": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "First line number",
                        "title": "Line Start",
                    },
                    "line_end": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "Last line number",
                        "title": "Line End",
                    },
                    "suggested_fix": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Short suggested fix",
                        "title": "Suggested Fix",
                    },
                    "rationale": {
                        "description": "Justification for the instance",
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
                    "text": {"description": "Retrieved text fragment", "title": "Text", "type": "string"},
                    "line_start": {"description": "First line in the fragment", "minimum": 1, "title": "Line Start", "type": "integer"},
                    "line_end": {"description": "Last line in the fragment", "minimum": 1, "title": "Line End", "type": "integer"},
                },
                "required": ["text", "line_start", "line_end"],
                "title": "RetrievalChunk",
                "type": "object",
            },
            "ThoughtProcess": {
                "properties": {
                    "retrieval": {
                        "description": "1-5 supporting snippets",
                        "items": {"$ref": "#/$defs/RetrievalChunk"},
                        "title": "Retrieval",
                        "type": "array",
                    },
                    "analysis": {"description": "Reasoning", "title": "Analysis", "type": "string"},
                    "critique": {"description": "Self-critique", "title": "Critique", "type": "string"},
                    "verification": {"description": "Verification notes", "title": "Verification", "type": "string"},
                },
                "required": ["retrieval", "analysis", "critique", "verification"],
                "title": "ThoughtProcess",
                "type": "object",
            },
        },
        "properties": {
            "group_id": {"description": "Classifier group id", "title": "Group Id", "type": "string"},
            "preliminary_notes": {
                "description": "Short notes about the group (≤120 chars)",
                "title": "Preliminary Notes",
                "type": "string",
            },
            "errors": {
                "description": "List of analysed errors",
                "items": {"$ref": "#/$defs/ErrorAnalysisStructured"},
                "title": "Errors",
                "type": "array",
            },
            "overall_critique": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": None,
                "description": "Optional overall critique",
                "title": "Overall Critique",
            },
        },
        "required": ["group_id", "preliminary_notes", "errors"],
        "title": "GroupReportStructured",
        "type": "object",
    },
}
