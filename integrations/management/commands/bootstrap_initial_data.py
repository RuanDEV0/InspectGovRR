"""Preenche apenas os conjuntos ausentes após a inicialização do web."""

from contextlib import contextmanager

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from contratos.models import ContractSnapshot
from contratos.services import local_today, sync_contracts
from integrations.models import SyncRun
from integrations.sync.runner import run_sync
from receita_arrecadada.models import RevenueSnapshot
from receita_arrecadada.services import current_period, sync_revenue
from remuneracoes.models import PayrollSnapshot
from remuneracoes.services import sync_payroll
from unidades.models import Unit


# Bloqueio de sessão do PostgreSQL: um deploy novo pode iniciar antes do antigo terminar.
INITIAL_LOAD_LOCK_ID = 873196410390452028


@contextmanager
def initial_load_lock():
    if connection.vendor != 'postgresql':
        yield True
        return

    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [INITIAL_LOAD_LOCK_ID])
        acquired = cursor.fetchone()[0]
        try:
            yield acquired
        finally:
            if acquired:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [INITIAL_LOAD_LOCK_ID])


class Command(BaseCommand):
    help = 'Faz a primeira carga dos conjuntos ainda ausentes no banco, sem agendador.'

    def handle(self, *args, **options):
        if not settings.FIPLAN_USERNAME or not settings.FIPLAN_PASSWORD:
            raise CommandError('Carga inicial requer FIPLAN_USERNAME e FIPLAN_PASSWORD no serviço web.')

        with initial_load_lock() as acquired:
            if not acquired:
                self.stdout.write('Carga inicial já está em andamento em outra instância.')
                return

            self.stdout.write('Carga inicial Fiplan iniciada.')
            failed = []
            year = settings.FIPLAN_SYNC_YEAR
            nature_code = settings.FIPLAN_NATURE_CODE
            steps = (
                (
                    'receita',
                    lambda: RevenueSnapshot.objects.filter(fiscal_year=current_period()[0]).exists(),
                    sync_revenue,
                ),
                (
                    'remunerações',
                    lambda: PayrollSnapshot.objects.exists(),
                    sync_payroll,
                ),
                (
                    'contratos',
                    lambda: ContractSnapshot.objects.filter(fiscal_year=local_today().year).exists(),
                    sync_contracts,
                ),
                (
                    'unidades e credores',
                    lambda: Unit.objects.exists() and SyncRun.objects.filter(
                        status=SyncRun.Status.SUCCESS,
                        fiscal_year=year,
                        nature_code=nature_code,
                    ).exists(),
                    lambda: run_sync(fiscal_year=year, nature_code=nature_code),
                ),
            )

            for label, already_loaded, collect in steps:
                if already_loaded():
                    self.stdout.write(f'Carga inicial: etapa ignorada, dados já presentes ({label}).')
                    continue
                self.stdout.write(f'Carga inicial: importando {label}.')
                try:
                    collect()
                except Exception as exc:
                    # Erros HTTP podem conter identificadores ou URLs da API.
                    self.stderr.write(f'Carga inicial: {label} falhou ({type(exc).__name__}).')
                    failed.append(label)
                else:
                    self.stdout.write(self.style.SUCCESS(f'Carga inicial: etapa concluída ({label}).'))

            if failed:
                raise CommandError('Carga inicial incompleta; consulte as etapas acima. '
                                   'As etapas ausentes serão tentadas no próximo início do web.')
            self.stdout.write(self.style.SUCCESS('Carga inicial concluída.'))
