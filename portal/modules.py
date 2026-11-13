"""Catálogo único dos módulos: nome cidadão, termo oficial, ícone e status.

Header, rodapé, Home e cabeçalho das páginas leem daqui. Todo módulo pertence a
um grupo do caminho do dinheiro (``GROUPS``). Para publicar um tema em
preparação, mova-o para AVAILABLE e informe ``url_name``.
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
    group: str = ''  # chave de GROUPS

    @property
    def namespace(self):
        return self.url_name.split(':')[0]


@dataclass(frozen=True)
class Group:
    key: str
    title: str
    description: str
    icon: str
    tone: str


# Agrupamento editorial do portal, na ordem em que o dinheiro anda.
GROUPS = (
    Group('entra', 'O dinheiro entra', 'Impostos, taxas e repasses que chegam aos cofres do estado.', 'arrecadacao', 'green'),
    Group('sai', 'O dinheiro sai', 'Todo gasto é reservado, conferido e só então pago.', 'pago', 'blue'),
    Group('recebe', 'Quem recebe', 'Servidores, empresas e outras pessoas que recebem dinheiro público.', 'fornecedor', 'teal'),
    Group('administra', 'Quem administra', 'Os órgãos, os Poderes e o patrimônio por trás dos números.', 'orgaos', 'ink'),
)

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
        group='entra',
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
        group='recebe',
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
        group='recebe',
    ),
    Module(
        title='Viagens a trabalho', official='Diárias',
        question='Para onde vão as viagens pagas pelo estado?',
        description='Escolha um lugar no mapa e veja quem foi, para quê e quanto custou.',
        icon='diarias', tone='green', nav_label='Diárias', url_name='diarias:index',
        group='recebe',
    ),
    Module(
        title='Pagamentos do estado', official='Pagamento',
        question='Para onde foi o dinheiro público?',
        description='Compare saúde, segurança e educação: quanto foi pago, quem mais recebeu e os maiores pagamentos.',
        icon='pago', tone='blue', nav_label='Pagamentos', url_name='pagamentos:index',
        group='sai',
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
        group='administra',
    ),
)

UPCOMING = (
    Module('Impostos e taxas arrecadados', 'Arrecadação', 'Detalhe do que o estado recebe, tributo por tributo.', 'impostos', group='entra'),
    Module('Dinheiro reservado para gastos', 'Empenhos', 'O primeiro passo de toda despesa: o valor é separado no orçamento.', 'reservado', group='sai'),
    Module('Serviços entregues e conferidos', 'Liquidação', 'Quando o governo confirma que recebeu o produto ou o serviço.', 'conferido', group='sai'),
    Module('Contas para o ano seguinte', 'Restos a pagar', 'Despesas de um ano que ficaram para ser pagas depois.', 'ano-seguinte', group='sai'),
    Module('Em que o dinheiro é gasto', 'Tipos de despesa', 'Pessoal, obras, materiais, serviços e outras áreas.', 'tipos-despesa', group='sai'),
    Module('Dia a dia ou investimento', 'Categorias econômicas', 'Separa a manutenção da máquina pública dos investimentos.', 'categorias', group='sai'),
    Module('Gastos por fornecedor', 'Despesas por credor', 'Quanto cada empresa recebeu, em todos os tipos de gasto.', 'fornecedor', group='recebe'),
    Module('Tipos de contrato', 'Tipos de contrato', 'Como os contratos são classificados.', 'tipos-contrato', group='recebe'),
    Module('Como o governo escolhe quem vende', 'Modalidades de licitação', 'Pregão, concorrência e outras formas de compra.', 'licitacao', group='recebe'),
    Module('Dinheiro repassado aos Poderes', 'Repasse de poderes', 'Quanto vai para Assembleia, Justiça, Ministério Público e outros.', 'repasse', group='administra'),
    Module('Bens do estado', 'Patrimônio', 'Prédios, veículos e equipamentos públicos.', 'patrimonio', group='administra'),
    Module('Cargos e órgãos principais', 'Principais cargos e órgãos', 'Quem ocupa os principais postos da administração.', 'cargos', group='administra'),
)


def grouped():
    """Grupos na ordem do caminho, cada um com seus temas disponíveis e em preparação."""
    return [
        {
            'group': group,
            'available': [module for module in AVAILABLE if module.group == group.key],
            'upcoming': [module for module in UPCOMING if module.group == group.key],
        }
        for group in GROUPS
    ]


def current_module(namespace):
    return next((module for module in AVAILABLE if module.namespace == namespace), None)
