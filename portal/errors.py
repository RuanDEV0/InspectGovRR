"""Mensagens públicas de erro; detalhes técnicos ficam nos logs protegidos."""

PUBLIC_ERRORS = {
    'ENTRADA-001': {'message': 'Selecione um ano e um mês válidos para consultar.'},
    'NAVEGACAO-404': {
        'title': 'Não encontramos esta página ou registro.',
        'message': 'Confira o endereço ou volte ao início para escolher outro assunto.',
    },
    'SISTEMA-500': {
        'title': 'Não foi possível abrir esta página agora.',
        'message': 'Tente novamente em alguns instantes.',
    },
}
