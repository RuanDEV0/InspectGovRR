from .modules import API_DOCS_URL, AVAILABLE, OMBUDSMAN_URL, current_module


def portal(request):
    match = getattr(request, 'resolver_match', None)
    return {
        'portal_modules': AVAILABLE,
        'current_module': current_module(match.namespace if match else ''),
        'api_docs_url': API_DOCS_URL,
        'ombudsman_url': OMBUDSMAN_URL,
    }
