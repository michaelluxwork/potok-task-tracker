"""One-time root bootstrap of a fresh synthetic curator instance; never prints secrets."""
import os
import pwd
import secrets
import subprocess
import sys
from pathlib import Path

release = Path(sys.argv[1]).resolve()
state = Path('/var/lib/potok-demo')
env_path = Path('/etc/potok-demo.env')
assert os.geteuid() == 0 and release == Path('/opt/potok-demo/releases/curator-v1')
assert not state.exists() and not env_path.exists()
account = pwd.getpwnam('potok-demo')
state.mkdir(mode=0o700)
os.chown(state, account.pw_uid, account.pw_gid)
values = {
    'TRACKER_PUBLIC':'1', 'TRACKER_PUBLIC_RELEASE_APPROVED':'1',
    'TRACKER_STATE_DIR':str(state), 'DJANGO_SECRET_KEY':secrets.token_urlsafe(64),
    'DJANGO_ALLOWED_HOSTS':'potok.178-255-126-110.sslip.io',
    'DJANGO_CSRF_TRUSTED_ORIGINS':'https://potok.178-255-126-110.sslip.io',
    'TRACKER_TRUSTED_PROXY':'127.0.0.1', 'TRACKER_BIND_HOST':'127.0.0.1',
    'TRACKER_THREADS':'2', 'PORT':'4366',
}
with env_path.open('x', encoding='ascii') as stream:
    stream.write(''.join(f'{k}={v}\n' for k,v in values.items()))
env_path.chmod(0o600)
env = dict(os.environ, **values)
python = str(release / '.venv/bin/python')
subprocess.run([python, 'manage.py', 'collectstatic', '--noinput'], cwd=release, env=env, check=True)
for path in (release/'staticfiles').rglob('*'):
    path.chmod(0o755 if path.is_dir() else 0o644)
(release/'staticfiles').chmod(0o755)

def demote():
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)

# Seed is explicitly local-only and runs once into a new synthetic state, before exposure.
local_env = dict(env, TRACKER_PUBLIC='0')
for command in [('migrate','--noinput'), ('seed_demo',), ('backup_tracker',)]:
    subprocess.run([python,'manage.py',*command], cwd=release, env=local_env, preexec_fn=demote, check=True)
subprocess.run([python,'manage.py','check','--deploy','--fail-level','ERROR'], cwd=release, env=env, preexec_fn=demote, check=True)
access = state / 'demo-access.txt'
access.chmod(0o600)
entries = [line.split('\t') for line in access.read_text(encoding='utf-8').splitlines() if '\t' in line]
assert len(entries) == 3
handoff = state / 'curator-handoff.txt'
with handoff.open('x',encoding='utf-8') as stream:
    stream.write('Поток — учебное демо для проверки куратором\nhttps://potok.178-255-126-110.sslip.io/\nТолько вымышленные данные. Не вводите личные или клиентские сведения.\n\n')
    labels = {'manager':'Руководитель','member':'Исполнитель','viewer':'Наблюдатель'}
    for name,role,password in entries:
        stream.write(f'{labels[role]}: логин {name}, пароль {password}\n')
    stream.write('\nПроверка: войдите lead → Запуск сайта → создайте задачу → измените статус → Участники. maker меняет назначенные ему задачи, reader только читает. Регистрация создаёт отдельное пустое пространство.\n')
handoff.chmod(0o600)
print('FRESH_SYNTHETIC_BOOTSTRAP_OK; credentials retained only in root-private handoff')
