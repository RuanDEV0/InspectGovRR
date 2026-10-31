from django.core.management.base import BaseCommand

from diarias.services import describe_dailies, local_year, sync_dailies


class Command(BaseCommand):
    help = 'Atualiza o conjunto de diárias de um exercício.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, default=local_year())

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(describe_dailies(sync_dailies(year=options['year']))))
