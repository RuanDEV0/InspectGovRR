# Interface do portal

O portal usa templates Django, HTML semântico e CSS padrão, sem framework. O visual segue uma linguagem clara e “aérea”: superfícies em névoa esverdeada, tipografia Inter com espaçamento negativo, botões com gradiente e relevo, header translúcido e linhas de livro-caixa no topo das páginas. Os verdes vêm da logo.

O público é o cidadão comum. Todo termo técnico aparece traduzido, com o nome oficial ao lado para quem quiser procurar na fonte.

## Onde alterar cada parte

| Responsabilidade | Arquivo |
| --- | --- |
| Catálogo de módulos (nome cidadão, nome oficial, ícone, status) | `portal/modules.py` |
| Termos técnicos traduzidos e o caminho do dinheiro | `portal/glossary.py` |
| Moeda (`brl`, `brl_compact`), meses, data local | `portal/formatting.py` |
| Tags de template (`icon`, filtros `brl` e `brl_compact`) | `portal/templatetags/portal.py` |
| Variáveis disponíveis em todas as páginas | `portal/context_processors.py` |
| Cores, espaçamentos, raios, sombras, fonte | `static/css/tokens.css` |
| Base tipográfica, foco, container, `[hidden]` | `static/css/global.css` |
| Botões, cards, selos, filtros, rankings, glossário, CTA | `static/css/components/ui.css` |
| Hero das páginas | `static/css/components/page.css` |
| Header, rodapé, aviso da fonte | `static/css/components/header/`, `footer/`, `source-dialog.css` |
| Ícones (sprite SVG) | `static/img/icons.svg` |
| Comportamentos (aviso, menu, busca em listas) | `static/js/portal.js` |

## Criar um novo módulo

1. Adicione o módulo em `AVAILABLE` (ou mova-o de `UPCOMING`) em `portal/modules.py`, com `url_name`. Header, rodapé e Home passam a listá-lo; o cabeçalho da página ganha ícone, pergunta e nome oficial.
2. Na view, envie `glossary=terms(...)` com os termos que aparecem na página. Se faltar um termo, inclua-o em `portal/glossary.py`.
3. Envie os valores monetários crus (`Decimal` ou texto numérico) e formate no template com `amount.html` ou `|brl`.

```django
{% extends 'default.html' %}
{% block title %}Novo módulo · Transparência Cidadã{% endblock %}
{% block content %}
{% include 'components/ui/page-hero.html' with module=current_module description='O que o cidadão encontra aqui.' period=period_label updated_at=updated_at only %}
<div class="ui-container">
    <section class="ui-section ui-section--tight" aria-labelledby="results-title">
        {% include 'components/ui/section-heading.html' with heading_id='results-title' eyebrow='Destaques' title='Pergunta que a seção responde' only %}
        <!-- Conteúdo do módulo. -->
    </section>
    {% include 'components/ui/glossary-section.html' with terms=glossary only %}
</div>
{% endblock %}
```

O `<main id="conteudo">` fica em `default.html`; as páginas não o repetem.

## Templates disponíveis

Use `only` nos includes. Todo texto é escapado pelo Django; não passe HTML com `safe`.

| Include | Parâmetros |
| --- | --- |
| `page-hero.html` | `module`, `title`, `eyebrow`, `description`, `back_url`, `back_label`, `period`, `updated_at`, `status`. Renderiza o único `h1`. Sem `title`/`eyebrow`, usa os do módulo. |
| `metadata.html` | `period`, `updated_at`, `status`. Inclui o selo “Registros da API Transparência RR”, que reabre o aviso. |
| `section-heading.html` | `title`, `heading_id`, `eyebrow`, `description`, `aside`. Renderiza `h2`. |
| `amount.html` | `value`. Valor por extenso (“R$ 11,98 bilhões”) com o valor exato abaixo. |
| `link-button.html` | `href`, `label`, `variant` (`ghost`, `dark`), `external`, `arrow`. |
| `module-card.html` | `module`. Card de tema disponível. |
| `glossary.html` / `glossary-section.html` | `terms` (e `title` opcional na seção). |
| `empty-state.html` | `title`, `description`, `action_url`, `action_label`, `heading_level`. |
| `rank.html` | `position`. |

Ícones: `{% load portal %}{% icon 'arrecadacao' %}`. São decorativos (`aria-hidden`); o texto ao lado carrega o significado. Para criar um ícone, adicione um `<symbol>` em grade 24×24, só com traço, em `static/img/icons.svg`.

## Classes principais

- Superfícies: `ui-card` (`--link` para cards clicáveis), `ui-panel` (bloco em névoa), `ui-cta` (faixa escura de chamada).
- Ícones: `ui-icon-tile` (`--lg`, `--sm`, `--muted` para temas em preparação).
- Rótulos: `ui-eyebrow`, `ui-pill`, `ui-badge` (`--neutral`, `--warning`), `ui-official` (nome oficial).
- Seções: `ui-section` (`--tight` dentro das páginas de módulo), `ui-section-heading`, `ui-reading` + `ui-reading__aside`, `ui-reference`.
- Dados: `ui-amount`, `ui-rank-list`, `ui-rank-card`, `ui-rank-card__value`.
- Formulários: `ui-filters`, `ui-field` (`--wide`), `ui-search`, `ui-checkbox`.
- Diárias (`diarias/static/diarias/index.css`): `daily-ticket` (bilhete de uma viagem, nas listas), `daily-example` (a única viagem de exemplo no painel do lugar), `daily-map`, `daily-panel`, `daily-rows` e `daily-segments`. O mapa é SVG com links reais; `index.js` só evita recarregar a página. Os 15 municípios têm nomes visíveis no mapa, inclusive em tela estreita; os rótulos ficam acima das áreas e não capturam o clique. Malha em `diarias/map_data.py`, gerada do IBGE.
- Busca em listas sem recarregar: input com `data-filter-input="#lista"` e `data-filter-count="#contador"`; itens com `data-filter-item` e `data-filter-text`; grupos com `data-filter-group`.

## Aviso sobre a origem dos dados

`components/source-dialog.html` abre uma vez por visita (via `sessionStorage`) e explica que os registros financeiros vêm da API de consultas do Portal da Transparência do Governo de Roraima, abreviada na interface como “API Transparência RR”, enquanto o portal os organiza e calcula métricas indicadas nas páginas. Botões com `data-source-open` reabrem o aviso. O header mantém o link “Fonte: API Transparência RR” em todas as páginas. Sem JavaScript, o aviso não abre, mas o link continua visível.

## Acessibilidade e responsividade

- Alvos interativos com pelo menos 44 px, foco visível e títulos em sequência.
- Cor nunca é o único indicador: status sempre têm texto.
- Valores monetários com `tabular-nums`; valores grandes aparecem por extenso e também exatos.
- `prefers-reduced-motion` desliga as animações; `forced-colors` tem contornos de reserva.
- Largura máxima de 1200 px, com margens de 32 px (16 px no celular). Abaixo de 1020 px, o menu vira um botão.
- Ao mudar uma classe compartilhada, confira as páginas em 390 px e 1440 px, incluindo os estados vazios.
