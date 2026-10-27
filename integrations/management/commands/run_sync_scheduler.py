"""Processo separado que observa o .env e agenda a sincronização."""

import signal
import time
from threading import Event

import environ
from django.conf import settings
from django.core.management.base import BaseCommand

from integrations.sync.runner import run_sync

POLL_SECONDS = 15


def read_sync_config():
    environ.Env.read_env(settings.BASE_DIR / '.env', overwrite=True)
    env = environ.Env()
    enabled = env.bool('FIPLAN_AUTO_SYNC_ENABLED', default=False)
    interval = env.int('FIPLAN_SYNC_INTERVAL_MINUTES', default=1440)
    if interval < 1:
        raise ValueError('FIPLAN_SYNC_INTERVAL_MINUTES deve ser maior que zero')
    return (
        enabled,
        interval,
        settings.FIPLAN_SYNC_YEAR,
        settings.FIPLAN_NATURE_CODE,
        settings.FIPLAN_SYNC_DIARIAS_ENABLED,
    )


class Command(BaseCommand):
    help = 'Sincroniza automaticamente conforme FIPLAN_AUTO_SYNC_ENABLED e FIPLAN_SYNC_INTERVAL_MINUTES.'

    def handle(self, *args, **options):
        stop = Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        last_finished = None
        was_enabled = False
        self.stdout.write('Agendador Fiplan iniciado; observando o arquivo .env.')

        while not stop.is_set():
            try:
                enabled, interval, year, nature_code, include_dailies = read_sync_config()
            except (ValueError, TypeError) as exc:
                self.stderr.write(f'Configuração de sincronização inválida: {exc}')
                stop.wait(POLL_SECONDS)
                continue

            if not enabled:
                if was_enabled:
                    self.stdout.write('Sincronização automática pausada.')
                was_enabled = False
                last_finished = None
                stop.wait(POLL_SECONDS)
                continue

            if not was_enabled:
                self.stdout.write(f'Sincronização ativada; intervalo de {interval} minuto(s).')
            was_enabled = True
            now = time.monotonic()
            remaining = 0 if last_finished is None else interval * 60 - (now - last_finished)
            if remaining > 0:
                stop.wait(min(remaining, POLL_SECONDS))
                continue

            try:
                counts = run_sync(
                    fiscal_year=year,
                    nature_code=nature_code,
                    include_dailies=include_dailies,
                )
                self.stdout.write(self.style.SUCCESS(f'Sincronização concluída: {counts}'))
            except Exception as exc:
                self.stderr.write(f'Sincronização falhou: {exc}')
            last_finished = time.monotonic()
