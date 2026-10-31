from decimal import Decimal
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from portal.formatting import br_date, brl, brl_compact, count, local_datetime
from portal.glossary import terms

from .destinations import ABROAD, BRAZIL, RORAIMA, UNKNOWN, fold
from .map_data import MUNICIPALITIES, VIEW_BOX
from .mappers import THEME_LABELS
from .models import DailySnapshot, DailyTrip

REGIONS = {'roraima': RORAIMA, 'brasil': BRAZIL, 'exterior': ABROAD}
REGION_LABELS = {'roraima': 'Em Roraima', 'brasil': 'Outros estados', 'exterior': 'Exterior'}
REGION_LIMITS = {RORAIMA: 15, BRAZIL: 14, ABROAD: 12}
TOP_AGENCIES = 6
TOP_PEOPLE = 5
RANKING_SIZE = 50
PAGE_SIZE = 20
INVALID_YEAR = 'Selecione um ano válido para consultar.'
INVALID_FILTER = 'Selecione um filtro válido para consultar.'
PEOPLE_ORDERS = {
    'valor': ('Maior valor pago', ('-total', 'name', 'person_id')),
    'viagens': ('Mais viagens', ('-trip_count', '-total', 'person_id')),
}
TRIP_ORDERS = {
    'recentes': ('Mais recentes', ('-start', '-paid', 'id')),
    'valor': ('Maior valor pago', ('-paid', '-start', 'id')),
}
GLOSSARY = ('diaria', 'exercicio', 'empenho', 'pagamento', 'estorno')


def percent(part, whole):
    return Decimal(part) / Decimal(whole) * 100 if whole else Decimal('0')


def bar(value):
    # Texto, não número: o locale pt-BR trocaria o ponto por vírgula e invalidaria o CSS.
    return f'{value:.1f}'


def select_year(request):
    years = list(DailySnapshot.objects.values_list('year', flat=True))
    year = years[0] if years else None
    if 'ano' in request.GET:
        try:
            year = int(request.GET['ano'])
        except ValueError:
            return years, None, None, INVALID_YEAR
        if not 2000 <= year <= 9999:
            return years, None, None, INVALID_YEAR
    snapshot = DailySnapshot.objects.filter(year=year).exclude(summary={}).first() if year else None
    return years, year, snapshot, ''


def present(trip, *, include_name=False):
    """Prepara uma viagem para o bilhete; o nome aparece só quando solicitado."""
    get = trip.get if isinstance(trip, dict) else lambda key: getattr(trip, key)
    start, end = br_date(get('start')), br_date(get('end'))
    if start and end:
        period = start if start == end else f'{start} a {end}'
    else:
        period = 'Datas não informadas'
    status = get('status')
    role = get('role')
    result = {
        'destination': get('destination'), 'acronym': get('acronym'), 'period': period,
        'role': role.capitalize() if role.isupper() else role,
        'quantity': get('quantity'), 'daily_value': get('daily_value'), 'formula_ok': get('formula_ok'),
        'paid': get('paid'), 'reversed': get('reversed'), 'process': get('process'), 'sei_url': get('sei_url'),
        'reason': get('reason'), 'theme': THEME_LABELS[get('theme')],
        'status_label': DailyTrip.Status(status).label, 'unpaid': status != DailyTrip.Status.PAID,
    }
    if include_name:
        result['name'] = get('name')
    return result


