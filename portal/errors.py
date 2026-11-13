"""Mensagens públicas de erro; detalhes técnicos ficam nos logs protegidos."""

PUBLIC_ERRORS = {
    'ENTRADA-001': {'message': 'Selecione um ano e um mês válidos para consultar.'},
    'PAGAMENTOS-FILTRO': {'message': 'Escolha um ano, mês, órgão ou tipo de despesa disponível.'},
    'DADOS-001': {'message': 'Ainda não há dados importados para este período.'},
    'DADOS-002': {'message': 'Não há registros neste recorte dos dados importados.'},
    'DADOS-003': {'message': 'A última atualização não foi concluída. Você está vendo os dados de'},
    'NAVEGACAO-404': {
        'title': 'Não encontramos esta página ou registro.',
        'message': 'Confira o endereço ou volte ao início para escolher outro assunto.',
    },
    'SISTEMA-500': {
        'title': 'Não foi possível abrir esta página agora.',
        'message': 'Tente novamente em alguns instantes.',
    },
}
