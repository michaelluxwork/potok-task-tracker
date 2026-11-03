from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from .forms import BoardForm, DeleteForm, MemberForm, MoveForm, TaskForm
from .models import Board, Membership, Task

def error_response(request, status, detail):
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'error': detail}, status=status)
    return render(request, 'error.html', {'error_status': status, 'error_detail': detail}, status=status)

def error400(request, exception=None):
    return error_response(request, 400, 'Проверьте адрес и поля формы.')

def error403(request, exception=None):
    return error_response(request, 403, 'У вас нет прав на это действие. Вернитесь на доску или обратитесь к её руководителю.')

def error404(request, exception=None):
    return error_response(request, 404, 'Страница не найдена или у вас нет доступа к этой доске.')

def error500(request):
    return error_response(request, 500, 'Не удалось выполнить действие. Проверьте доску перед повторной отправкой.')

def csrf_failure(request, reason=''):
    return error_response(request, 403, 'Сессия формы устарела или источник запроса не подтверждён. Обновите страницу и повторите действие.')

def allowed_fields(request, names):
    return not (set(request.POST) - set(names) - {'csrfmiddlewaretoken'})

def strict_post(names):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == 'POST' and not allowed_fields(request, names):
                return error400(request)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate

class TrackerLogin(LoginView):
    template_name = 'auth.html'
    extra_context = {'auth_title': 'С возвращением', 'auth_subtitle': 'Ваши проекты, команда и задачи — в одном месте.'}

    def post(self, request, *args, **kwargs):
        if not allowed_fields(request, ['username', 'password', 'next']):
            return error400(request)
        return super().post(request, *args, **kwargs)

class TrackerLogout(LogoutView):
    http_method_names = ['post', 'options']

@require_GET
def home(request):
    return redirect('boards')

