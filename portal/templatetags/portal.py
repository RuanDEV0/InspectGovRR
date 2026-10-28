from django import template
from django.templatetags.static import static
from django.utils.html import format_html

from portal import formatting

register = template.Library()
register.filter('brl', formatting.brl)
register.filter('brl_compact', formatting.brl_compact)


@register.simple_tag
def icon(name, css_class='', tone=''):
    """Ícone decorativo do sprite; o texto ao lado carrega o significado.

    Com `tone`, vira um ícone de destaque em duas cores (classe ui-glyph).
    """
    if tone:
        css_class = f'ui-glyph tone-{tone} {css_class}'.strip()
    return format_html(
        '<svg class="ui-icon {}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        css_class, static('img/icons.svg'), name,
    )
