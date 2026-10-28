"""Atualiza o Top 5 da receita arrecadada para o período corrente."""

from django.core.management.base import BaseCommand, CommandError

from receita_arrecadada.services import sync_revenue


class Command(BaseCommand):
    help = 'Consulta a Fiplan uma vez e salva o Top 5 de receita arrecadada.'

    def handle(self, *args, **options):
        try:
            snapshot = sync_revenue()
        except Exception as exc:
            raise CommandError(f'Sincronização da receita falhou: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(
            f'Top {len(snapshot.rows)} atualizado: '
            f'{snapshot.month_start:02d}-{snapshot.month_end:02d}/{snapshot.fiscal_year}'
        ))
