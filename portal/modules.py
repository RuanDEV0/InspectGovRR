"""Catálogo único dos módulos: nome cidadão, termo oficial, ícone e status.

Header, rodapé, Home e cabeçalho das páginas leem daqui. Para publicar um tema
em preparação, mova-o para AVAILABLE e informe ``url_name``.
"""

from dataclasses import dataclass

API_DOCS_URL = 'https://api2.transparencia.rr.gov.br/transparencia/swagger-ui/#/'
OMBUDSMAN_URL = 'https://ouvidoria.rr.gov.br/'


@dataclass(frozen=True)
class Module:
    title: str
    official: str
    description: str
    icon: str
    nav_label: str = ''
    question: str = ''
    url_name: str = ''
    tone: str = 'muted'  # cor do ícone: green, blue, teal, ink; em preparação usa muted

    @property
    def namespace(self):
        return self.url_name.split(':')[0]


AVAILABLE = (
    Module(
        title='Quanto o estado arrecada',
        official='Receita arrecadada',
        question='Quanto dinheiro entra?',
        description='Veja quais órgãos e fundos mais recebem recursos: impostos, taxas e repasses.',
        icon='arrecadacao',
        tone='green',
        nav_label='Arrecadação',
        url_name='receita_arrecadada:index',
    ),
    Module(
        title='Para quem o estado paga',
        official='Execução orçamentária',
        question='Quem recebe do governo?',
        description='Conheça as empresas e pessoas que mais receberam pagamentos do estado.',
        icon='pagamentos',
        tone='blue',
        nav_label='Pagamentos',
        url_name='integrations:get_list_credors_by_total_pago',
    ),
    Module(
        title='Salários do serviço público',
        official='Remunerações',
        question='Quanto ganham os servidores?',
        description='Compare os maiores salários do mês e entenda como cada valor é formado.',
        icon='salarios',
        tone='teal',
        nav_label='Salários',
        url_name='remuneracoes:index',
    ),
    Module(
        title='Contratos do governo',
        official='Contratos e aditivos',
        question='Com quem o governo fecha negócio?',
        description='Veja as empresas com mais contratos, quem fica com a maior parte de cada órgão e as mudanças feitas depois da assinatura.',
        icon='contrato',
        tone='blue',
        nav_label='Contratos',
        url_name='contratos:index',
    ),
    Module(
        title='Órgãos do governo',
        official='Unidades orçamentárias',
        question='Quem administra o dinheiro?',
        description='Secretarias, fundos, empresas e poderes que aparecem nas consultas.',
        icon='orgaos',
        tone='ink',
        nav_label='Órgãos',
        url_name='unidades:list',
    ),
)

UPCOMING = (
    ('Como o dinheiro é gasto', (
        Module('Dinheiro reservado para gastos', 'Empenhos', 'O primeiro passo de toda despesa: o valor é separado no orçamento.', 'reservado'),
        Module('Serviços entregues e conferidos', 'Liquidação', 'Quando o governo confirma que recebeu o produto ou o serviço.', 'conferido'),
        Module('Pagamentos realizados', 'Pagamento', 'O dinheiro que de fato saiu dos cofres públicos.', 'pago'),
        Module('Contas para o ano seguinte', 'Restos a pagar', 'Despesas de um ano que ficaram para ser pagas depois.', 'ano-seguinte'),
        Module('Gastos por fornecedor', 'Despesas por credor', 'Quanto cada empresa recebeu, em todos os tipos de gasto.', 'fornecedor'),
        Module('Em que o dinheiro é gasto', 'Tipos de despesa', 'Pessoal, obras, materiais, serviços e outras áreas.', 'tipos-despesa'),
        Module('Dia a dia ou investimento', 'Categorias econômicas', 'Separa a manutenção da máquina pública dos investimentos.', 'categorias'),
        Module('Viagens a trabalho', 'Diárias', 'Valores pagos a servidores em viagens oficiais.', 'diarias'),
    )),
    ('Contratos e compras', (
        Module('Tipos de contrato', 'Tipos de contrato', 'Como os contratos são classificados.', 'tipos-contrato'),
        Module('Como o governo escolhe quem vende', 'Modalidades de licitação', 'Pregão, concorrência e outras formas de compra.', 'licitacao'),
    )),
    ('Arrecadação e estrutura', (
        Module('Impostos e taxas arrecadados', 'Arrecadação', 'Detalhe do que o estado recebe, tributo por tributo.', 'impostos'),
        Module('Dinheiro repassado aos Poderes', 'Repasse de poderes', 'Quanto vai para Assembleia, Justiça, Ministério Público e outros.', 'repasse'),
        Module('Bens do estado', 'Patrimônio', 'Prédios, veículos e equipamentos públicos.', 'patrimonio'),
        Module('Cargos e órgãos principais', 'Principais cargos e órgãos', 'Quem ocupa os principais postos da administração.', 'cargos'),
    )),
)

UPCOMING_COUNT = sum(len(modules) for _, modules in UPCOMING)


def current_module(namespace):
    return next((module for module in AVAILABLE if module.namespace == namespace), None)