@require_http_methods(['GET', 'POST'])
@strict_post(['username', 'password1', 'password2'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('boards')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Bound the public curator demo, including concurrent registrations.
            if settings.PUBLIC_MODE and get_user_model().objects.count() >= 20:
                form.add_error(None, 'Учебное демо: достигнут лимит 20 аккаунтов. Используйте выданный учебный аккаунт.')
            else:
                user = form.save()
                login(request, user)
                messages.success(request, 'Аккаунт создан. Создайте свою доску или передайте логин руководителю команды.')
                return redirect('boards')
    return render(request, 'auth.html', {'form': form, 'signup': True, 'auth_title': 'Начните с чистого листа', 'auth_subtitle': 'Создайте аккаунт, чтобы собрать задачи и команду.'})

def accessible_boards(user):
    queryset = Board.objects.all()
    if not user.is_superuser:
        queryset = queryset.filter(pk__in=Membership.objects.filter(user=user).values('board_id'))
    return queryset

def board_and_role(request, board_id):
    board = get_object_or_404(accessible_boards(request.user), pk=board_id)
    role = Membership.Role.MANAGER if request.user.is_superuser else Membership.objects.get(board=board, user=request.user).role
    return board, role

def require_manager(role):
    if role != Membership.Role.MANAGER:
        raise PermissionDenied

def can_edit(user, role, task):
    return role == Membership.Role.MANAGER or (role == Membership.Role.MEMBER and task.assignee_id == user.id)

@login_required
@require_GET
def board_list(request):
    boards = accessible_boards(request.user).annotate(task_count=Count('tasks', distinct=True), done_count=Count('tasks', filter=Q(tasks__status='done'), distinct=True), member_count=Count('memberships', distinct=True)).order_by('-created_at', '-id')
    page = Paginator(boards, 20).get_page(request.GET.get('page'))
    return render(request, 'board_list.html', {'board_page': page})

@login_required
@require_http_methods(['GET', 'POST'])
@strict_post(['name', 'description'])
def board_create(request):
    form = BoardForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            if settings.PUBLIC_MODE and Board.objects.count() >= 40:
                form.add_error(None, 'Учебное демо: достигнут лимит 40 досок. Используйте существующую доску.')
            else:
                board = form.save()
                Membership.objects.create(board=board, user=request.user, role='manager')
                messages.success(request, 'Доска создана. Добавьте задачу или пригласите зарегистрированных участников.')
                return redirect('board', board_id=board.id)
    return render(request, 'board_form.html', {'form': form})

@login_required
@require_GET
def board_detail(request, board_id):
    board, role = board_and_role(request, board_id)
    query = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    priority = request.GET.get('priority', '')
    if len(query) > 100 or scope not in ['all', 'mine'] or priority not in ['', 'low', 'normal', 'high']:
        return error400(request)
    tasks = board.tasks.select_related('assignee')
    total = tasks.count()
    done = tasks.filter(status='done').count()
    if query:
        tasks = tasks.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if scope == 'mine':
        tasks = tasks.filter(assignee=request.user)
    if priority:
        tasks = tasks.filter(priority=priority)
    columns = []
    task_list = list(tasks)
    for task in task_list:
        task.editable = can_edit(request.user, role, task)
    for value, label in Task.Status.choices:
        columns.append({'value': value, 'label': label, 'tasks': [task for task in task_list if task.status == value]})
    membership_list = board.memberships.select_related('user').order_by('user__username')
    return render(request, 'board.html', {'board': board, 'role': role, 'role_label': Membership.Role(role).label, 'columns': columns, 'query': query, 'scope': scope, 'priority': priority, 'total': total, 'done': done, 'shown': len(task_list), 'memberships': membership_list, 'today': timezone.localdate(), 'can_create': role != 'viewer'})

def task_fields(role):
    fields = ['title', 'description', 'status', 'priority', 'due_date', 'version']
    if role == Membership.Role.MANAGER:
        fields.append('assignee')
    return fields

@login_required
@require_http_methods(['GET', 'POST'])
def task_create(request, board_id):
    with transaction.atomic():
        board, role = board_and_role(request, board_id)
        if role == 'viewer':
            raise PermissionDenied
        if request.method == 'POST' and not allowed_fields(request, task_fields(role)):
            return error400(request)
        status = request.GET.get('status', 'todo')
        initial = {'status': status if status in Task.Status.values else 'todo'}
        form = TaskForm(request.POST or None, board=board, user=request.user, role=role, initial=initial)
        if request.method == 'POST' and form.is_valid():
            if board.tasks.count() >= 200:
                form.add_error(None, 'На доске уже 200 задач. Создайте новую доску или удалите ненужные задачи.')
            else:
                task = form.save(commit=False)
                task.board = board
                task.creator = request.user
                if role == 'member':
                    task.assignee = request.user
                task.save()
                messages.success(request, 'Задача создана.')
                return redirect('board', board_id=board.id)
    return render(request, 'task.html', {'board': board, 'role': role, 'form': form, 'creating': True, 'editable': True})

def conflict(request):
    return error_response(request, 409, 'Задачу уже изменили в другой вкладке. Обновите страницу: ваши данные не перезаписали новую версию.')

@login_required
@require_http_methods(['GET', 'POST'])
def task_detail(request, board_id, task_id):
    with transaction.atomic():
        board, role = board_and_role(request, board_id)
        task = get_object_or_404(Task.objects.select_related('creator', 'assignee'), pk=task_id, board=board)
        editable = can_edit(request.user, role, task)
        if request.method == 'POST' and not editable:
            raise PermissionDenied
        if request.method == 'POST' and not allowed_fields(request, task_fields(role)):
            return error400(request)
        form = TaskForm(request.POST or None, instance=task, board=board, user=request.user, role=role)
        if request.method == 'POST' and form.is_valid():
            if form.cleaned_data['version'] != task.version:
                return conflict(request)
            changes = {field: form.cleaned_data[field] for field in ['title', 'description', 'status', 'priority', 'due_date']}
            if role == 'manager':
                changes['assignee'] = form.cleaned_data['assignee']
            if not Task.objects.filter(pk=task.id, version=form.cleaned_data['version']).update(**changes, version=F('version') + 1, updated_at=timezone.now()):
                return conflict(request)
            messages.success(request, 'Изменения сохранены.')
            return redirect('board', board_id=board.id)
    return render(request, 'task.html', {'board': board, 'role': role, 'task': task, 'form': form, 'editable': editable})

@login_required
@require_POST
@strict_post(['status', 'version'])
def task_move(request, board_id, task_id):
    with transaction.atomic():
        board, role = board_and_role(request, board_id)
        task = get_object_or_404(Task, pk=task_id, board=board)
        if not can_edit(request.user, role, task):
            raise PermissionDenied
        form = MoveForm(request.POST)
        if not form.is_valid():
            return error400(request)
        if not Task.objects.filter(pk=task.id, version=form.cleaned_data['version']).update(status=form.cleaned_data['status'], version=F('version') + 1, updated_at=timezone.now()):
            return conflict(request)
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'id': task.id, 'status': form.cleaned_data['status'], 'version': form.cleaned_data['version'] + 1})
    messages.success(request, 'Статус задачи обновлён.')
    return redirect('board', board_id=board.id)

