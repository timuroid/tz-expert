# === Документ для аудита (Шаг 1) ===

<DOCUMENT>
{DOCUMENT}
</DOCUMENT>

## === Группа ошибок ===

Группа: {GROUP_ID} - <{GROUP_TITLE}>
Описание группы: {GROUP_DESC}

Ошибки этой группы:
{ERRORS_BLOCK}  <!-- перечисление кодов и кратких описаний -->

## === Формат ответа ===

Верните **один** JSON по схеме **GroupResult** (alias Step1GroupResult):
- перечислите все error_id из группы (даже если нарушений нет);
- для каждого шага укажите goal и observed;
- заполните critique, verdict, instances согласно инструкциям System-подсказки.

Никакого лишнего текста вне JSON.
