"""Recortes por unidade orçamentária conferidos na API Transparência RR em 2026."""

AREAS = {
    'saude': ('Saúde', {
        '20101': 'Secretaria de Estado da Saúde',
        '20601': 'Fundo Estadual de Saúde',
    }),
    'seguranca': ('Segurança pública', {
        '19101': 'Secretaria de Estado da Segurança Pública',
        '19102': 'Corpo de Bombeiros Militar do Estado de Roraima',
        '19103': 'Polícia Militar do Estado de Roraima',
        '19104': 'Academia de Polícia Integrada',
        '19105': 'Polícia Civil do Estado de Roraima',
        '19601': 'Fundo de Reequipamento do Corpo de Bombeiros Militar de Roraima',
        '19602': 'Fundo de Reaparelhamento e Aperfeiçoamento da Polícia Militar',
        '19603': 'Fundo de Modernização, Manutenção e Desenvolvimento da Polícia Civil',
        '19604': 'Fundo Estadual de Segurança Pública',
    }),
    'educacao': ('Educação', {
        '17101': 'Secretaria de Estado da Educação e Desporto',
        '17201': 'Universidade Estadual de Roraima',
        '17301': 'Instituto de Educação de Roraima',
        '17601': 'Fundeb',
    }),
}
AREA_YEAR = 2026

# Rótulos editoriais para algumas naturezas, conservando código e descrição da fonte.
NATURE_LABELS = {
    '31900100': 'Aposentadorias e inatividade militar',
    '31900400': 'Contratações temporárias',
    '31901100': 'Salários e parcelas fixas do pessoal civil',
    '31901200': 'Salários e parcelas fixas do pessoal militar',
    '31901300': 'Encargos pagos pelo órgão empregador',
    '31911300': 'Encargos pagos pelo órgão empregador',
    '33901400': 'Diárias de viagem',
    '33903000': 'Materiais de consumo',
    '33903300': 'Passagens e deslocamentos',
    '33903400': 'Despesas de pessoal com terceirização',
    '33903600': 'Serviços prestados por pessoas físicas',
    '33903700': 'Contratação de mão de obra',
    '33903900': 'Serviços prestados por empresas',
    '33909200': 'Despesas correntes de anos anteriores',
    '44905100': 'Obras e instalações',
    '44905200': 'Equipamentos e bens duráveis',
}
