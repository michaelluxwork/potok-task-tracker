"""Container startup; persistent volume must already be mounted."""
import os
import subprocess
import sys

if os.environ.get('TRACKER_PUBLIC') == '1' and not os.environ.get('TRACKER_PUBLIC_RELEASE_APPROVED') == '1':
    raise SystemExit('Public launch is gated. Complete the deployment review in RAILWAY.md first.')
for command in [('check', '--deploy', '--fail-level', 'ERROR'), ('migrate', '--noinput'), ('collectstatic', '--noinput')]:
    subprocess.run([sys.executable, 'manage.py', *command], check=True)
os.execv(sys.executable, [sys.executable, 'serve.py'])
