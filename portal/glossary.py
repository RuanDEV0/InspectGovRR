"""Termos técnicos traduzidos para linguagem simples, reutilizados pelas páginas."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    term: str
    plain: str
    explanation: str


TERMS = {
    'receita': Term(
        'Receita', 'Dinheiro que entra nos cofres públicos',
        'Inclui impostos como ICMS e IPVA, taxas, repasses do governo federal, convênios e rendimentos.',
    ),
    'tesouro': Term(
        'Tesouro do Estado', 'O caixa central do governo',
        'Recebe a maior parte dos impostos e distribui o dinheiro para os órgãos conforme o orçamento.',
    ),
    'unidade': Term(
        'Unidade orçamentária', 'Órgão ou fundo com orçamento próprio',
        'Secretarias, fundos, institutos, empresas públicas e os Poderes. Cada um recebe e gasta a sua parte do orçamento.',
    ),
    'fundo': Term(
        'Fundo', 'Uma conta separada, com destino definido em lei',
        'O dinheiro de um fundo só pode ser usado para a sua finalidade. O Fundo Estadual de Saúde, por exemplo, só paga despesas de saúde.',
    ),
    'credor': Term(
        'Credor', 'Quem tem dinheiro a receber do governo',
        'Empresa ou pessoa que vendeu um produto ou prestou um serviço ao estado.',
    ),
    'empenho': Term(
        'Empenho', 'A reserva do dinheiro',
        'Antes de comprar, o governo separa o valor no orçamento. O empenho ainda não é um pagamento.',
    ),
    'liquidacao': Term(
        'Liquidação', 'A conferência da entrega',
        'O governo confere se o produto ou serviço foi entregue como combinado. Só depois disso o pagamento pode ser feito.',
    ),
    'pagamento': Term(
        'Pagamento', 'O dinheiro sai da conta pública',
        'É a transferência ao credor depois da conferência. A conferência e o pagamento podem acontecer em datas diferentes.',
    ),
    'restos': Term(
        'Restos a pagar', 'Contas que ficaram para o ano seguinte',
        'Despesas reservadas em um ano e pagas apenas no ano seguinte.',
    ),
    'natureza': Term(
        'Natureza de despesa', 'O tipo de gasto',
        'Um código que indica em que o dinheiro foi usado. O código 3.3.90.39, por exemplo, reúne serviços prestados por empresas.',
    ),
    'exercicio': Term(
        'Exercício', 'O ano do orçamento',
        'O orçamento público vale de 1º de janeiro a 31 de dezembro.',
    ),
    'bruto': Term(
        'Remuneração bruta', 'O salário antes dos descontos',
        'Soma o salário-base, adicionais, gratificações e pagamentos eventuais, como férias e 13º.',
    ),
    'liquido': Term(
        'Remuneração líquida', 'O que cai na conta',
        'O valor que sobra depois de impostos, previdência e outros descontos.',
    ),
    'matricula': Term(
        'Matrícula', 'Cada vínculo de trabalho',
        'Uma pessoa pode ter mais de uma matrícula, por exemplo um professor que trabalha em duas redes. Isso, sozinho, não indica irregularidade.',
    ),
    'fiplan': Term(
        'Fiplan', 'O sistema financeiro do governo de Roraima',
        'É onde receitas e despesas do estado são registradas. A API pública de transparência entrega esses registros, e é dela que vêm todos os números deste portal.',
    ),
}


def terms(*slugs):
    return [TERMS[slug] for slug in slugs]


# O caminho de cada gasto público, do dinheiro que entra ao pagamento.
MONEY_PATH = (
    {'icon': 'arrecadacao', 'tone': 'green', 'title': 'Entra', 'term': TERMS['receita'],
     'text': 'O estado recebe impostos, taxas e repasses do governo federal.'},
    {'icon': 'reservado', 'tone': 'ink', 'title': 'É reservado', 'term': TERMS['empenho'],
     'text': 'Antes de comprar, o valor é separado no orçamento.'},
    {'icon': 'conferido', 'tone': 'teal', 'title': 'É conferido', 'term': TERMS['liquidacao'],
     'text': 'O governo confere se recebeu o que comprou.'},
    {'icon': 'pago', 'tone': 'blue', 'title': 'É pago', 'term': TERMS['pagamento'],
     'text': 'O dinheiro sai da conta pública para quem vendeu.'},
)
