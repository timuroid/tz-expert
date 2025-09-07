from django.db import models

class ErrorGroupGroup(models.Model):
    id = models.AutoField(primary_key=True)  # <-- автоинкремент
    name = models.TextField()

    class Meta:
        db_table = "error_group_groups"
        managed = False
        verbose_name = "Группа групп"
        verbose_name_plural = "Группы групп"

    def __str__(self):
        return self.name or f"GG #{self.id}"


class ErrorGroup(models.Model):
    id = models.AutoField(primary_key=True)  # <-- автоинкремент
    name = models.TextField()
    group_description = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    gg = models.ForeignKey(
        ErrorGroupGroup,
        to_field="id",
        db_column="gg_id",
        on_delete=models.DO_NOTHING,
        related_name="error_groups",
        db_constraint=False,
    )
    code = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "error_groups"
        managed = False
        verbose_name = "Группа ошибок"
        verbose_name_plural = "Группы ошибок"

    def __str__(self):
        return self.name or f"Group #{self.id}"


class Error(models.Model):
    id = models.AutoField(primary_key=True)  # <-- автоинкремент
    code = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    detector = models.TextField(blank=True, null=True)
    group = models.ForeignKey(
        ErrorGroup,
        to_field="id",
        db_column="group_id",
        on_delete=models.DO_NOTHING,
        related_name="errors",
        db_constraint=False,
    )
    name = models.TextField()

    class Meta:
        db_table = "errors"
        managed = False
        verbose_name = "Ошибка"
        verbose_name_plural = "Ошибки"

    def __str__(self):
        return self.name or f"Error #{self.id}"
