"""Reúne o destino, que é texto livre na fonte, em lugares que uma pessoa reconhece.

A classificação é do portal, não da API: sem origem nem código de município, ela
se apoia nas grafias observadas. O texto original continua guardado e visível.
"""

import re
import unicodedata

from django.utils.text import slugify

RORAIMA = 'rr'
BRAZIL = 'br'
ABROAD = 'ex'
UNKNOWN = 'na'
SCOPES = {RORAIMA: 'Em Roraima', BRAZIL: 'Outros estados', ABROAD: 'Exterior', UNKNOWN: 'Destino não identificado'}
OTHER_BRAZIL = 'Outras cidades do Brasil'

# Grafias e erros de digitação recorrentes, vilas e abreviações usadas pelos órgãos.
MUNICIPALITIES = {
    'Alto Alegre': ('ALTO ALEGRE', 'ALTO ALGRE', 'ALTO ALREGRE'),
    'Amajari': ('AMAJARI', 'TEPEQUEM'),
    'Boa Vista': ('BOA VISTA', 'BOA VSITA', 'ZONA RURAL'),
    'Bonfim': ('BONFIM',),
    'Cantá': ('CANTA', 'CANTARR', 'VILA FELIX PINTO'),
    'Caracaraí': ('CARACARAI', 'CARACARI', 'CARACARA', 'NOVO PARAISO', 'CAICUBI', 'BAIXO RIO BRANCO'),
    'Caroebe': ('CAROEBE',),
    'Iracema': ('IRACEMA',),
    'Mucajaí': ('MUCAJAI',),
    'Normandia': ('NORMANDIA', 'NORMADIA'),
    'Pacaraima': ('PACARAIMA', 'PARACAIMA', 'PACRAIMA'),
    'Rorainópolis': (
        'RORAINOPOLIS', 'RORAINOPOLI', 'RORAINOPLIS', 'RORAINOPOLES', 'JUNDIA',
        'SANTA MARIA DO BOIACU', 'S.M DO BOIACU', 'BAIXO RIO BRANCO',
    ),
    'São João da Baliza': ('SAO JOAO DA BALIZA', 'SAO JOAO DO BALIZA', 'S. J. DA BALIZA', 'BALIZA'),
    'São Luiz': ('SAO LUIZ', 'SAO LUIS'),
    'Uiramutã': ('UIRAMUTA', 'UITAMUTA'),
}
ABBREVIATIONS = {
    'ALG': 'Alto Alegre', 'AMJ': 'Amajari', 'BOF': 'Bonfim', 'CAB': 'Caroebe', 'CTA': 'Cantá',
    'IRA': 'Iracema', 'MUC': 'Mucajaí', 'NOD': 'Normandia', 'PAC': 'Pacaraima', 'UTA': 'Uiramutã',
}
COUNTRIES = {
    'Chile': ('CHILE',),
    'China': ('CHINA',),
    'Colômbia': ('COLOMBIA',),
    'Espanha': ('ESPANHA', 'MADRID'),
    'Estados Unidos': ('EUA', 'ESTADOS UNIDOS', 'ORLANDO'),
    'França': ('FRANCA', 'PARIS'),
    'Guiana': ('GUIANA', 'GEORGETOWN', 'LETHEM', 'LETEHEM'),
    'Itália': ('ITALIA',),
    'Peru': ('PERU',),
    'Portugal': ('PORTUGAL', 'LISBOA'),
    'Uruguai': ('URUGUAI', 'MONTEVIDEO'),
}
BRAZILIAN_CITIES = {
    'BRASILIA': 'Brasília/DF', 'MANAUS': 'Manaus/AM', 'SAO PAULO': 'São Paulo/SP',
    'RIO DE JANEIRO': 'Rio de Janeiro/RJ', 'FORTALEZA': 'Fortaleza/CE', 'FOZ DO IGUACU': 'Foz do Iguaçu/PR',
    'CURITIBA': 'Curitiba/PR', 'JOAO PESSOA': 'João Pessoa/PB', 'BELEM': 'Belém/PA', 'CUIABA': 'Cuiabá/MT',
    'PALMAS': 'Palmas/TO', 'GOIANIA': 'Goiânia/GO', 'PORTO ALEGRE': 'Porto Alegre/RS',
    'BELO HORIZONTE': 'Belo Horizonte/MG', 'BLUMENAU': 'Blumenau/SC', 'TERESINA': 'Teresina/PI',
    'FLORIANOPOLIS': 'Florianópolis/SC', 'NATAL': 'Natal/RN', 'MACEIO': 'Maceió/AL',
    'CAMPO GRANDE': 'Campo Grande/MS', 'RECIFE': 'Recife/PE', 'PORTO VELHO': 'Porto Velho/RO',
    'SALVADOR': 'Salvador/BA', 'VITORIA': 'Vitória/ES', 'ARACAJU': 'Aracaju/SE', 'RIO BRANCO': 'Rio Branco/AC',
    'MACAPA': 'Macapá/AP', 'GRAMADO': 'Gramado/RS', 'ARACRUZ': 'Aracruz/ES', 'NOVA LIMA': 'Nova Lima/MG',
}
STATE_SUFFIX = re.compile(r'[-/\s](AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|SC|SP|SE|TO)\s*\.?$')


def fold(text):
    """Maiúsculas sem acento: compara grafias que a fonte e a busca escrevem de formas diferentes."""
    decomposed = unicodedata.normalize('NFKD', text or '')
    return ''.join(char for char in decomposed if not unicodedata.combining(char)).upper()


def _has(text, term):
    return re.search(rf'(?<![A-Z]){re.escape(term)}(?![A-Z])', text) is not None


def _matches(text, table):
    return sorted(name for name, terms in table.items() if any(_has(text, term) for term in terms))


def classify(destination):
    """Retorna (abrangência, nomes dos lugares). Uma viagem por três cidades conta nas três."""
    text = fold(destination).strip()
    # Sem esta troca, a região do Baixo Rio Branco, em Roraima, viraria a capital do Acre.
    cities = sorted(name for term, name in BRAZILIAN_CITIES.items() if _has(text.replace('BAIXO RIO BRANCO', ''), term))
    countries = [] if _has(text, 'NOVA LIMA') else _matches(text, COUNTRIES)
    if countries:
        return ABROAD, countries
    if cities:
        return BRAZIL, cities
    if STATE_SUFFIX.search(text):
        return BRAZIL, [OTHER_BRAZIL]
    places = _matches(text, MUNICIPALITIES)
    if not places:
        places = sorted({name for code, name in ABBREVIATIONS.items() if _has(text, code)})
    # Em roteiros como "BV - Uiramutã - BV", Boa Vista é a saída, não o destino.
    if len(places) > 1 and 'Boa Vista' in places:
        places.remove('Boa Vista')
    return (RORAIMA, places) if places else (UNKNOWN, [])


def place_slug(name):
    return slugify(name)
