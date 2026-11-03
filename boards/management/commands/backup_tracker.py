import sqlite3
from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Create checked online SQLite backup, retaining the latest five snapshots.'

    def handle(self, *args, **options):
        source_path = settings.STATE_DIR / 'tracker.sqlite3'
        if not source_path.is_file():
            raise CommandError('Database does not exist.')
        folder = settings.STATE_DIR / 'backups'
        folder.mkdir(exist_ok=True)
        target_path = folder / f'tracker-{datetime.now(timezone.utc):%Y%m%d-%H%M%S-%f}.sqlite3'
        try:
            with sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(target_path) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise CommandError('Backup integrity check failed; source database remains untouched.')
        except sqlite3.Error as error:
            raise CommandError('Backup failed; source database remains untouched.') from error
        # Only snapshots generated in this dedicated directory are subject to retention.
        for old in sorted(folder.glob('tracker-*.sqlite3'))[:-5]:
            old.unlink()
        self.stdout.write(f'Backup checked: {target_path.name}')
