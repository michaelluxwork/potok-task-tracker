import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from boards.models import Board, Membership, Task

class Command(BaseCommand):
    help = 'Create local invented project and three demo accounts. Never runs on production startup.'

    def handle(self, *args, **options):
        if settings.PUBLIC_MODE:
            raise CommandError('Demo seed is allowed only in local mode.')
        access_file = settings.STATE_DIR / 'demo-access.txt'
        if access_file.exists():
            self.stdout.write('Demo already initialized; credentials remain in .state/demo-access.txt')
            return
        accounts = []
        with transaction.atomic():
            if get_user_model().objects.filter(username__in=['lead', 'maker', 'reader']).exists():
                raise CommandError('Demo usernames already exist. Existing accounts will not be modified.')
            for username, role in [('lead', 'manager'), ('maker', 'member'), ('reader', 'viewer')]:
                password = secrets.token_urlsafe(18)
                user = get_user_model().objects.create_user(username=username, password=password)
                accounts.append((user, role, password))
            board = Board.objects.create(name='Запуск сайта', description='От первого наброска до готового проекта. Всё, что важно команде, — на одной доске.')
            for user, role, _ in accounts:
                Membership.objects.create(board=board, user=user, role=role)
            lead, maker = accounts[0][0], accounts[1][0]
            samples = [
                ('Собрать структуру страниц', 'Определить разделы сайта и путь от первого экрана к заявке.', 'todo', 'high', lead, 1),
                ('Подготовить тексты для главной', 'Написать заголовок, описание продукта и текст кнопок.', 'todo', 'normal', maker, 2),
                ('Проверить мобильную навигацию', 'Проверить меню на небольшом экране и управление с клавиатуры.', 'todo', 'normal', None, 3),
                ('Собрать первый экран', 'Сверстать утверждённую композицию и проверить адаптивность.', 'doing', 'high', maker, 0),
                ('Подготовить набор иконок', 'Собрать SVG-иконки в едином стиле, без внешних зависимостей.', 'doing', 'low', lead, 2),
                ('Проверить форму обратной связи', 'Проверить обязательные поля и полезные сообщения об ошибках.', 'review', 'high', maker, 1),
                ('Согласовать цветовую палитру', 'Проверить контраст основного текста, кнопок и подписей.', 'done', 'normal', lead, None),
                ('Определить задачи проекта', 'Описать результат первой версии и критерии готовности.', 'done', 'low', maker, None),
            ]
            for title, description, status, priority, assignee, offset in samples:
                Task.objects.create(board=board, creator=lead, title=title, description=description, status=status, priority=priority, assignee=assignee, due_date=timezone.localdate() + timedelta(days=offset) if offset is not None else None)
            second = Board.objects.create(name='Рабочие процессы', description='Небольшие улучшения ежедневной работы команды.')
            Membership.objects.create(board=second, user=lead, role='manager')
            Task.objects.create(board=second, creator=lead, assignee=lead, title='Подготовить шаблон постановки задачи')
            with access_file.open('x', encoding='utf-8') as stream:
                stream.write('Локальные синтетические аккаунты. Не переносить в публичный сервис.\n')
                for user, role, password in accounts:
                    stream.write(f'{user.username}\t{role}\t{password}\n')
        self.stdout.write('Created invented boards and accounts. Credentials: .state/demo-access.txt')
