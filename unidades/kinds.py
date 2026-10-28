"""Agrupa as unidades em tipos que o cidadão reconhece, a partir do nome oficial."""

# Ordem de exibição: do mais familiar ao mais técnico.
KINDS = {
    'secretarias': ('Secretarias e órgãos do governo', 'Áreas do Executivo que cuidam de saúde, educação, obras e outros serviços.'),
    'poderes': ('Poderes e órgãos de controle', 'Legislativo, Justiça, Ministério Público e órgãos que fiscalizam o governo.'),
    'seguranca': ('Segurança pública', 'Polícias e Corpo de Bombeiros.'),
    'autarquias': ('Institutos, fundações e agências', 'Entidades com administração própria para serviços específicos.'),
    'empresas': ('Empresas públicas', 'Empresas controladas pelo estado, como água e energia.'),
    'fundos': ('Fundos', 'Contas separadas, com destino definido em lei.'),
    'contas': ('Contas gerais do estado', 'Registros que não são órgãos, como o caixa central e as reservas.'),
    'outros': ('Outros', ''),
}

# A primeira regra que casar define o tipo. Fundos vêm antes porque seus nomes
# citam outros órgãos ("Fundo Especial do Ministério Público").
RULES = (
    ('fundos', ('fundo ',)),
    ('poderes', ('assembleia', 'tribunal', 'ministério público', 'defensoria', 'controladoria', 'ouvidoria')),
    ('secretarias', ('secretaria', 'procuradoria', 'casa civil', 'casa militar', 'governadoria', 'representação', 'cerimonial', 'comissão')),
    ('seguranca', ('polícia', 'bombeiros')),
    ('empresas', ('companhia', 'empresa ')),
    ('autarquias', ('instituto', 'fundação', 'agência', 'departamento', 'universidade', 'junta', 'consórcio')),
    ('contas', ('tesouro', 'operações especiais', 'reserva')),
)


def classify(name):
    lowered = f'{name.strip().lower()} '
    return next((kind for kind, words in RULES if any(word in lowered for word in words)), 'outros')


def group_units(units):
    groups = {slug: {'slug': slug, 'title': title, 'description': description, 'units': []}
              for slug, (title, description) in KINDS.items()}
    for unit in sorted(units, key=lambda unit: unit.name.strip().casefold()):
        groups[classify(unit.name)]['units'].append({
            'name': unit.name.strip(),
            'acronym': (unit.acronym or '').strip(' ,'),
        })
    return [group for group in groups.values() if group['units']]
