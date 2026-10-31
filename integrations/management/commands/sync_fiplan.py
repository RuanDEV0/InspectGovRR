"""Executa uma sincronização manual da Fiplan."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from integrations.sync.runner import run_sync


class Command(BaseCommand):
    help = 'Sincroniza unidades e estatísticas por credor da API Fiplan.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=settings.FIPLAN_SYNC_YEAR)
        parser.add_argument('--nature-code', default=settings.FIPLAN_NATURE_CODE)
        parser.add_argument('--include-dailies', action='store_true')

    def handle(self, *args, **options):
        year = options['year']
        if year < 2000 or year > 9999:
            raise CommandError('O exercício deve ser um ano entre 2000 e 9999')
        try:
            counts = run_sync(
                fiscal_year=year,
                nature_code=options['nature_code'],
                include_dailies=options['include_dailies'] or settings.FIPLAN_SYNC_DIARIAS_ENABLED,
            )
        except Exception as exc:
            raise CommandError(f'Sincronização falhou: {type(exc).__name__}') from None
        self.stdout.write(self.style.SUCCESS(f'Sincronização concluída: {counts}'))
