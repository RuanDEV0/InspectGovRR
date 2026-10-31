# Origem dos dados, dicionário e privacidade

## Caminho dos dados

O [README](../README.md#como-o-site-funciona) descreve a arquitetura. Em resumo: `integrations/fiplan_api/client.py` autentica e consulta a API Fiplan; comandos de sincronização validam e persistem os resultados no PostgreSQL; as páginas públicas leem o banco local. `integrations` não expõe rota HTTP pública. A data de `updated_at` indica quando o portal gravou o snapshot, não quando o governo criou cada registro.

| Conjunto | Origem consultada no cliente | Persistência e recorte atual | Transformação local |
| --- | --- | --- | --- |
| Unidades | `/api/v1/unidades-orcamentarias` | `unidades.Unit`; código, nome e sigla. | Agrupamento por palavras do nome em `unidades/kinds.py`; tipo é classificação do portal, não campo oficial. |
| Receita | `/api/v1/receita-arrecadada/top-valor-total-uo` | `RevenueSnapshot`; ano corrente, janeiro até o mês atual, até 5 unidades. | Ordenação, formatação monetária, barra proporcional e participação dentro **dessas cinco unidades**. Não é participação na receita total do estado. |
| Remunerações | `/api/v1/remuneracoes/rankingTotalBruto` e `/api/v1/remuneracoes` | `PayrollSnapshot`; até 50 posições do período disponível e seus detalhes. | Identificador público HMAC, ordenação e comparação aproximada com salário mínimo de referência **externa**, citada na tela. CPF serve à consulta da API e não entra no snapshot. |
| Contratos | `/api/v1/contratos/json`, `/api/v1/contratos`, `/api/v1/contratos/totais-contratos-pagos-por-ano` | `ContractSnapshot` e `Contract`; contratos com vigência no ano, com exportação conferida pela contagem paginada. | Agrupamentos, somas, percentuais e indicação de prazo; métricas do portal, sem inferência de irregularidade. |
| Aditivos e fiscais | `/api/v1/aditivo-contratos/termo-aditivo/{id}` e `/api/v1/fiscais-contrato/{id}` | `ContractDetail`; coleta gradual, até 1.000 contratos por ciclo. | Normalização; detalhe ainda não coletado não é ausência de fiscal ou aditivo. |
| Credores | `/api/v1/execucao-orcamentaria/estatisticas-por-credor/` | `CreditorSnapshot`; por unidade, exercício e natureza configurada. | Vínculo com unidade e execução. `Credor` é tabela legada preservada. |
| Diárias | `/api/v1/diarias/json` | `Daily`; coleta desativada por padrão. | Exige validação de identificador estável antes de ativação. O modelo ainda contém `recipient_cpf`; revisar necessidade, retenção e exposição antes de publicar. |

**Dicionário mínimo:** `exercício` é o ano do orçamento; `competência` é o mês/ano da folha; `unidade` é um órgão ou fundo com código na API; `snapshot` é a cópia local de um recorte consultado; `coleta` é a execução que busca, valida e salva; `atualizado em` é a gravação local. Para termos de cidadania, use `portal/glossary.py`. Ao adicionar campo, documente nome na API, significado, tipo/unidade, transformação, armazenamento, exposição, período e tratamento de nulos.

## Regras de proveniência

- Preserve o valor e o significado de cada campo. Arredondamento e formato de moeda precisam ser explícitos; um valor abreviado deve ter o valor exato acessível quando pertinente.
- Uma associação entre conjuntos só pode usar identificador confiável da fonte. Coincidência de nome não comprova que duas pessoas, unidades ou empresas são a mesma entidade.
- Agregações precisam declarar universo, filtro, período, denominador e fórmula. Uma comparação com fonte externa, como salário mínimo, deve nomear e ligar essa outra fonte.
- Não escreva no texto público que “todos os números vêm exclusivamente da API” se a tela contém números calculados localmente ou referência externa.
- A API pode corrigir seus registros. Mantenha visível a data do conjunto, permita nova sincronização e não atribua ao governo uma alteração feita pela apresentação do portal.

## LGPD: critérios para revisão de cada conjunto

Dados acessíveis ao público **continuam sujeitos à LGPD** quando identificam pessoa natural. A origem pública não dispensa avaliar finalidade, base legal, necessidade, transparência, segurança e direitos dos titulares. A hipótese legal para cada tratamento e o papel do projeto como agente de tratamento devem ser definidos antes de ampliar coleta ou publicação; este documento não declara conformidade jurídica concluída.

1. **Inventarie** os campos pessoais recebidos, armazenados, exibidos, usados temporariamente e registrados em logs, inclusive nomes, CPF, matrícula e identificadores derivados.
2. **Justifique** por que cada campo é necessário à finalidade de facilitar a consulta pública. Minimize dados em snapshots, URLs, logs, erros, caches e backups. CPF em claro não deve ser publicado; máscara ou HMAC também exigem avaliação porque podem permitir associação a uma pessoa.
3. **Defina e registre** hipótese legal, retenção, acesso, descarte, responsável pelo tratamento e canal para solicitações/correções. Conferir o aviso de privacidade antes de publicação é uma pendência de produto e de revisão jurídica.
4. **Proteja** segredos, banco e tráfego. Não grave token, senha, CPF nem URL de erro que contenha identificador pessoal. Teste os caminhos de exceção, comandos e scheduler.
5. **Reavalie** qualquer cruzamento de bases, perfil ou destaque individual. Publicidade na fonte original não autoriza automaticamente um uso novo mais intrusivo.

### Pontos encontrados no estado atual

- A folha evita guardar CPF no `PayrollSnapshot`; a consulta por CPF usa esse dado em memória. Nome, órgão, remuneração e detalhes publicados ainda são dados pessoais e precisam de finalidade e política de retenção documentadas.
- `Daily.recipient_cpf` existe no modelo legado, embora a importação atual não preencha esse campo e diárias estejam desligadas por padrão. Antes de ligar a coleta, decidir se o campo deve sequer existir no banco.
- `SyncRun.error_message` passou a registrar apenas etapa e classe da exceção; scheduler e comandos de coleta também não imprimem o texto bruto da falha. Novos caminhos de erro precisam manter essa proteção, inclusive quando a API mudar.
- O aviso de origem da interface deve explicar que há cálculos do portal e uma comparação com salário mínimo de fonte adicional; a API Fiplan continua sendo a origem dos registros financeiros.

## Fontes normativas e orientação

- [Lei nº 13.709/2018, texto compilado (LGPD)](https://www.gov.br/mj/pt-br/assuntos/sua-protecao/sedigi/Lei13709.pdf), especialmente arts. 5º a 7º, 9º, 18 e 46.
- [Perguntas frequentes da ANPD](https://www.gov.br/anpd/pt-br/acesso-a-informacao/perguntas-frequentes/perguntas-frequentes), sobre dados pessoais e dados de acesso público.
- [Guia da ANPD sobre tratamento pelo poder público](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia_orientativo_tratamento_de_dados_pessoais_pelo_poder_publico). A atuação deste portal independente deve ser avaliada segundo seu próprio papel, não presumida como atuação do poder público.
