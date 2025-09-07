# core/admin.py
"""
Админка для:
- ErrorGroupGroup (Группа групп)
- ErrorGroup (Группа ошибок)
- Error (Ошибка)

Особенности:
- Вложенные инлайны через django-nested-admin:
  На странице Группы групп видны и группы ошибок, и их ошибки.
- Кнопка "Склонировать эту группу групп" без правок шаблонов:
  делает полную копию с новыми PK, схемы БД не трогаем (managed=False в моделях).
"""

from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
import nested_admin

from .models import ErrorGroupGroup, ErrorGroup, Error


# ──────────────────────────────────────────────
# Inline для ошибок (2-й уровень)
class ErrorInline(nested_admin.NestedTabularInline):
    model = Error
    extra = 0
    fields = ("name", "code", "detector", "description")  # id не редактируем
    show_change_link = True


# ──────────────────────────────────────────────
# Inline для групп ошибок (1-й уровень)
class ErrorGroupInline(nested_admin.NestedTabularInline):
    model = ErrorGroup
    extra = 0
    fields = ("name", "code", "is_deleted", "group_description")  # id не редактируем
    show_change_link = True
    inlines = [ErrorInline]
    raw_id_fields = ("gg",)  # ускоряет селектор при больших объемах


# ──────────────────────────────────────────────
# Вспомогательная функция: клон одной "Группы групп" целиком
def _clone_single_group_group(src_gg: ErrorGroupGroup) -> ErrorGroupGroup:
    """
    Копирует одну 'Группу групп' вместе с ее ErrorGroup и Error.
    PK НЕ передаем — БД выдаст новые ID (auto-increment/identity).
    """
    with transaction.atomic():
        # 1) создаем новую ГГ
        new_gg = ErrorGroupGroup.objects.create(name=f"{src_gg.name} (копия)")

        # 2) копируем группы ошибок и запоминаем соответствие
        old_to_new_group = {}
        for g in ErrorGroup.objects.filter(gg=src_gg).iterator():
            g_new = ErrorGroup.objects.create(
                name=g.name,
                group_description=g.group_description,
                is_deleted=g.is_deleted,
                gg=new_gg,
                code=g.code,
            )
            old_to_new_group[g.id] = g_new

        # 3) копируем ошибки, используя карту соответствия групп
        if old_to_new_group:
            old_ids = list(old_to_new_group.keys())
            for e in Error.objects.filter(group_id__in=old_ids).iterator():
                Error.objects.create(
                    name=e.name,
                    code=e.code,
                    description=e.description,
                    detector=e.detector,
                    group=old_to_new_group[e.group_id],
                )

    return new_gg


# ──────────────────────────────────────────────
# Админ для Группы групп (видим всё дерево + кнопка "Склонировать")
@admin.register(ErrorGroupGroup)
class ErrorGroupGroupAdmin(nested_admin.NestedModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    inlines = [ErrorGroupInline]
    exclude = ("id",)  # id не редактируем

    # Кнопка без шаблонов: readonly-поле с HTML-ссылкой
    def clone_button(self, obj):
        if not obj or not obj.pk:
            return "Кнопка появится после сохранения."
        url = reverse("admin:core_errorgroupgroup_clone", args=[obj.pk])
        return format_html('<a class="button" href="{}">Склонировать эту группу групп</a>', url)

    clone_button.short_description = "Действия"
    readonly_fields = ("clone_button",)
    fields = ("name", "clone_button")

    # Кастомный URL под кнопку
    def get_urls(self):
        return [
            path(
                "<int:object_id>/clone/",
                self.admin_site.admin_view(self.clone_view),
                name="core_errorgroupgroup_clone",
            ),
        ] + super().get_urls()

    # Обработчик клонирования
    def clone_view(self, request, object_id: int):
        obj = self.get_object(request, object_id)
        if not obj:
            self.message_user(request, "Объект не найден.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:core_errorgroupgroup_changelist"))

        if not self.has_add_permission(request):
            self.message_user(request, "Недостаточно прав для клонирования.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:core_errorgroupgroup_change", args=[object_id]))

        try:
            new_gg = _clone_single_group_group(obj)  # создаем копию с НОВЫМИ PK
        except Exception as exc:
            self.message_user(request, f"Ошибка при клонировании: {exc}", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:core_errorgroupgroup_change", args=[object_id]))

        self.message_user(
            request,
            f"Создана копия: «{new_gg.name}» (ID {new_gg.id}).",
            level=messages.SUCCESS,
        )
        # Переходим сразу на новую копию
        return HttpResponseRedirect(reverse("admin:core_errorgroupgroup_change", args=[new_gg.id]))

    # Массовое действие в списке (опционально)
    @admin.action(description="Склонировать со всем содержимым")
    def clone_with_contents(self, request, queryset):
        created, errors = [], 0
        for gg in queryset:
            try:
                created.append(_clone_single_group_group(gg))
            except Exception:
                errors += 1
        if created:
            names = ", ".join(f"{o.name} (ID {o.id})" for o in created[:5])
            more = "" if len(created) <= 5 else f" и ещё {len(created) - 5}"
            self.message_user(request, f"Созданы копии: {names}{more}.", level=messages.SUCCESS)
        if errors:
            self.message_user(request, f"Не удалось склонировать: {errors} шт.", level=messages.WARNING)

    actions = ["clone_with_contents"]


# ──────────────────────────────────────────────
# Отдельные админы для удобства точечного редактирования
@admin.register(ErrorGroup)
class ErrorGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "gg", "is_deleted")
    list_filter = ("is_deleted", "gg")
    search_fields = ("name", "code", "group_description")
    raw_id_fields = ("gg",)
    inlines = [ErrorInline]
    exclude = ("id",)  # id не редактируем


@admin.register(Error)
class ErrorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "group", "detector")
    list_filter = ("group",)
    search_fields = ("name", "code", "description", "detector")
    raw_id_fields = ("group",)
    exclude = ("id",)  # id не редактируем
