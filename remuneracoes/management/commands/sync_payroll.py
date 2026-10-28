from django.core.management.base import BaseCommand, CommandError

from remuneracoes.services import sync_payroll


class Command(BaseCommand):
    help = 'Importa até 50 maiores remunerações e seus detalhes. Sem período, busca o último mês disponível em até 12 meses.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int)
        parser.add_argument('--month', type=int)

    def handle(self, *args, **options):
        try:
            snapshot = sync_payroll(year=options['year'], month=options['month'])
        except Exception as exc:
            # Erros HTTP podem conter CPF na URL; não os reproduza no console.
            message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            raise CommandError(f'Sincronização de remunerações falhou: {message}') from None
        self.stdout.write(self.style.SUCCESS(
            f'Remunerações atualizadas: {len(snapshot.rows)} registros, {snapshot.month:02d}/{snapshot.year}.'
        ))