@login_required
@require_POST
@strict_post(['version', 'confirm'])
def task_delete(request, board_id, task_id):
    with transaction.atomic():
        board, role = board_and_role(request, board_id)
        require_manager(role)
        task = get_object_or_404(Task, pk=task_id, board=board)
        form = DeleteForm(request.POST)
        if not form.is_valid():
            return error400(request)
        if task.version != form.cleaned_data['version']:
            return conflict(request)
        task.delete()
    messages.success(request, 'Задача удалена.')
    return redirect('board', board_id=board.id)

@login_required
@require_http_methods(['GET', 'POST'])
@strict_post(['action', 'username', 'role', 'membership_id'])
def members(request, board_id):
    with transaction.atomic():
        board, role = board_and_role(request, board_id)
        form = MemberForm()
        if request.method == 'POST':
            require_manager(role)
            action = request.POST.get('action')
            if action == 'add':
                form = MemberForm(request.POST)
                if form.is_valid():
                    if board.memberships.count() >= 50:
                        form.add_error(None, 'На доске уже 50 участников.')
                    elif board.memberships.filter(user=form.member_user).exists():
                        form.add_error('username', 'Пользователь уже на доске. Измените его роль в списке.')
                    else:
                        Membership.objects.create(board=board, user=form.member_user, role=form.cleaned_data['role'])
                        messages.success(request, 'Участник добавлен на доску.')
                        return redirect('members', board_id=board.id)
            elif action in ['change', 'remove']:
                raw_id = request.POST.get('membership_id', '')
                if not raw_id.isascii() or not raw_id.isdigit() or len(raw_id) > 18:
                    return error400(request)
                member = get_object_or_404(Membership, pk=int(raw_id), board=board)
                new_role = request.POST.get('role') if action == 'change' else None
                if action == 'change' and new_role not in Membership.Role.values:
                    return error400(request)
                if member.role == 'manager' and new_role != 'manager' and board.memberships.filter(role='manager', user__is_active=True).count() <= 1:
                    return error_response(request, 409, 'На доске должен остаться хотя бы один руководитель. Сначала назначьте другого.')
                if action == 'remove' or new_role == 'viewer':
                    board.tasks.filter(assignee_id=member.user_id).update(assignee=None, version=F('version') + 1, updated_at=timezone.now())
                if action == 'remove':
                    member.delete()
                else:
                    member.role = new_role
                    member.save(update_fields=['role'])
                messages.success(request, 'Состав команды обновлён.')
                return redirect('members' if request.user.is_superuser or board.memberships.filter(user=request.user).exists() else 'boards', **({'board_id': board.id} if request.user.is_superuser or board.memberships.filter(user=request.user).exists() else {}))
            else:
                return error400(request)
        membership_list = list(board.memberships.select_related('user').order_by('user__username'))
    return render(request, 'members.html', {'board': board, 'role': role, 'form': form, 'memberships': membership_list, 'roles': Membership.Role.choices})

@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1 FROM boards_board LIMIT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})
