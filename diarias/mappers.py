"""Valida cada registro de diária e calcula o resumo publicado com o snapshot.

Temas, lugares, somas e percentuais são do portal; os valores vêm da API. O CPF
entra aqui apenas para gerar o identificador público e nunca é devolvido.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import html
import re
from statistics import median

from django.utils.crypto import salted_hmac

from .destinations import ABROAD, BRAZIL, RORAIMA, SCOPES, UNKNOWN, classify, fold, place_slug

SEI_PREFIX = 'https://sei.rr.gov.br/'
FORMULA_TOLERANCE = Decimal('0.02')
TOP_ROLES = 5

OTHER_THEME = 'outros'
THEME_LABELS = {
    'eventos': 'Cursos, congressos e reuniões',
    'fiscalizacao': 'Fiscalização e auditoria',
    'atendimento': 'Atendimento à população',
    'seguranca': 'Escolta e segurança',
    'saude-educacao': 'Saúde e educação',
    'apoio': 'Transporte e apoio de equipes',
    'obras-ambiente': 'Obras, terras e meio ambiente',
    OTHER_THEME: 'Outros motivos',
}
# A ordem é a regra: um motivo fica no primeiro tema que combinar. Participação em
# evento vem antes para "congresso de fiscalização" não contar como fiscalização.
THEME_RULES = tuple((slug, re.compile(pattern)) for slug, pattern in (
    ('eventos', r'^(PARA )?PARTICIPA[A-Z]* .{0,60}(CONGRESSO|SEMINARIO|FORUM|EVENTO|ENCONTRO|CONFERENCIA|CURSO|OFICINA|FAIR|FEIRA)'),
    ('seguranca', r'ESCOLTA|PROTECAO D[OE]|SEGURANCA APROXIMADA|PRECURSORA|GOVERNADOR|AGENDA OFICIAL|AUTORIDADE'),
    ('seguranca', r'POLICIAMENTO|POLICIAL|OPERACAO|OSTENSIV|PATRULHA|SISTEMA PRISIONAL|PENITENCI|BOMBEIRO|SEGURANCA PUBLICA|COMANDOS'),
    ('atendimento', r'CESTA|BENEFICIARIOS|ASSISTENCIA SOCIAL|VULNERAB|CRAS\b|CREAS\b|PROGRAMA.*FAMILIA|CADUNICO|CADASTRO UNICO|VISITADOR|CRIANCA FELIZ|PRIMEIRA INFANCIA'),
    ('atendimento', r'ITINERANTE|MUTIRAO'),
    ('fiscalizacao', r'POSTO FISCAL|POSTOS FISCAIS|TRIBUT|ARRECADACAO|SEFAZ|FISCAIS, TECNICOS'),
    ('fiscalizacao', r'AGROPECUARI|ABATEDOURO|FRIGORIFICO|MOSCA|VACINACAO ANTI|ANIMAL|SANITARI[AO] VEGETAL|PRAGA|FEBRE AFTOSA|POSTOS DE VIGILANCIA|FITOSSANIT|INSPECAO PERMANENTE|PRODUTORES?|ATER\b|EXTENSAO RURAL'),
    ('atendimento', r'DIRECAO VEICULAR|EXAME PRATICO|DETRAN|HABILITACAO|TRANSITO|CNH\b|VISTORIA VEICULAR'),
    ('saude-educacao', r'SAUDE|HOSPITAL|VACIN|SUS\b|MEDIC|PACIENTE|EPIDEMI|ENFERM|MALARIA|DSEI|REGULACAO|UBS\b'),
    ('saude-educacao', r'ESCOLA|ENSINO|ESTUDANTE|PROFESSOR|PEDAGOG|EDUCACA|JOGOS ESCOLARES|ALUNOS|MERENDA|JERS\b'),
    ('obras-ambiente', r'AMBIENTAL|LICENCIAMENTO|GLEBA|FUNDIARI|GEORREFERENC|DESMATAMENTO|QUEIMADA|GARIMPO|REGULARIZACAO'),
    ('obras-ambiente', r'OBRA|ENGENHARIA|CONSTRUCAO|VICINA|PONTE|ESTRADA|ENERGIA|PAVIMENT|MEDICAO'),
    ('fiscalizacao', r'AUDITORIA|INSPECAO|FISCALIZACAO|FISCALIZAR|VISTORIA|VISTORIAR|DILIGENCIA|CORREICAO|CONTROLE EXTERNO'),
    ('atendimento', r'DEFENSORIA|AUDIENCIA|JURI\b|JUDICI|PROMOTORIA|PROCESSUAL|ATENDIMENTO JURIDICO|CARCERE|NUCLEO'),
    ('eventos', r'CURSO|TREINAMENTO|CAPACITACAO|CONGRESSO|SEMINARIO|ENCONTRO|REUNIAO|CONFERENCIA|EVENTO|FORUM|WORKSHOP|SIMPOSIO|FORMACAO|PARTICIPA|CONSELHO|FEIRA|VISITA TECNICA|BENCHMARK'),
    ('apoio', r'CONDUZIR|TRANSPORTA|MOTORISTA|APOIO|LOGISTIC|SUPORTE|ACOMPANHAR|ACOMPANHAMENTO|ENTREGA|DESLOCAMENTO|EQUIPE'),
))
# Exemplos em destaque não devem trazer nomes, propriedades particulares nem referências internas.
NOT_FOR_HIGHLIGHT = re.compile(
    r'SENHOR|\bSR\b|\bSRA\b|EXMO|EXCELENTISS|SERVIDOR(A|ES)?\s+[A-Z]{3,}|\bDRA?\.|GOVERNADOR'
    r'|SITIO|FAZENDA|CHACARA|PORTARIA|MEMORANDO|OFICIO|DESPACHO|\bN[O°º.]\s*\d|\bPROC\b|\d{5,}|\bSEI\b'
)
PROPER_NOUNS = (
    'Roraima', 'Boa Vista', 'Rorainópolis', 'Bonfim', 'Iracema', 'Alto Alegre', 'Uiramutã',
    'Pacaraima', 'Normandia', 'Caracaraí', 'Mucajaí', 'Amajari', 'Cantá', 'Caroebe', 'Brasília',
    'São Paulo', 'Manaus', 'Curitiba', 'Rio de Janeiro', 'Lethem',
)
ROLE_ALIASES = {'SD PM': 'Soldado PM', 'SOLDADO PM': 'Soldado PM', 'PROFESSORA': 'Professor', 'ENGENHEIRA CIVIL': 'Engenheiro civil'}


def amount(value, *, label='Valor de diária'):
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result) >= Decimal('1e14'):
            raise ValueError
        return result.quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label} inválido') from exc


def parse_date(value):
    if value in (None, ''):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Data de viagem inválida') from exc


def text(value):
    return str(value or '').strip()


def optional_amount(value):
    """Quantidade e valor da diária só explicam a conta: um valor ilegível vira "não informado"."""
    try:
        return amount(text(value).replace(',', '.') or None)
    except ValueError:
        return None


def clean_reason(value):
    """Limpa o motivo sem reescrevê-lo: entidades HTML, caracteres soltos e texto todo em maiúsculas."""
    reason = html.unescape(text(value)).replace('​', '').replace('¿', ' – ')
    reason = re.sub(r'[\x80-\x9f]', '', reason)
    reason = re.sub(r'\s+', ' ', reason).strip()
    letters = [char for char in reason if char.isalpha()]
    if letters and sum(char.isupper() for char in letters) / len(letters) > .8:
        reason = reason.lower()
        reason = reason[0].upper() + reason[1:]
        for noun in PROPER_NOUNS:
            reason = re.sub(rf'\b{noun}\b', noun, reason, flags=re.IGNORECASE)
        reason = re.sub(r'\brr\b', 'RR', reason)
    return reason


def classify_reason(reason):
    folded = fold(reason)
    for slug, rule in THEME_RULES:
        if rule.search(folded):
            return slug
    return OTHER_THEME


def status_of(paid, reversed_amount):
    if paid > 0:
        return 'paid'
    return 'reversed' if reversed_amount else 'pending'


def normalize(item, year):
    if not isinstance(item, dict) or item.get('cdExercicio') != year:
        raise ValueError('Registro de diária com exercício divergente')
    document = re.sub(r'\D', '', text(item.get('cpfCnpjCredor')))
    name = text(item.get('nomeCredor'))
    unit = text(item.get('cdUnidadeOrcamentaria'))
    agency = text(item.get('dsUnidadeOrcamentaria'))
    acronym = text(item.get('sigla'))
    paid = amount(item.get('totalPago'))
    if paid is None:
        raise ValueError('Total pago ausente na diária')
    committed = amount(item.get('valorEmpenho'))
    if len(document) == 14:
        # Lançamento em nome de uma instituição: entra no total, mas não descreve uma viagem.
        return {'kind': 'lump_sum', 'unit': unit, 'agency': agency, 'acronym': acronym, 'paid': paid, 'committed': committed}
    if len(document) != 11 or not name or not unit:
        raise ValueError('Identificação de diária ausente')
    start = parse_date(item.get('dataInicioViagem'))
    end = parse_date(item.get('dataRetornoViagem'))
    if start and end and end < start:
        raise ValueError('Período de viagem inválido')
    reversed_amount = amount(item.get('totalEstornado'))
    quantity = optional_amount(item.get('quantidadeDiarias'))
    daily_value = optional_amount(item.get('valorDiaria'))
    order_value = optional_amount(item.get('valrOsd'))
    destination = text(item.get('localidade'))
    scope, places = classify(destination)
    reason = clean_reason(item.get('motivo'))
    link = text(item.get('link'))
    return {
        'kind': 'trip',
        'commitment': text(item.get('numeroEmpenho')),
        'person_id': salted_hmac('daily-person', document).hexdigest()[:32],
        'name': name, 'role': text(item.get('cargo')),
        'unit': unit, 'agency': agency, 'acronym': acronym,
        'start': start, 'end': end,
        'destination': destination, 'scope': scope, 'places': [place_slug(place) for place in places],
        'reason': reason, 'theme': classify_reason(reason),
        'quantity': quantity, 'daily_value': daily_value,
        'formula_ok': (
            None not in (quantity, daily_value, order_value)
            and abs(quantity * daily_value - order_value) < FORMULA_TOLERANCE
        ),
        'committed': committed, 'paid': paid, 'reversed': reversed_amount,
        'status': status_of(paid, reversed_amount),
        'process': text(item.get('numrProcessoFormatado')),
        'sei_url': link if link.startswith(SEI_PREFIX) else '',
    }


def reconcile(trips, lump_sums, official):
    """Compara a soma por órgão com o total oficial; a fonte só informa os dez maiores."""
    if not isinstance(official, list) or not official:
        raise ValueError('Total oficial de diárias indisponível')
    totals = defaultdict(Decimal)
    for record in [*trips, *lump_sums]:
        totals[record['acronym']] += record['paid']
    for row in official:
        acronym = text(row.get('sigla'))
        if abs(totals[acronym] - amount(row.get('totalPago'))) > Decimal('0.01'):
            raise ValueError(f'Soma de diárias diverge do total oficial em {acronym}. Dados anteriores preservados.')
    return len(official)


def money(value):
    return str(value.quantize(Decimal('0.01')))


def share(part, whole):
    return round(float(part / whole * 100), 1) if whole else 0


def percentile_90(values):
    ordered = sorted(values)
    return ordered[int(.9 * len(ordered))] if ordered else None


def trip_card(trip):
    return {
        key: (str(value) if isinstance(value, (Decimal, date)) else value)
        for key, value in trip.items()
        if key in {'name', 'destination', 'acronym', 'role', 'start', 'end', 'quantity', 'daily_value', 'formula_ok',
                   'paid', 'reversed', 'status', 'process', 'sei_url', 'reason', 'theme'}
    }


def presentable(trip):
    return (
        trip['paid'] > 0 and trip['formula_ok'] and len(trip['reason']) > 30
        and trip['start'] is not None and not NOT_FOR_HIGHLIGHT.search(fold(trip['reason']))
    )


def closest_to_median(trips):
    """Prefere uma viagem típica e com processo aberto ao público, que a pessoa consiga conferir."""
    middle = median(trip['paid'] for trip in trips)
    return min(trips, key=lambda trip: (not trip['sei_url'], abs(trip['paid'] - middle), trip['commitment']))


def place_example(trips):
    candidates = [trip for trip in trips if presentable(trip)]
    if not candidates:
        return None
    usual = Counter(trip['theme'] for trip in candidates if trip['theme'] != OTHER_THEME).most_common(1)
    same_theme = [trip for trip in candidates if usual and trip['theme'] == usual[0][0]]
    return trip_card(closest_to_median(same_theme or candidates))


def ranked(pairs):
    return sorted(pairs, key=lambda pair: (-pair[1], pair[0]))


def place_summary(name, trips):
    by_agency, by_theme = defaultdict(Decimal), defaultdict(Decimal)
    for trip in trips:
        by_agency[trip['acronym'] or trip['agency']] += trip['paid']
        by_theme[trip['theme']] += trip['paid']
    paid = sum((trip['paid'] for trip in trips), Decimal('0'))
    return {
        'slug': place_slug(name), 'name': name, 'count': len(trips), 'paid': money(paid),
        'people': len({trip['person_id'] for trip in trips}),
        'agencies': [[key, money(value)] for key, value in ranked(by_agency.items())[:4]],
        'themes': [[THEME_LABELS[key], share(value, paid)] for key, value in ranked(by_theme.items())[:3]],
        'example': place_example(trips),
    }


def place_summaries(trips, names):
    places = {scope: defaultdict(list) for scope in (RORAIMA, BRAZIL, ABROAD)}
    for trip in trips:
        if trip['scope'] in places:
            for slug in trip['places']:
                places[trip['scope']][slug].append(trip)
    result = {}
    for scope, groups in places.items():
        cards = [place_summary(names[slug], group) for slug, group in groups.items()]
        key = 'count' if scope == RORAIMA else 'paid'
        cards.sort(key=lambda card: (-Decimal(card[key]), card['name']))
        result[scope] = cards
    return result


def scope_summary(trips, total_paid):
    rows = []
    for scope, label in SCOPES.items():
        group = [trip for trip in trips if trip['scope'] == scope]
        paid = sum((trip['paid'] for trip in group), Decimal('0'))
        values = [trip['daily_value'] for trip in group if trip['daily_value'] is not None]
        rows.append({
            'scope': scope, 'label': label, 'count': len(group), 'paid': money(paid),
            'count_share': share(Decimal(len(group)), Decimal(len(trips))), 'paid_share': share(paid, total_paid),
            'daily_median': money(median(values)) if values else None,
            'daily_p90': money(percentile_90(values)) if values else None,
        })
    return rows


def theme_summary(trips, total_paid):
    groups = defaultdict(lambda: [0, Decimal('0')])
    for trip in trips:
        groups[trip['theme']][0] += 1
        groups[trip['theme']][1] += trip['paid']
    rows = [
        {'slug': slug, 'label': THEME_LABELS[slug], 'count': count, 'paid': money(paid), 'share': share(paid, total_paid)}
        for slug, (count, paid) in groups.items()
    ]
    rows.sort(key=lambda row: (row['slug'] == OTHER_THEME, -Decimal(row['paid']), row['slug']))
    return rows


def agency_summary(trips, lump_sums):
    groups = defaultdict(lambda: {'paid': Decimal('0'), 'count': 0, 'people': set(), 'name': '', 'lump_sum': False})
    for trip in trips:
        group = groups[trip['acronym'] or trip['agency']]
        group['paid'] += trip['paid']
        group['count'] += 1
        group['people'].add(trip['person_id'])
        group['name'] = trip['agency']
    for lump_sum in lump_sums:
        group = groups[lump_sum['acronym'] or lump_sum['agency']]
        group['paid'] += lump_sum['paid']
        group['name'] = lump_sum['agency']
        group['lump_sum'] = True
    rows = [
        {'acronym': key, 'name': group['name'], 'paid': money(group['paid']), 'count': group['count'],
         'people': len(group['people']), 'lump_sum': group['lump_sum']}
        for key, group in groups.items()
    ]
    rows.sort(key=lambda row: (-Decimal(row['paid']), row['acronym']))
    return rows


def role_summary(trips):
    counts, spellings = Counter(), defaultdict(Counter)
    for trip in trips:
        original = re.split(r' - |,|\(', trip['role'])[0].strip()
        if not original:
            continue
        key = fold(original)
        alias = ROLE_ALIASES.get(key)
        key = fold(alias) if alias else key
        counts[key] += 1
        spellings[key][alias or original] += 1
    rows = []
    for key, count in counts.most_common(TOP_ROLES):
        # Prefere a grafia com acentos e minúsculas, quando a fonte tiver alguma.
        best = max(spellings[key].items(), key=lambda pair: (not pair[0].isupper(), pair[1]))[0]
        rows.append({'label': best.capitalize() if best.isupper() else best, 'count': count})
    return rows


def people_summary(trips, detailed_paid):
    paid_by_person = defaultdict(Decimal)
    for trip in trips:
        paid_by_person[trip['person_id']] += trip['paid']
    ordered = sorted(paid_by_person.values(), reverse=True)
    top_decile = sum(ordered[:len(ordered) // 10], Decimal('0'))
    return {
        'count': len(ordered),
        'median': money(median(ordered)) if ordered else None,
        'top_decile_share': share(top_decile, detailed_paid),
    }


def featured_trips(trips):
    """Três viagens que mostram a amplitude: meia diária, viagem típica e o maior valor."""
    candidates = [trip for trip in trips if presentable(trip)]
    if not candidates:
        return []
    half_day = [trip for trip in candidates if trip['scope'] == RORAIMA and trip['quantity'] == Decimal('0.50')]
    regular = [trip for trip in candidates if trip['scope'] == RORAIMA and trip['quantity'] and trip['quantity'] > 1]
    chosen = [closest_to_median(half_day) if half_day else None, closest_to_median(regular) if regular else None,
              max(candidates, key=lambda trip: (trip['paid'], trip['commitment']))]
    return [trip_card(trip) for trip in chosen if trip]


def aggregate(trips, lump_sums, *, reconciled):
    detailed_paid = sum((trip['paid'] for trip in trips), Decimal('0'))
    lump_paid = sum((lump_sum['paid'] for lump_sum in lump_sums), Decimal('0'))
    names = {}
    for trip in trips:
        names.update({place_slug(place): place for place in classify(trip['destination'])[1]})
    statuses = {}
    for status in ('paid', 'pending', 'reversed'):
        group = [trip for trip in trips if trip['status'] == status]
        statuses[status] = {'count': len(group), 'committed': money(sum((trip['committed'] or Decimal('0') for trip in group), Decimal('0')))}
    unknown = sum(trip['scope'] == UNKNOWN for trip in trips)
    return {
        'paid': money(detailed_paid + lump_paid), 'detailed_paid': money(detailed_paid), 'lump_paid': money(lump_paid),
        'lump_sums': [
            {'agency': lump_sum['agency'], 'acronym': lump_sum['acronym'], 'paid': money(lump_sum['paid'])}
            for lump_sum in lump_sums
        ],
        'trips': len(trips),
        'daily_count': money(sum((trip['quantity'] or Decimal('0') for trip in trips if trip['paid'] > 0), Decimal('0'))),
        'agencies': agency_summary(trips, lump_sums),
        'status': statuses,
        'scopes': scope_summary(trips, detailed_paid),
        'themes': theme_summary(trips, detailed_paid),
        'places': place_summaries(trips, names),
        'roles': role_summary(trips),
        'people': people_summary(trips, detailed_paid),
        'featured': featured_trips(trips),
        'quality': {
            'spellings': len({fold(trip['destination']).strip() for trip in trips}),
            'identified_share': share(Decimal(len(trips) - unknown), Decimal(len(trips))),
            'sei_links': sum(bool(trip['sei_url']) for trip in trips),
            'sei_share': share(Decimal(sum(bool(trip['sei_url']) for trip in trips)), Decimal(len(trips))),
            'formula_share': share(Decimal(sum(trip['formula_ok'] for trip in trips)), Decimal(len(trips))),
            'reconciled_agencies': reconciled,
        },
    }
