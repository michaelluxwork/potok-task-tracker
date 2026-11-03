from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import OperationalError, close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from .models import Board, Membership, Task

PASSWORD = 'AnInventedTestPassword_57!'

@override_settings(ALLOWED_HOSTS=['testserver', '127.0.0.1'])
class TrackerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.manager = users.objects.create_user('leadtest', password=PASSWORD)
        cls.member = users.objects.create_user('makertest', password=PASSWORD)
        cls.viewer = users.objects.create_user('readtest', password=PASSWORD)
        cls.outsider = users.objects.create_user('outside', password=PASSWORD)
        cls.staff = users.objects.create_user('staff', password=PASSWORD, is_staff=True)
        cls.superuser = users.objects.create_superuser('admin', password=PASSWORD)
        cls.board = Board.objects.create(name='Private Alpha', description='Synthetic project')
        for user, role in [(cls.manager, 'manager'), (cls.member, 'member'), (cls.viewer, 'viewer')]:
            Membership.objects.create(board=cls.board, user=user, role=role)
        cls.other = Board.objects.create(name='Private Beta')
        Membership.objects.create(board=cls.other, user=cls.outsider, role='manager')
        cls.task = Task.objects.create(board=cls.board, creator=cls.manager, title='Existing', assignee=cls.member)
        cls.other_task = Task.objects.create(board=cls.other, creator=cls.outsider, title='Secret Beta')

    def setUp(self):
        self.client.force_login(self.manager)

    def path(self, suffix=''):
        return f'/boards/{self.board.id}/{suffix}'

    def payload(self, **overrides):
        return {'title': 'New task', 'description': 'Expected result', 'status': 'todo', 'priority': 'normal', 'due_date': '', **overrides}

    def post(self, url, data, **extra):
        return self.client.post(url, data, content_type='application/x-www-form-urlencoded', **extra) if isinstance(data, str) else self.client.post(url, __import__('urllib.parse', fromlist=['urlencode']).urlencode(data or {'csrfmiddlewaretoken': 'test'}), content_type='application/x-www-form-urlencoded', **extra)

    def test_login_required_for_all_private_routes(self):
        self.client.logout()
        for url in ['/boards/', '/boards/new/', self.path(), self.path('members/'), self.path('tasks/new/'), self.path(f'tasks/{self.task.id}/')]:
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_registration_hash_and_no_private_access(self):
        self.client.logout()
        response = self.post('/accounts/signup/', {'username': 'newperson', 'password1': PASSWORD, 'password2': PASSWORD})
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='newperson')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_superuser or user.is_staff)
        self.assertNotContains(self.client.get('/boards/'), 'Private Alpha')
        self.assertEqual(self.client.get(self.path()).status_code, 404)

    @override_settings(PUBLIC_MODE=True)
    def test_public_registration_cap_has_no_partial_account(self):
        self.client.logout()
        users = get_user_model()
        users.objects.bulk_create([users(username=f'cap{i}') for i in range(20-users.objects.count())])
        response = self.post('/accounts/signup/', {'username': 'overcap', 'password1': PASSWORD, 'password2': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'достигнут лимит 20 аккаунтов')
        self.assertEqual(users.objects.count(), 20)
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(PUBLIC_MODE=True)
    def test_public_board_cap_has_no_partial_membership(self):
        Board.objects.bulk_create([Board(name=f'Cap {i}') for i in range(40-Board.objects.count())])
        members = Membership.objects.count()
        response = self.post('/boards/new/', {'name': 'Overcap', 'description': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'достигнут лимит 40 досок')
        self.assertEqual(Board.objects.count(), 40)
        self.assertEqual(Membership.objects.count(), members)

    def test_registration_rejects_duplicate_weak_and_mismatch(self):
        self.client.logout()
        for username, first, second in [('leadtest', PASSWORD, PASSWORD), ('newuser', '123', '123'), ('newuser', PASSWORD, 'different')]:
            response = self.post('/accounts/signup/', {'username': username, 'password1': first, 'password2': second})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='newuser').exists())

    def test_registration_cannot_self_promote(self):
        self.client.logout()
        response = self.post('/accounts/signup/', {'username': 'elevate', 'password1': PASSWORD, 'password2': PASSWORD, 'is_superuser': '1'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username='elevate').exists())

    def test_login_external_next_ignored(self):
        self.client.logout()
        response = self.post('/accounts/login/', {'username': 'leadtest', 'password': PASSWORD, 'next': 'https://example.com/steal'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/boards/')

    def test_logout_post_only(self):
        self.assertEqual(self.client.get('/accounts/logout/').status_code, 405)
        self.assertEqual(self.post('/accounts/logout/', {}).status_code, 302)
        self.assertEqual(self.client.get(self.path()).status_code, 302)

    def test_new_board_atomic_membership_and_validation(self):
        count = Board.objects.count()
        response = self.post('/boards/new/', {'name': '  ', 'description': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Board.objects.count(), count)
        response = self.post('/boards/new/', {'name': 'Fresh', 'description': 'Goal'})
        self.assertEqual(response.status_code, 302)
        board = Board.objects.get(name='Fresh')
        self.assertEqual(board.memberships.get().user, self.manager)
        self.assertEqual(board.memberships.get().role, 'manager')

    def test_board_list_isolated_and_pagination(self):
        response = self.client.get('/boards/')
        self.assertContains(response, 'Private Alpha')
        self.assertNotContains(response, 'Private Beta')
        for index in range(21):
            board = Board.objects.create(name=f'Page {index}')
            Membership.objects.create(board=board, user=self.manager, role='manager')
        self.assertEqual(len(self.client.get('/boards/').context['board_page']), 20)
        self.assertEqual(len(self.client.get('/boards/?page=2').context['board_page']), 2)

    def test_board_list_counts_full_team_without_exposing_foreign_boards(self):
        for user in [self.manager, self.member, self.viewer]:
            self.client.force_login(user)
            response = self.client.get('/boards/')
            visible = list(response.context['board_page'])
            self.assertEqual(len(visible), 1)
            self.assertEqual(visible[0].member_count, 3)
            self.assertEqual(visible[0].task_count, 1)
            self.assertEqual(visible[0].done_count, 0)
            self.assertEqual(visible[0].id, self.board.id)

    def test_cross_board_detail_and_mutations_are_404(self):
        for suffix, data in [('', None), ('members/', None), ('tasks/new/', self.payload()), (f'tasks/{self.other_task.id}/move/', {'status': 'done', 'version': 1})]:
            url = f'/boards/{self.other.id}/{suffix}'
            response = self.client.get(url) if data is None else self.post(url, data)
            self.assertEqual(response.status_code, 404, url)
        self.assertEqual(self.client.get(self.path(f'tasks/{self.other_task.id}/')).status_code, 404)
        self.assertEqual(self.post(self.path(f'tasks/{self.other_task.id}/move/'), {'status': 'done', 'version': 1}).status_code, 404)

    def test_staff_no_implicit_access_superuser_has_access(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.path()).status_code, 404)
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.path()).status_code, 200)

    def test_manager_task_create_edit_move_delete(self):
        response = self.post(self.path('tasks/new/'), self.payload(assignee=self.member.id))
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title='New task')
        self.assertEqual(task.assignee, self.member)
        self.assertEqual(task.creator, self.manager)
        response = self.post(self.path(f'tasks/{task.id}/'), self.payload(title='Edited', assignee=self.manager.id, version=1))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.title, 'Edited')
        self.assertEqual(task.version, 2)
        response = self.post(self.path(f'tasks/{task.id}/move/'), {'status': 'done', 'version': 2}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['version'], 3)
        self.assertEqual(response.json()['status'], 'done')
        self.assertEqual(self.post(self.path(f'tasks/{task.id}/delete/'), {'version': 3, 'confirm': 'on'}).status_code, 302)
        self.assertFalse(Task.objects.filter(id=task.id).exists())

    def test_assignment_foreign_user_and_viewer_rejected(self):
        for user in [self.outsider, self.viewer]:
            response = self.post(self.path('tasks/new/'), self.payload(assignee=user.id))
            self.assertEqual(response.status_code, 200)
            self.assertIn('assignee', response.context['form'].errors)
        self.assertFalse(Task.objects.filter(title='New task').exists())

    def test_member_task_create_forces_self_and_blocks_forgery(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post(self.path('tasks/new/'), self.payload(assignee=self.manager.id)).status_code, 400)
        self.assertEqual(self.post(self.path('tasks/new/'), self.payload()).status_code, 302)
        self.assertEqual(Task.objects.get(title='New task').assignee, self.member)
        for field in ['creator', 'board', 'role']:
            self.assertEqual(self.post(self.path('tasks/new/'), self.payload(**{field: 1})).status_code, 400)

    def test_member_edit_own_task_only(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post(self.path(f'tasks/{self.task.id}/'), self.payload(title='Own edit', version=1)).status_code, 302)
        foreign_task = Task.objects.create(board=self.board, creator=self.member, assignee=self.manager, title='Not assigned to member')
        for suffix, data in [('', self.payload(version=1)), ('move/', {'status': 'done', 'version': 1}), ('delete/', {'version': 1, 'confirm': 'on'})]:
            self.assertEqual(self.post(self.path(f'tasks/{foreign_task.id}/{suffix}'), data).status_code, 403)
        self.assertEqual(self.client.get(self.path(f'tasks/{foreign_task.id}/')).status_code, 200)

    def test_viewer_reads_without_writes_or_drag(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.path())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'draggable="true"')
        self.assertNotContains(response, 'Создать задачу')
        self.assertEqual(self.client.get(self.path('members/')).status_code, 200)
        for url, data in [(self.path('tasks/new/'), self.payload()), (self.path(f'tasks/{self.task.id}/'), self.payload(version=1)), (self.path(f'tasks/{self.task.id}/move/'), {'status': 'done', 'version': 1}), (self.path(f'tasks/{self.task.id}/delete/'), {'version': 1, 'confirm': 'on'}), (self.path('members/'), {'action': 'add', 'username': 'outside', 'role': 'manager'})]:
            self.assertEqual(self.post(url, data).status_code, 403, url)

    def test_stale_move_edit_delete_do_not_overwrite(self):
        move = self.path(f'tasks/{self.task.id}/move/')
        self.assertEqual(self.post(move, {'status': 'doing', 'version': 1}).status_code, 302)
        self.assertEqual(self.post(move, {'status': 'done', 'version': 1}).status_code, 409)
        self.assertEqual(self.post(self.path(f'tasks/{self.task.id}/'), self.payload(version=1)).status_code, 409)
        self.assertEqual(self.post(self.path(f'tasks/{self.task.id}/delete/'), {'version': 1, 'confirm': 'on'}).status_code, 409)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'doing')
        self.assertEqual(self.task.title, 'Existing')
        self.assertEqual(self.task.version, 2)

    def test_members_add_change_remove_unassigns_task(self):
        url = self.path('members/')
        self.assertEqual(self.post(url, {'action': 'add', 'username': 'outside', 'role': 'member'}).status_code, 302)
        membership = Membership.objects.get(board=self.board, user=self.member)
        self.assertEqual(self.post(url, {'action': 'change', 'membership_id': membership.id, 'role': 'viewer'}).status_code, 302)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assignee)
        self.assertEqual(self.task.version, 2)
        self.client.force_login(self.member)
        self.assertEqual(self.post(self.path(f'tasks/{self.task.id}/move/'), {'status': 'doing', 'version': 2}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.post(url, {'action': 'remove', 'membership_id': membership.id}).status_code, 302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.path()).status_code, 404)
        self.assertTrue(Task.objects.filter(id=self.task.id).exists())

    def test_last_manager_and_membership_foreign_id_protected(self):
        membership = Membership.objects.get(board=self.board, user=self.manager)
        for action in ['change', 'remove']:
            self.assertEqual(self.post(self.path('members/'), {'action': action, 'membership_id': membership.id, 'role': 'viewer'}).status_code, 409)
        foreign = Membership.objects.get(board=self.other)
        self.assertEqual(self.post(self.path('members/'), {'action': 'remove', 'membership_id': foreign.id}).status_code, 404)
        self.assertEqual(self.post(self.path('members/'), {'action': 'add', 'username': 'outside', 'role': 'superuser'}).status_code, 200)

    def test_member_cannot_promote_self(self):
        self.client.force_login(self.member)
        membership = Membership.objects.get(board=self.board, user=self.member)
        self.assertEqual(self.post(self.path('members/'), {'action': 'change', 'membership_id': membership.id, 'role': 'manager'}).status_code, 403)
        membership.refresh_from_db()
        self.assertEqual(membership.role, 'member')

    def test_duplicate_membership_and_invalid_user_have_form_errors(self):
        for username in ['makertest', 'missing-user']:
            response = self.post(self.path('members/'), {'action': 'add', 'username': username, 'role': 'member'})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)

    def test_csrf_origin_and_secure_headers(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post(self.path(f'tasks/{self.task.id}/move/'), 'status=done&version=1', content_type='application/x-www-form-urlencoded').status_code, 403)
        response = client.get(self.path('tasks/new/'))
        token = client.cookies['csrftoken'].value
        response = client.post(self.path(f'tasks/{self.task.id}/move/'), 'status=done&version=1', content_type='application/x-www-form-urlencoded', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_no_get_mutation(self):
        for suffix in ['move/', 'delete/']:
            url = self.path(f'tasks/{self.task.id}/{suffix}')
            self.assertEqual(self.client.get(url, {'status': 'done', 'version': 1}).status_code, 405)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'todo')

    def test_xss_stays_escaped(self):
        title = '<script>window.pwned=true</script>'
        self.task.title = title
        self.task.description = '<img src=x onerror=alert(1)>'
        self.task.save()
        response = self.client.get(self.path())
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, title)
        self.assertNotContains(response, '<img src=x')

    def test_invalid_input_no_write(self):
        before = Task.objects.count()
        for changes in [{'title': ''}, {'title': 'x'*161}, {'description': 'x'*5001}, {'status': 'evil'}, {'priority': 'urgent'}, {'due_date': 'nonsense'}]:
            response = self.post(self.path('tasks/new/'), self.payload(**changes))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertEqual(Task.objects.count(), before)
        self.assertEqual(self.post(self.path(f'tasks/{self.task.id}/move/'), {'status': 'done', 'version': '-1'}).status_code, 400)

    def test_content_type_size_duplicate_fields_unknown_fields(self):
        url = self.path('tasks/new/')
        self.assertEqual(self.client.post(url, '{}', content_type='application/json').status_code, 415)
        self.assertEqual(self.post(url, 'title='+'x'*33000).status_code, 413)
        self.assertEqual(self.post(url, 'title=one&title=two').status_code, 400)
        self.assertEqual(self.post(url, self.payload(is_staff='1')).status_code, 400)
        self.assertEqual(self.post(url, '&'.join(f'f{i}=a' for i in range(31))).status_code, 400)

    def test_unicode_membership_id_rejected(self):
        self.assertEqual(self.post(self.path('members/'), {'action': 'remove', 'membership_id': '²'}).status_code, 400)

    def test_early_errors_have_security_headers(self):
        response = self.client.post(self.path('tasks/new/'), '{}', content_type='application/json')
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])

    def test_limits_tasks_members(self):
        Task.objects.bulk_create([Task(board=self.board, creator=self.manager, title=f'Task {n}') for n in range(199)])
        response = self.post(self.path('tasks/new/'), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.board.tasks.count(), 200)
        for index in range(47):
            user = get_user_model().objects.create(username=f'limit{index}')
            Membership.objects.create(board=self.board, user=user, role='viewer')
        response = self.post(self.path('members/'), {'action': 'add', 'username': 'outside', 'role': 'member'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(self.board.memberships.count(), 50)

    def test_filters_and_bad_query(self):
        self.assertContains(self.client.get(self.path(), {'q': 'Existing'}), 'Existing')
        response = self.client.get(self.path(), {'q': 'no-match'})
        self.assertEqual(response.context['shown'], 0)
        self.assertEqual(self.client.get(self.path(), {'q': 'x'*101}).status_code, 400)
        self.assertEqual(self.client.get(self.path(), {'scope': 'evil'}).status_code, 400)

    def test_database_write_failure_rolls_back(self):
        before = Task.objects.count()
        with patch.object(Task, 'save', side_effect=OperationalError('invented failure')):
            response = self.post(self.path('tasks/new/'), self.payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(Task.objects.count(), before)
        self.assertNotContains(response, 'Задача создана', status_code=503)

    def test_static_and_path_boundary(self):
        for url in ['/.state/tracker.sqlite3', '/.git/config', '/config/settings.py', '/static/../config/settings.py', '/static/.state/secret.key']:
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_health_minimal_and_database_failure(self):
        self.client.logout()
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        with patch('boards.views.connection.cursor', side_effect=OperationalError('invented failure')):
            self.assertEqual(self.client.get('/health/').status_code, 503)

    def test_unknown_host_rejected(self):
        self.assertEqual(self.client.get('/health/', HTTP_HOST='evil.example').status_code, 400)

@override_settings(ALLOWED_HOSTS=['testserver'])
class ConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.a = get_user_model().objects.create_user('manager_a', password=PASSWORD)
        self.b = get_user_model().objects.create_user('manager_b', password=PASSWORD)
        self.board = Board.objects.create(name='Concurrent')
        self.ma = Membership.objects.create(board=self.board, user=self.a, role='manager')
        self.mb = Membership.objects.create(board=self.board, user=self.b, role='manager')
        self.task = Task.objects.create(board=self.board, creator=self.a, title='Concurrent task')

    def request_as(self, user_id, url, data):
        close_old_connections()
        client = Client()
        client.force_login(get_user_model().objects.get(pk=user_id))
        try:
            from urllib.parse import urlencode
            return client.post(url, urlencode(data), content_type='application/x-www-form-urlencoded').status_code
        finally:
            close_old_connections()

    def test_concurrent_move_only_one_wins(self):
        url = f'/boards/{self.board.id}/tasks/{self.task.id}/move/'
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request_as, user.id, url, {'status': status, 'version': 1}) for user, status in [(self.a, 'doing'), (self.b, 'done')]]
            statuses = [future.result() for future in futures]
        self.assertEqual(sorted(statuses), [302, 409])
        self.task.refresh_from_db()
        self.assertEqual(self.task.version, 2)

    def test_concurrent_last_manager_removal(self):
        url = f'/boards/{self.board.id}/members/'
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request_as, user.id, url, {'action': 'remove', 'membership_id': membership.id}) for user, membership in [(self.a, self.ma), (self.b, self.mb)]]
            statuses = [future.result() for future in futures]
        self.assertEqual(sorted(statuses), [302, 409])
        self.assertEqual(self.board.memberships.filter(role='manager').count(), 1)
