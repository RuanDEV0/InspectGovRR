# Engenharia, erros e operação

## Arquitetura e estrutura

O diagrama e os comandos de execução estão no [README](../README.md#como-o-site-funciona). A regra de dependência é: `integrations/fiplan_api` só faz HTTP; os serviços e mappers de cada módulo validam e publicam dados; modelos persistem; views consultam o banco e montam contexto; templates apresentam. A página pública não chama a API externa. Código compartilhado de formatação, glossário e componentes fica em `portal/`, `templates/components/` e `static/`.

Ao criar um módulo, mantenha URLs, view, serviço, mapper, modelo, template e testes no próprio app quando fizer sentido. Evite mover regras específicas para `integrations` ou duplicar formatação e mensagens. `docs/design-system.md` define a composição da interface.

## Padrão de código

- Python: quatro espaços, sem tabs; nomes `snake_case` para funções/variáveis e `PascalCase` para classes; imports em grupos (biblioteca padrão, terceiros, projeto); linhas e funções curtas quando isso melhorar a leitura. Aplique o mesmo estilo ao arquivo que tocar, sem reformatar módulos alheios sem necessidade.
- Templates: HTML semântico, indentação consistente, componentes reutilizáveis e escape padrão do Django. Não use `safe` em texto da API. CSS compartilhado usa os tokens existentes; JS deve ser progressivo e pequeno.
- Funções devem ter uma responsabilidade clara. Extraia código compartilhado quando duas partes tiverem a mesma regra, não apenas o mesmo formato superficial. Prefira consultas em lote e `select_related`/`prefetch_related` quando evitarem N+1; meça antes de introduzir cache ou abstração pesada.
- Para valores monetários, use `Decimal` e preserve a unidade e o período. Controle ordenação, empates e arredondamento. Não trate `None`, string vazia e zero como equivalentes sem justificativa da fonte.
- Para sincronização, valide a resposta completa antes de substituir um snapshot; use transação para publicação atômica e preserve o último conjunto válido em falha. Limite paginação e tamanho de lotes, com critério de parada claro.

## Comentários e docstrings

Um comentário deve registrar uma **razão que o código não mostra**, como limitação da API, decisão de privacidade, invariante de integridade ou custo de uma operação. Não narre a próxima linha. Em arquivo essencial, um breve docstring inicial pode explicar sua responsabilidade e sua fronteira. Docstrings de função só são úteis quando contrato, efeito ou limitação não estão claros pela assinatura.

Na revisão, remova comentários gerados automaticamente, placeholders e descrições óbvias. Preserve avisos de segurança e privacidade (por exemplo, risco de CPF na URL de um erro), regras de precedência e peculiaridades reais da fonte. Não altere migrações antigas só para limpar comentários gerados pelo Django.

Auditoria desta rodada: foram retirados cabeçalhos gerados pelo Django, comentário placeholder de admin, descrições óbvias em templates, JavaScript e funções, além de uma estimativa de tempo da API que não tinha medição atual. Permaneceram explicações de segurança, comportamento atípico da fonte e regras de negócio que não são evidentes pela leitura do código.

## Erros e fallback

**Estado atual:** `portal/errors.py` centraliza as mensagens públicas de filtro inválido, `404` e `500`. Algumas páginas têm mensagens próprias para ausência de dados. `/healthz/` retorna `503` quando o banco falha; falhas de coleta são registradas no processo de sincronização. O catálogo de estados de dados e o monitoramento por módulo ainda não estão completos.

**Padrão para mudanças novas:** primeiro identifique o tipo de situação; depois mostre uma frase humana, a consequência e uma ação possível. Um código curto é referência para suporte, nunca substitui a explicação.

| Código de referência | Situação | Mensagem para a pessoa | Próximo passo / comportamento |
| --- | --- | --- | --- |
| `ENTRADA-001` | Ano/mês inválidos | “Selecione um ano e um mês válidos para consultar.” | Manter formulário e orientar correção; não tratar como erro do servidor. |
| `DADOS-001` | Nenhum snapshot importado | “Ainda não há dados importados para esta consulta.” | Mostrar fonte e, quando possível, último período disponível ou outro tema. |
| `DADOS-002` | Filtro válido sem resultado | “Não há registros neste recorte dos dados importados.” | Permitir limpar filtros; não afirmar que o fato não ocorreu. |
| `DADOS-003` | Coleta falhou, snapshot antigo existe | “A última atualização não foi concluída. Você está vendo os dados de [data].” | Manter snapshot válido; exibir data real quando houver sinal confiável da falha. |
| `NAVEGACAO-404` | Página ou registro não encontrado | “Não encontramos esta página ou registro.” | Link para a página inicial ou lista do módulo. |
| `SISTEMA-500` | Erro inesperado no site | “Não foi possível abrir esta página agora.” | Sugerir tentar de novo; não expor exceção, credenciais ou dados pessoais. |

`DADOS-003` depende de um estado de última falha por módulo, que **ainda não existe**; não exiba esse aviso só porque o snapshot é antigo. Para coleta, registre etapa, módulo, horário, período, resultado e contagens; não registre payload completo, token ou URL com CPF. Uma exceção técnica pode aparecer em log protegido após sanitização, nunca na mensagem pública. `/healthz/` usa `ok`/`unavailable` porque é uma checagem de infraestrutura, não uma página para leitura cidadã.

Os códigos `DADOS-*` acima são especificação pendente; só `ENTRADA-001`, `NAVEGACAO-404` e `SISTEMA-500` estão implementados. Ao adicionar um estado, inclua mensagem em `portal/errors.py` e teste a renderização.

## Testes e revisão de performance

Teste o comportamento que protege a pessoa e os dados, não apenas a implementação interna:

1. **API e normalização:** payload válido, campos ausentes, tipo errado, duplicidade, paginação incompleta, período divergente e valores monetários inválidos.
2. **Persistência:** falha não publica conjunto parcial; coleta repetida é idempotente onde previsto; relações e migrações mantêm integridade.
3. **Páginas:** snapshot presente, ausente e antigo; filtro válido/inválido; fonte, período e linguagem sem acusação. Confirme que a view não chama a API externa.
4. **Privacidade:** CPF e segredos fora do HTML, URL pública, snapshot e logs; links externos restritos aos domínios aprovados.
5. **Interface:** 320–390 px e desktop, teclado, foco, contraste, texto ampliado, valor longo, conexão lenta e página utilizável sem JavaScript para o conteúdo principal.

Antes de concluir, execute os testes afetados e `python manage.py check`; rode a suíte completa quando a mudança cruzar módulos. Relate comandos executados e falhas. Para performance, considere o caminho inteiro: tempo e volume da API, validação, consultas/escritas no banco, custo de renderização, tamanho de HTML/CSS/JS e carregamento no telefone. Reporte o risco concreto com local e impacto, por exemplo “N+1 em detalhe de contratos” ou “coleta de 1.000 detalhes pode ultrapassar o ciclo”; não declare a interface “leve” sem observar payload e comportamento.

## Auditoria e monitoramento

Para cada mudança, a revisão humana deve receber: arquivos e fluxos alterados; hipótese de falha; efeito esperado para a pessoa; como reproduzir e depurar; evidência de teste; risco residual. Um log de sincronização deve permitir responder **qual módulo, qual período, quando, quantos registros, qual etapa e qual resultado**, sem expor dados pessoais.

**Pontos de atenção no estado atual:**

- `SyncRun` registra status e contagens apenas da coleta geral. Receita, folha e contratos têm mensagens no scheduler, mas não um histórico persistido equivalente por módulo.
- `run_sync_scheduler` usa intervalo configurável para unidades/credores; receita, folha e contratos usam 24 horas fixas. Não documente o intervalo variável como se controlasse todos os módulos.
- O scheduler relê algumas flags do `.env` a cada 15 segundos; outras configurações carregadas pelo Django exigem reinício. Em implantação com múltiplas instâncias, deve existir apenas um scheduler.
- A coleta de diárias confere contagem e soma antes de publicar. Se a fonte mudar entre as consultas, a execução falha e o conjunto anterior fica no ar até o próximo ciclo. A exportação tem cerca de 17 MB e o cliente usa limite de 60 segundos: acompanhe esse tempo se o volume crescer. Uma `DailySnapshot` antiga, sem resumo, é tratada como dados não importados.
- A coleta de contratos valida a quantidade antes de publicar, mas aditivos/fiscais são graduais. Uma página deve diferenciar detalhe ainda não coletado de detalhe comprovadamente ausente.
- Na coleta geral, unidades são gravadas antes da etapa de credores. Se credores falharem, a execução fica marcada como falha e o ranking anterior é preservado, mas unidades já atualizadas não são revertidas. Revisar esse limite antes de tratar a coleta geral como publicação inteiramente atômica.
- Exceções podem conter URL, parâmetros ou identificadores. A coleta geral agora persiste apenas etapa e classe da falha; comandos e scheduler imprimem apenas classe e módulo. Ao ampliar observabilidade, mantenha essa barreira e documente onde obter diagnóstico técnico sem expor dados pessoais.
