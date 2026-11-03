from django.conf import settings
from django.db import models

class Board(models.Model):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.name

class Membership(models.Model):
    class Role(models.TextChoices):
        MANAGER = 'manager', 'Руководитель'
        MEMBER = 'member', 'Исполнитель'
        VIEWER = 'viewer', 'Наблюдатель'

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['board', 'user'], name='one_membership_per_board'), models.CheckConstraint(condition=models.Q(role__in=['manager', 'member', 'viewer']), name='membership_valid_role')]

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = 'todo', 'Нужно сделать'
        DOING = 'doing', 'В работе'
        REVIEW = 'review', 'На проверке'
        DONE = 'done', 'Готово'

    class Priority(models.TextChoices):
        LOW = 'low', 'Низкий'
        NORMAL = 'normal', 'Обычный'
        HIGH = 'high', 'Высокий'

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=5000, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    due_date = models.DateField(null=True, blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tasks')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['todo', 'doing', 'review', 'done']), name='task_valid_status'), models.CheckConstraint(condition=models.Q(priority__in=['low', 'normal', 'high']), name='task_valid_priority'), models.CheckConstraint(condition=models.Q(version__gte=1), name='task_positive_version')]
