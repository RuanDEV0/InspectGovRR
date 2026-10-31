from django.core.management.base import BaseCommand, CommandError

from contratos.services import (
    DETAIL_LIMIT, describe_contracts, describe_details, sync_contract_details, sync_contracts,
)


class Command(BaseCommand):
    help = (
        'Importa os contratos com vigência no ano, agrega por fornecedor e por órgão '
        'e coleta aos poucos os aditivos e fiscais de cada contrato.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int)
        parser.add_argument(
            '--details-limit', type=int, default=DETAIL_LIMIT,
            help=f'Máximo de contratos com aditivos e fiscais consultados nesta execução (padrão {DETAIL_LIMIT}; 0 pula).',
        )

    def handle(self, *args, **options):
        try:
            snapshot = sync_contracts(year=options['year'])
        except Exception as exc:
            raise CommandError(f'Sincronização de contratos falhou: {type(exc).__name__}') from None
        self.stdout.write(self.style.SUCCESS(describe_contracts(snapshot)))
        if options['details_limit'] <= 0:
            return
        try:
            counts = sync_contract_details(snapshot.fiscal_year, limit=options['details_limit'])
        except Exception as exc:
            raise CommandError(f'Coleta de aditivos e fiscais interrompida: {type(exc).__name__}') from None
        self.stdout.write(self.style.SUCCESS(describe_details(counts)))
