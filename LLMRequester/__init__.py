"""
LLM Requester — изолированный исполнитель LLM-запросов.
Не зависит от PromptBuilder и БД. Принимает messages+schema+model и возвращает
результат, usage и стоимость.
"""