def map_scale(places):
    """Faixas proporcionais ao maior município, para um destino muito acima dos outros se destacar."""
    peak = max((place['count'] for place in places), default=0)
    limits = [int(peak * share) // 50 * 50 for share in (.3, .4, .6)]
    if not limits[0]:
        return [], lambda value: 1
    labels = [
        f'até {count(limits[0] - 1)}',
        f'{count(limits[0])} a {count(limits[1] - 1)}',
        f'{count(limits[1])} a {count(limits[2] - 1)}',
        f'{count(limits[2])} ou mais',
    ]
    legend = [{'level': level, 'label': label} for level, label in enumerate(labels, 1)]
    return legend, lambda value: 1 + sum(value >= limit for limit in limits)


def place_query(year, region, slug):
    return urlencode({'ano': year, 'regiao': region, 'lugar': slug})


def place_rows(places, measure, year, selected, region_of):
    peak = max((Decimal(place[measure]) for place in places), default=Decimal('0'))
    return [{
        **place,
        'url': f'?{place_query(year, region_of(place), place["slug"])}#lugares',
        'bar': bar(percent(place[measure], peak)),
        'selected': bool(selected) and place['slug'] == selected['slug'],
        'region_label': REGION_LABELS[region_of(place)],
    } for place in places]


def map_shapes(places, year, selected, level_of):
    by_slug = {place['slug']: place for place in places}
    shapes = []
    for slug, name, x, y, _width, path in MUNICIPALITIES:
        place = by_slug.get(slug)
        shapes.append({
            'slug': slug, 'name': name, 'x': x, 'y': y, 'path': path,
            'level': level_of(place['count']) if place else 0, 'count': place['count'] if place else 0,
            'url': f'?{place_query(year, "roraima", slug)}#lugares',
            'selected': bool(selected) and slug == selected['slug'],
        })
    # O selecionado vem por último para o contorno não ficar sob os vizinhos.
    return sorted(shapes, key=lambda shape: shape['selected'])


def scope_rows(summary):
    colored = {RORAIMA: 'rr', BRAZIL: 'br', ABROAD: 'ex', UNKNOWN: 'na'}
    return [{
        **row, 'tone': colored[row['scope']],
        'count_bar': bar(Decimal(str(row['count_share']))), 'paid_bar': bar(Decimal(str(row['paid_share']))),
        'count_label': round(row['count_share']) if row['count_share'] >= 8 else '',
        'paid_label': round(row['paid_share']) if row['paid_share'] >= 8 else '',
    } for row in summary['scopes']]


def theme_rows(summary, year):
    peak = max((Decimal(row['paid']) for row in summary['themes']), default=Decimal('0'))
    return [{
        **row, 'bar': bar(percent(row['paid'], peak)),
        'url': f'{reverse("diarias:trips")}?{urlencode({"ano": year, "tema": row["slug"]})}',
    } for row in summary['themes']]


def agency_rows(summary, year):
    agencies = summary['agencies']
    shown = agencies[:TOP_AGENCIES] + [row for row in agencies[TOP_AGENCIES:] if row['lump_sum']]
    peak = Decimal(agencies[0]['paid']) if agencies else Decimal('0')
    return [{
        **row, 'bar': bar(percent(row['paid'], peak)),
        'url': f'{reverse("diarias:trips")}?{urlencode({"ano": year, "orgao": row["acronym"]})}' if row['count'] else '',
    } for row in shown]


def ranking(year, *, agency='', order='valor'):
    trips = DailyTrip.objects.filter(year=year)
    if agency:
        trips = trips.filter(acronym=agency)
    return trips.values('person_id').annotate(
        name=Max('name'), agency=Max('acronym'), role=Max('role'), trip_count=Count('id'),
        total=Sum('paid'), diarias=Sum('quantity', filter=Q(paid__gt=0)),
    ).order_by(*PEOPLE_ORDERS[order][1])


def page_context(snapshot, year, years):
    return {
        'snapshot': snapshot, 'year': year, 'years': sorted(set(years) | ({year} if year else set()), reverse=True),
        'period_label': f'Exercício {year}' if year else '',
        'updated_at': local_datetime(snapshot.updated_at) if snapshot else '',
        'glossary': terms(*GLOSSARY),
    }


def index(request):
    years, year, snapshot, error = select_year(request)
    context = {**page_context(snapshot, year, years), 'error': error}
    if not snapshot:
        return render(request, 'diarias/index.html', context)

    summary = snapshot.summary
    places = summary['places']
    catalog = {place['slug']: (region, place) for region, scope in REGIONS.items() for place in places[scope]}
    region = request.GET.get('regiao', '')
    region = region if region in REGIONS else 'roraima'
    slug = request.GET.get('lugar', '')
    selected = None
    if slug in catalog:
        region, selected = catalog[slug]
    elif slug:
        context['error'] = 'Não encontramos esse lugar neste exercício. Escolha outro no mapa ou na lista.'
    scope = REGIONS[region]
    region_places = places[scope][:REGION_LIMITS[scope]]
    selected = selected or next(iter(region_places), None)

    query = request.GET.get('busca', '').strip()[:80]
    region_of = lambda place: catalog[place['slug']][0]
    if query:
        needle = fold(query)
        found = [place for _, place in catalog.values() if needle in fold(place['name'])]
        rows = place_rows(found, 'paid', year, selected, region_of)
    else:
        rows = place_rows(region_places, 'count' if scope == RORAIMA else 'paid', year, selected, region_of)
    legend, level_of = map_scale(places[RORAIMA])

    rows_by_scope = {row['scope']: row for row in scope_rows(summary)}
    leaving = rows_by_scope[BRAZIL]['count'] + rows_by_scope[ABROAD]['count']
    leaving_paid = rows_by_scope[BRAZIL]['paid_share'] + rows_by_scope[ABROAD]['paid_share']
    themes = theme_rows(summary, year)
    agencies = agency_rows(summary, year)
    featured = [present(trip, include_name=True) for trip in summary['featured']]
    context.update({
        'summary': summary,
        'hero_title': f'Órgãos de Roraima pagaram {brl_compact(summary["paid"])} em diárias em {year}'.replace('R$ ', 'R$ '),
        'region': region, 'regions': [
            {'key': key, 'label': REGION_LABELS[key], 'url': '?' + urlencode({'ano': year, 'regiao': key}) + '#lugares',
             'active': key == region and not query}
            for key in REGIONS
        ],
        'show_map': scope == RORAIMA and not query, 'view_box': ' '.join(map(str, VIEW_BOX)),
        'shapes': map_shapes(places[RORAIMA], year, selected, level_of), 'legend': legend,
        'place_rows': rows, 'query': query, 'count_measure': scope == RORAIMA and not query,
        'selected': selected, 'selected_region': REGION_LABELS[catalog[selected['slug']][0]] if selected else '',
        'selected_example': present(selected['example'], include_name=True) if selected and selected.get('example') else None,
        'selected_url': f'{reverse("diarias:trips")}?{urlencode({"ano": year, "lugar": selected["slug"]})}' if selected else '',
        'scopes': list(rows_by_scope.values()),
        'value_scopes': [rows_by_scope[key] for key in (RORAIMA, BRAZIL, ABROAD)],
        'split_title': (
            f'{round(leaving / summary["trips"] * 100) if summary["trips"] else 0} de cada 100 viagens '
            f'saem de Roraima e levam {round(leaving_paid)}% do dinheiro'
        ),
        'themes': themes,
        'top_theme_title': f'{themes[0]["label"]} são o maior motivo: {brl_compact(themes[0]["paid"])}',
        'agencies': agencies,
        'top_agency_title': f'{agencies[0]["acronym"]} lidera, com {brl_compact(agencies[0]["paid"])}',
        'featured': featured,
        'featured_title': (
            f'Três viagens reais, de {brl(featured[0]["paid"])} a {brl(featured[-1]["paid"])}' if len(featured) > 1 else ''
        ),
        'people_description': (
            f'Metade das pessoas recebeu até {brl(summary["people"]["median"])} no ano. Os 10% que mais '
            f'receberam concentram {summary["people"]["top_decile_share"]:.0f}% do valor detalhado.'
        ),
        'top_people': ranking(year)[:TOP_PEOPLE],
    })
    return render(request, 'diarias/index.html', context)


def trips(request):
    years, year, snapshot, error = select_year(request)
    context = {**page_context(snapshot, year, years), 'error': error}
    if not snapshot:
        return render(request, 'diarias/trips.html', context)
    summary = snapshot.summary
    names = {place['slug']: place['name'] for scope in summary['places'].values() for place in scope}
    agencies = [row for row in summary['agencies'] if row['count']]
    place = request.GET.get('lugar', '').strip()
    region = request.GET.get('regiao', '').strip()
    theme = request.GET.get('tema', '').strip()
    agency = request.GET.get('orgao', '').strip()
    order = request.GET.get('ordem', 'recentes')
    invalid = (
        (place and place not in names) or (region and region not in REGIONS) or (theme and theme not in THEME_LABELS)
        or (agency and agency not in {row['acronym'] for row in agencies}) or order not in TRIP_ORDERS
    )
    if invalid:
        context['error'] = INVALID_FILTER
        place, region, theme, agency, order = '', '', '', '', 'recentes'
    rows = DailyTrip.objects.filter(year=year)
    title = 'Todas as viagens'
    if place:
        rows = rows.filter(places__contains=[place])
        title = f'Viagens para {names[place]}'
    if region:
        rows = rows.filter(scope=REGIONS[region])
        title = f'Viagens: {REGION_LABELS[region].lower()}'
    if theme:
        rows = rows.filter(theme=theme)
    if agency:
        rows = rows.filter(acronym=agency)
    totals = rows.aggregate(total=Sum('paid'), people=Count('person_id', distinct=True), trips=Count('id'))
    page = Paginator(rows.order_by(*TRIP_ORDERS[order][1]), PAGE_SIZE).get_page(request.GET.get('pagina'))
    kept = {'ano': year, 'lugar': place, 'regiao': region, 'tema': theme, 'orgao': agency, 'ordem': order}
    query = urlencode({key: value for key, value in kept.items() if value})
    context.update({
        'title': title, 'place': place, 'region': region, 'theme': theme, 'agency': agency, 'order': order,
        'themes': THEME_LABELS.items(), 'agency_options': sorted(agencies, key=lambda row: row['acronym']),
        'orders': [(key, label) for key, (label, _) in TRIP_ORDERS.items()],
        'totals': totals, 'page': page, 'tickets': [present(trip, include_name=True) for trip in page.object_list], 'query': query,
        'filtered': bool(theme or agency or order != 'recentes'),
    })
    return render(request, 'diarias/trips.html', context)


def people(request):
    years, year, snapshot, error = select_year(request)
    context = {**page_context(snapshot, year, years), 'error': error}
    if not snapshot:
        return render(request, 'diarias/people.html', context)
    agencies = [row for row in snapshot.summary['agencies'] if row['count']]
    agency = request.GET.get('orgao', '').strip()
    order = request.GET.get('ordem', 'valor')
    if (agency and agency not in {row['acronym'] for row in agencies}) or order not in PEOPLE_ORDERS:
        context['error'] = INVALID_FILTER
        agency, order = '', 'valor'
    rows = ranking(year, agency=agency, order=order)
    context.update({
        'rows': rows[:RANKING_SIZE], 'total_count': rows.count(), 'agency': agency, 'order': order,
        'agency_options': sorted(agencies, key=lambda row: row['acronym']),
        'orders': [(key, label) for key, (label, _) in PEOPLE_ORDERS.items()],
        'filtered': bool(agency or order != 'valor'),
    })
    return render(request, 'diarias/people.html', context)


def detail(request, year, person_id):
    snapshot = get_object_or_404(DailySnapshot, year=year)
    rows = list(DailyTrip.objects.filter(year=year, person_id=person_id).order_by('-start', '-paid', 'id'))
    if not rows:
        raise Http404('Pessoa não encontrada neste exercício.')
    response = render(request, 'diarias/detail.html', {
        **page_context(snapshot, year, [year]), 'person': rows[0], 'tickets': [present(trip) for trip in rows],
        'total': sum((row.paid for row in rows), Decimal('0')),
        'diarias': sum((row.quantity or Decimal('0') for row in rows if row.paid > 0), Decimal('0')),
        'back_url': reverse('diarias:people') + '?' + urlencode({'ano': year}),
    })
    # Ficha individual: a consulta é pública, mas buscadores não precisam indexar pessoas por nome.
    response['X-Robots-Tag'] = 'noindex'
    return response
