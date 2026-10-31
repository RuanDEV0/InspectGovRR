"""Processo separado que observa o .env e agenda a sincronização."""

import signal
import time
from threading import Event

import environ
from django.conf import settings
from django.core.management.base import BaseCommand

from contratos.services import describe_contracts, describe_details, sync_contract_details, sync_contracts
from integrations.sync.runner import run_sync
from receita_arrecadada.services import sync_revenue
from remuneracoes.services import sync_payroll

POLL_SECONDS = 15
REVENUE_INTERVAL_SECONDS = 24 * 60 * 60
PAYROLL_INTERVAL_SECONDS = 24 * 60 * 60
CONTRACTS_INTERVAL_SECONDS = 24 * 60 * 60


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


def read_revenue_sync_enabled():
    environ.Env.read_env(settings.BASE_DIR / '.env', overwrite=True)
    env = environ.Env()
    has_credentials = bool(env('FIPLAN_USERNAME', default='') and env('FIPLAN_PASSWORD', default=''))
    return env.bool('FIPLAN_REVENUE_AUTO_SYNC_ENABLED', default=has_credentials)


def read_payroll_sync_enabled():
    environ.Env.read_env(settings.BASE_DIR / '.env', overwrite=True)
    env = environ.Env()
    has_credentials = bool(env('FIPLAN_USERNAME', default='') and env('FIPLAN_PASSWORD', default=''))
    return env.bool('FIPLAN_PAYROLL_AUTO_SYNC_ENABLED', default=has_credentials)


def read_contracts_sync_enabled():
    environ.Env.read_env(settings.BASE_DIR / '.env', overwrite=True)
    env = environ.Env()
    has_credentials = bool(env('FIPLAN_USERNAME', default='') and env('FIPLAN_PASSWORD', default=''))
    return env.bool('FIPLAN_CONTRACTS_AUTO_SYNC_ENABLED', default=has_credentials)


class Command(BaseCommand):
    help = 'Sincroniza automaticamente conforme FIPLAN_AUTO_SYNC_ENABLED e FIPLAN_SYNC_INTERVAL_MINUTES.'

    def handle(self, *args, **options):
        stop = Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        last_finished = None
        last_revenue_finished = None
        last_payroll_finished = None
        last_contracts_finished = None
        was_enabled = False
        revenue_was_enabled = False
        self.stdout.write('Agendador Fiplan iniciado; observando o arquivo .env.')

        while not stop.is_set():
            try:
                enabled, interval, year, nature_code, include_dailies = read_sync_config()
                revenue_enabled = read_revenue_sync_enabled()
                payroll_enabled = read_payroll_sync_enabled()
                contracts_enabled = read_contracts_sync_enabled()
            except (ValueError, TypeError) as exc:
                self.stderr.write(f'Configuração de sincronização inválida: {exc}')
                stop.wait(POLL_SECONDS)
                continue

            if revenue_enabled:
                if not revenue_was_enabled:
                    self.stdout.write('Sincronização diária de receita ativada.')
                revenue_was_enabled = True
                revenue_due = (
                    last_revenue_finished is None
                    or time.monotonic() - last_revenue_finished >= REVENUE_INTERVAL_SECONDS
                )
                if revenue_due:
                    try:
                        snapshot = sync_revenue()
                        self.stdout.write(self.style.SUCCESS(
                            f'Receita atualizada: {len(snapshot.rows)} unidades, '
                            f'{snapshot.month_start:02d}-{snapshot.month_end:02d}/{snapshot.fiscal_year}'
                        ))
                    except Exception as exc:
                        self.stderr.write(f'Sincronização da receita falhou: {exc}')
                    last_revenue_finished = time.monotonic()
            else:
                if revenue_was_enabled:
                    self.stdout.write('Sincronização diária de receita pausada.')
                revenue_was_enabled = False
                last_revenue_finished = None

            if payroll_enabled:
                payroll_due = (
                    last_payroll_finished is None
                    or time.monotonic() - last_payroll_finished >= PAYROLL_INTERVAL_SECONDS
                )
                if payroll_due and not stop.is_set():
                    try:
                        snapshot = sync_payroll()
                        self.stdout.write(self.style.SUCCESS(
                            f'Remunerações atualizadas: {len(snapshot.rows)} registros, '
                            f'{snapshot.month:02d}/{snapshot.year}'
                        ))
                    except Exception as exc:
                        self.stderr.write(f'Sincronização de remunerações falhou: {type(exc).__name__}')
                    last_payroll_finished = time.monotonic()
            else:
                last_payroll_finished = None

            if contracts_enabled:
                contracts_due = (
                    last_contracts_finished is None
                    or time.monotonic() - last_contracts_finished >= CONTRACTS_INTERVAL_SECONDS
                )
                if contracts_due and not stop.is_set():
                    try:
                        snapshot = sync_contracts()
                        self.stdout.write(self.style.SUCCESS(describe_contracts(snapshot)))
                        counts = sync_contract_details(snapshot.fiscal_year)
                        self.stdout.write(self.style.SUCCESS(describe_details(counts)))
                    except Exception as exc:
                        self.stderr.write(f'Sincronização de contratos falhou: {exc}')
                    last_contracts_finished = time.monotonic()
            else:
                last_contracts_finished = None

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
