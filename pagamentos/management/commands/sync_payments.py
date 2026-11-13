from django.core.management.base import BaseCommand, CommandError

from pagamentos.services import PaymentSyncError, describe_payments, sync_payments


class Command(BaseCommand):
    help = 'Importa e confere os pagamentos do ano, mês a mês, antes de publicar o conjunto.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int)
        parser.add_argument('--month-end', type=int, help='Último mês do recorte a partir de janeiro.')

    def handle(self, *args, **options):
        try:
            snapshot = sync_payments(year=options['year'], month_end=options['month_end'])
        except PaymentSyncError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(describe_payments(snapshot)))
