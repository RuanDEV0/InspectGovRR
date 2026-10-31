# InspectGovRR

**Um caminho para entender dados públicos de Roraima.** O InspectGovRR organiza registros da [API de consultas do Portal da Transparência do Governo de Roraima](https://api2.transparencia.rr.gov.br/transparencia/swagger-ui/#/) — abreviada na interface como **API Transparência RR** — em páginas com linguagem simples, contexto e links para a fonte. O projeto é independente: os registros financeiros vêm da fonte oficial; seleção, cálculos, apresentação e explicações são feitos aqui. A comparação com salário mínimo usa uma referência externa identificada na página.

> **Comece por aqui:** [o que já é possível consultar](#o-que-você-pode-consultar) · [como os dados chegam ao site](#como-o-site-funciona) · [rodar no computador](#desenvolvimento-local) · [publicar](#publicação)

Para decisões de produto e contribuições com IA, leia o [guia em `docs/`](docs/README.md).

## Para quem chegou como cidadão

Você não precisa saber o que é “natureza da despesa” ou “unidade orçamentária” para explorar o portal. A página inicial (`/`) organiza os assuntos em perguntas. A página Entenda (`/entenda/`) explica termos usados nas consultas. Esses endereços funcionam no site depois que ele estiver publicado; neste repositório, veja a tabela a seguir para conhecer o que cada tela oferece.

### O que você pode consultar

| Pergunta | Página | O que aparece hoje |
| --- | --- | --- |
| Quanto dinheiro entra? | `/receita-arrecadada/` | As cinco unidades com maior receita no período importado. |
| Para onde vão as viagens pagas pelo estado? | `/diarias/` | Mapa dos municípios, destinos no Brasil e no exterior, motivos agrupados, órgãos e bilhetes de cada viagem. Até 50 pessoas com os maiores valores em `/diarias/pessoas/`. |
| Quanto ganham os servidores? | `/remuneracoes/` | Até 50 remunerações do mês mais recente disponível, com composição e matrículas quando informadas pela fonte. |
| Com quem o governo fecha negócio? | `/contratos/` | Contratos com vigência no ano, fornecedores, órgãos, aditivos e fiscais coletados. Há páginas por fornecedor e de contratos próximos do vencimento. |
| Quais órgãos aparecem nos dados? | `/unidades/` | Unidades orçamentárias importadas. |
| O que significam os termos? | `/entenda/` | Glossário em linguagem comum. |

**Como ler os resultados:** cada página indica o período e a atualização dos dados disponíveis. Uma lista limitada, como o Top 5 da receita ou o ranking de 50 remunerações, não representa todos os registros do estado. Um valor alto, uma diferença ou a ausência de informação não prova irregularidade. Se quiser pedir esclarecimentos sobre um registro, use a [Ouvidoria do Estado](https://ouvidoria.rr.gov.br/). O portal não envia manifestações por você.

Os temas mostrados como **“Em preparação”** na página inicial ainda não são consultas publicadas. Se a fonte não tiver sido sincronizada ou uma coleta falhar, uma tela pode ficar vazia ou continuar exibindo o último conjunto válido.

## Como o site funciona

```mermaid
flowchart LR
    C[Pessoa visitante] -->|HTTPS| P[Plataforma ou proxy]
    P --> W[Gunicorn + Django<br/>rotas, views, templates e seletores]
    W -->|consulta| DB[(PostgreSQL<br/>snapshots e histórico)]
    W --> S[WhiteNoise<br/>CSS, JS, fontes e imagens]
    A[Processo scheduler<br/>comandos Django] -->|autentica e consulta| F[API Transparência RR]
    A -->|valida e publica| DB
    M[Migrações] --> DB
```

**A navegação pública lê o PostgreSQL.** O processo `scheduler` consulta a API externa em separado, valida as respostas e grava snapshots locais. Assim, abrir uma página não dispara uma consulta à API externa. O Django renderiza HTML no servidor com templates e CSS; o WhiteNoise serve os arquivos estáticos coletados na imagem de produção.

### Mapa do backend

| Camada | Código | Responsabilidade |
| --- | --- | --- |
| Entrada HTTP | `InspectGovRR/urls.py` e `*/urls.py` | Liga cada endereço à view do módulo. |
| Páginas | `portal/`, `unidades/`, `receita_arrecadada/`, `remuneracoes/`, `diarias/`, `contratos/` | Monta o contexto e apresenta os dados locais. |
| Consultas e apresentação | `*/services.py`, `*/mappers.py`, `portal/formatting.py` | Seleciona snapshots, valida e formata números e registros. |
| Coleta | `integrations/fiplan_api/client.py`, `integrations/sync/`, `*/management/commands/` | Acessa a API de consultas por HTTP, sincroniza módulos e registra execuções. O nome `fiplan_api` é um identificador técnico legado. |
| Persistência | `*/models.py` e `*/migrations/` | Guarda unidades, snapshots, contratos, detalhes e histórico da sincronização. |
| Interface | `templates/`, `*/templates/`, `static/`, `*/static/` | Templates, componentes, estilos, fontes e JavaScript. Veja o [guia visual](docs/design-system.md). |

O catálogo em `portal/modules.py` define os módulos disponíveis e os que estão em preparação. O app `unidades` mantém a tabela física `integrations_unit`, preservando os dados e as chaves estrangeiras anteriores. `SyncRun` registra a coleta geral. O app `integrations` continua responsável pela coleta em segundo plano, **sem rotas HTTP públicas**.

### Administração dos dados

**Implementado:** `/admin/` mostra unidades, receita, remunerações, diárias, contratos e registros da coleta. Unidades continuam editáveis; os demais registros importados são consultáveis, com filtros e busca onde úteis, mas não podem ser criados, alterados ou apagados no admin, pois a sincronização publica e substitui esses conjuntos. O CPF do modelo legado de diárias e o identificador de credor, que pode ser pessoal, não aparecem nas telas administrativas. O acesso exige conta administrativa com permissão de visualização do modelo.

**Pendente:** os temas “Em preparação” pertencem ao catálogo estático `portal/modules.py`, não a modelos do banco. Publicar um deles ainda exige implementar a consulta e mover o módulo para `AVAILABLE` no código; o admin não ativa temas novos nem executa coletas.

### Atualizações e limites dos dados

- **Coleta geral:** `sync_fiplan` importa unidades e credores. A rotina antiga de diárias (v1) continua desligada; a coleta atual é `sync_dailies`.
- **Receita:** `sync_revenue` valida, ordena e conserva as cinco unidades de maior valor; usa o ano corrente e janeiro até o mês atual, no horário de Roraima.
- **Remunerações:** `sync_payroll` procura até 12 competências anteriores quando o mês atual ainda não tem dados. Importa até 50 posições e seus detalhes. O CPF é usado apenas na consulta à fonte: não é armazenado no snapshot nem enviado ao navegador. O endereço do detalhe usa um identificador derivado com HMAC.
- **Diárias (v3):** `sync_dailies` usa a exportação `novo_diarias/json`, porque a listagem paginada só ordena por campos não únicos e repete e perde registros entre as páginas. A contagem da listagem confirma a exportação; o que faltar, como lançamentos sem data de viagem, é buscado por órgão; a soma é conferida com `total-por-ano-uo`. Qualquer divergência mantém o conjunto anterior. Roda no agendador quando `FIPLAN_DAILIES_AUTO_SYNC_ENABLED=True`; a coleta leva cerca de 1min30.
- **Contratos:** `sync_contracts` valida a quantidade da exportação antes de publicar o conjunto do ano. Aditivos e fiscais são coletados em lotes e podem levar mais de um ciclo para completar.
- **Agendamento:** `run_sync_scheduler` mantém essas coletas em um processo próprio. Receita, remunerações e contratos são atualizados a cada 24 horas quando há credenciais, salvo se a respectiva flag for `False`. A coleta geral é independente e começa desligada.

## Para desenvolver

### Requisitos

- Python 3.12 ou superior e PostgreSQL para execução nativa; a imagem Docker usa Python 3.13.
- Ou Docker com o plugin Compose.

### Variáveis de ambiente

Há **um único arquivo ativo: `.env`**. Escolha o modelo correspondente ao ambiente: `.env.dev.example` para desenvolvimento ou `.env.prod.example` para produção. Copie o modelo escolhido para `.env` e preencha os segredos; ao trocar de ambiente, substitua o conteúdo do `.env` com cuidado para não perder os valores locais. O `.env` atual deste repositório está configurado para desenvolvimento e foi preservado com permissão de leitura apenas para o proprietário (`600`). O arquivo é ignorado pelo Git e excluído da imagem Docker.

No Compose, web, migração e scheduler leem esse mesmo `.env`. Em produção, o Compose entrega `FIPLAN_USERNAME` e `FIPLAN_PASSWORD` somente ao scheduler. No Render, o `.env` local não é enviado: configure as variáveis no painel dos serviços usando `.env.prod.example` como referência, sem publicar credenciais no repositório.

| Variável | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY` | Chave privada do Django; mantenha a mesma nos processos web e scheduler. |
| `DJANGO_DEBUG` | `True` apenas no ambiente de desenvolvimento. |
| `DJANGO_ALLOWED_HOSTS` | Domínios aceitos, separados por vírgula. O hostname padrão do Render é acrescentado automaticamente. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens HTTPS de domínios próprios, separadas por vírgula. A origem padrão do Render é acrescentada automaticamente. |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | Confia em `X-Forwarded-Proto` somente quando o proxy controla esse cabeçalho. |
| `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS` | Redirecionamento HTTPS e duração de HSTS; configure depois de ter HTTPS funcional. |
| `DATABASE_URL` | URL PostgreSQL do serviço externo em produção; tem prioridade sobre as variáveis `DB_*`. Inclua a opção TLS exigida pelo provedor. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexão PostgreSQL local quando `DATABASE_URL` não está definida, como no Compose de desenvolvimento. |
| `WEB_MIGRATE_ON_STARTUP` | Use `True` apenas em um web de instância única sem comando de pré-deploy; executa migrações antes do Gunicorn. |
| `FIPLAN_INITIAL_LOAD_ENABLED` | No web único sem scheduler, inicia uma carga dos conjuntos ausentes em segundo plano após verificar as migrações. Padrão `False`; requer credenciais da API no web. |
| `FIPLAN_USERNAME`, `FIPLAN_PASSWORD` | Credenciais da API, necessárias para importar; o site pode iniciar sem elas. |
| `FIPLAN_AUTO_SYNC_ENABLED`, `FIPLAN_SYNC_INTERVAL_MINUTES` | Liga a coleta geral e define minutos entre o fim de uma execução e o início da próxima; mínimo 1. |
| `FIPLAN_SYNC_YEAR`, `FIPLAN_NATURE_CODE`, `FIPLAN_SYNC_DIARIAS_ENABLED` | Exercício, natureza de despesa e opção de diárias da coleta geral. |
| `FIPLAN_REVENUE_AUTO_SYNC_ENABLED`, `FIPLAN_PAYROLL_AUTO_SYNC_ENABLED`, `FIPLAN_CONTRACTS_AUTO_SYNC_ENABLED`, `FIPLAN_DAILIES_AUTO_SYNC_ENABLED` | Pausam cada coleta diária. Diárias v3 começam desligadas até a revisão de privacidade do módulo; as demais ficam ativas quando há credenciais. |
| `WEB_HOST_PORT`, `DB_HOST_PORT` | Portas locais publicadas pelo Compose de produção/desenvolvimento. |
| `WEB_BIND_ADDRESS` | Interface de publicação no Compose de produção; padrão `127.0.0.1`, para acesso por um proxy no mesmo servidor. |

No Compose de desenvolvimento, o scheduler relê flags e intervalo de `.env` a cada 15 segundos. Em plataformas como Render, as configurações são variáveis do processo: altere-as no painel e reinicie/reimplante o serviço. Mudanças de exercício, natureza e credenciais também exigem reinício para que web e scheduler usem a mesma configuração.

### Desenvolvimento local

**Com Docker Compose:**

```bash
cp -i .env.dev.example .env
# Edite .env antes de iniciar.
chmod 600 .env
docker compose -f docker-compose.dev.yml up --build
```

Abra <http://localhost:8000/>. Esse Compose inicia banco, migrações, web com `runserver` e scheduler; monta o código local para recarga durante o desenvolvimento. O banco fica no volume `postgres_data`.

Para importar dados ou criar uma conta administrativa usando os contêineres:

```bash
docker compose -f docker-compose.dev.yml exec web python manage.py sync_fiplan
docker compose -f docker-compose.dev.yml exec web python manage.py sync_revenue
docker compose -f docker-compose.dev.yml exec web python manage.py sync_payroll
docker compose -f docker-compose.dev.yml exec web python manage.py sync_contracts
docker compose -f docker-compose.dev.yml exec web python manage.py sync_dailies
docker compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
```

`docker compose -f docker-compose.dev.yml down` para os serviços e preserva o volume do banco.

**Com Python:** crie no PostgreSQL o usuário e o banco indicados no `.env`. Depois:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Comandos de coleta manual, com o ambiente virtual ativo:

```bash
python manage.py sync_fiplan
python manage.py sync_revenue
python manage.py sync_payroll
python manage.py sync_contracts
python manage.py sync_dailies
```

Para usar o agendador fora do Compose, execute `python manage.py run_sync_scheduler` em outro terminal. Para importar outro exercício na coleta geral, por exemplo, use `python manage.py sync_fiplan --year 2025`. Execute os testes com `python manage.py test`.

## Publicação

A imagem de `Dockerfile` serve tanto para o site quanto para o scheduler. Ela instala as dependências, executa `collectstatic`, usa um usuário sem privilégios e inicia Gunicorn para o site. Antes do Gunicorn, o web verifica a conexão com o banco e se há migrações pendentes; uma falha impede que um serviço sem banco seja anunciado como pronto. A aplicação recebe a porta por `PORT` (padrão `8000`). A coleta precisa rodar como **um único processo scheduler** para evitar sincronizações duplicadas. O PostgreSQL deve manter dados persistentes; os contêineres web e scheduler não precisam de disco persistente.

### Render: primeiro destino

O arquivo `render.yaml` descreve **um serviço web Docker e um background worker**. O PostgreSQL fica em outro serviço ou provedor, fora deste Blueprint. O web executa as migrações antes de cada deploy e publica `/healthz/` como checagem de saúde. Essa rota responde `503` se o banco não puder ser consultado. O worker executa `run_sync_scheduler` e recebe a mesma chave secreta que o web.

1. Crie o PostgreSQL externo e obtenha a **URL de conexão acessível a partir do Render**, com TLS habilitado conforme o provedor. Exemplo de formato: `postgresql://usuario:senha@host:5432/banco?sslmode=require`. Se o provedor restringir IPs, autorize as [faixas de saída do serviço Render](https://render.com/docs/outbound-ip-addresses).
2. Envie o repositório para um provedor Git conectado ao Render e crie um **Blueprint** apontando para `render.yaml`. Ele não cria um banco no Render. Revise os custos antes de aplicar: o comando de pré-deploy requer um serviço web pago e o background worker não tem plano gratuito.
3. Informe a **mesma `DATABASE_URL` externa** no web e no worker, nos campos secretos solicitados na primeira criação do Blueprint. Nunca coloque a URL ou a senha no Git. Se os serviços já existem, ajuste `DATABASE_URL` manualmente na página **Environment** de cada um: alterações `sync: false` no Blueprint não preenchem serviços existentes.
4. Defina `FIPLAN_USERNAME` e `FIPLAN_PASSWORD` no worker quando quiser iniciar as coletas. Sem elas, o site sobe e exibe estados vazios até haver dados.
5. Ajuste `FIPLAN_SYNC_YEAR` no worker e, se usar a coleta geral, também no web; ajuste `FIPLAN_NATURE_CODE` nos dois serviços pelo mesmo motivo. O Blueprint ativa `FIPLAN_AUTO_SYNC_ENABLED=True` **no worker** para importar unidades e credores. Receita, remunerações e contratos iniciam a coleta diária quando recebem credenciais. O intervalo de `1440` minutos é contado após a conclusão da coleta; a primeira execução começa quando o worker inicia.
6. Se usar domínio próprio, configure `DJANGO_ALLOWED_HOSTS` e `DJANGO_CSRF_TRUSTED_ORIGINS` no web, com o hostname e a origem HTTPS completos, respectivamente. Confira `/healthz/`, a página inicial, os arquivos CSS e os logs do worker. A primeira importação pode demorar; páginas sem snapshot mostram estado vazio.

O `render.yaml` não contém senhas. Os campos `sync: false` pedem `DATABASE_URL` e as credenciais da API na criação do Blueprint. No Render, o site força HTTPS e inicia HSTS com duração de uma hora. O comando de pré-deploy faz a migração quando disponível. Em um **web gratuito criado manualmente**, configure `WEB_MIGRATE_ON_STARTUP=True` na página Environment para uma única instância executar as migrações antes do Gunicorn; depois de migrar para um plano com pré-deploy, remova essa opção. Confira a [referência de Blueprints](https://render.com/docs/blueprint-spec) e os [comandos de deploy](https://render.com/docs/deploys).

Para conferir a primeira carga, abra o Dashboard do Render, procure `inspectgovrr-scheduler` na lista de serviços e veja **Logs**. O início esperado é `Agendador Fiplan iniciado`; a coleta geral registra `Sincronização ativada` e depois `Sincronização concluída`. Se esse serviço não existir, definir as variáveis apenas no web não executa o agendador. No web gratuito, o Render não oferece shell nem jobs avulsos: para uma importação manual, execute os comandos de gestão a partir de um ambiente com acesso ao PostgreSQL externo e as mesmas variáveis de produção, sem expor as credenciais no repositório.

#### Primeira carga em um web gratuito sem worker

No serviço **web gratuito criado manualmente**, configure `FIPLAN_USERNAME`, `FIPLAN_PASSWORD` e `FIPLAN_INITIAL_LOAD_ENABLED=True` em **Environment**; salve as variáveis para reiniciar o serviço. No Blueprint com worker, a flag do web permanece `False`. `FIPLAN_SYNC_YEAR` e `FIPLAN_NATURE_CODE` definem a coleta de unidades e credores. `FIPLAN_AUTO_SYNC_ENABLED` e `FIPLAN_SYNC_INTERVAL_MINUTES` pertencem ao scheduler e não acionam a carga inicial no web. Mantenha o intervalo em `1440` quando usar um worker futuramente.

O web abre normalmente enquanto `bootstrap_initial_data` consulta a API. Os **Logs do web** mostram `Carga inicial Fiplan iniciada`, cada etapa e `Carga inicial concluída`. São importados receita, remunerações, resumo/lista de contratos, unidades e credores; a coleta extensa de aditivos e fiscais fica para o worker ou execução manual. A cada reinício, o comando verifica o PostgreSQL e tenta apenas as etapas ainda ausentes. Há um bloqueio no PostgreSQL para impedir duas cargas iniciais simultâneas. Se alguma etapa falhar, as demais continuam e a ausente será tentada no próximo início. Erros são registrados sem URLs nem credenciais.

Depois de confirmar os dados nas páginas, defina `FIPLAN_INITIAL_LOAD_ENABLED=False` e remova `FIPLAN_USERNAME` e `FIPLAN_PASSWORD` do web se não houver outra necessidade. **Essa flag faz somente a primeira carga; não substitui atualização periódica.** O Render [suspende o web gratuito após 15 minutos sem tráfego de entrada](https://render.com/docs/free), o que pode interromper uma coleta longa; na próxima inicialização, as etapas ainda ausentes serão retomadas. Para atualizações regulares, use um worker ou outro agendador fora do web gratuito.

### Outra plataforma Docker ou servidor próprio

Forneça `DATABASE_URL` ou as variáveis `DB_*`, `DJANGO_SECRET_KEY`, o domínio permitido e HTTPS por um proxy da plataforma. Execute `python manage.py migrate --noinput` **uma vez por deploy**, antes de servir a nova versão. Inicie a imagem com o comando padrão para o web e com `python manage.py run_sync_scheduler` para o worker. Configure uma checagem HTTP em `/healthz/`.

Para um servidor com Docker Compose e PostgreSQL externo:

```bash
cp -i .env.prod.example .env
# Preencha a URL externa, as credenciais, o domínio e as opções de HTTPS.
chmod 600 .env
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
```

O Compose de produção executa as migrações e inicia web e scheduler usando `DATABASE_URL` em `.env`; o banco não é criado pelo Compose. A porta web fica restrita a `127.0.0.1` por padrão; coloque um proxy HTTPS confiável na frente antes de expor o serviço à internet. Se o proxy estiver em outra máquina, ajuste `WEB_BIND_ADDRESS` e restrinja o acesso com firewall. Faça backup regular no serviço PostgreSQL escolhido. Para inspecionar: `docker compose --env-file .env -f docker-compose.prod.yml ps` e `docker compose --env-file .env -f docker-compose.prod.yml logs -f web scheduler`.

### Cuidados de segurança

- O app `integrations` faz coletas internas, mas não registra URLs públicas. Endereços antigos sob `/integrations/` retornam `404`; a coleta deve ser iniciada por comandos de gerenciamento ou pelo scheduler.
- Mantenha `DJANGO_DEBUG=False`, credenciais e chave secreta fora do Git. Revise os domínios em `DJANGO_ALLOWED_HOSTS` e use HTTPS antes de ativar redirecionamento ou HSTS em outra plataforma.
- `/admin/` continua sendo o login administrativo do Django. Use contas individuais com senha forte e restrinja o acesso no proxy ou na plataforma quando possível. O projeto não implementa autenticação multifator nem limite de tentativas de login.
- A coleta de diárias não grava CPF em registros novos. A coluna `recipient_cpf` ainda existe por compatibilidade e **bancos antigos podem conter CPFs já importados**. Antes de habilitar diárias ou publicar backups, defina uma política de retenção e uma migração de limpeza desses valores.
- O histórico de credores pode conter identificadores pessoais no banco, mesmo sem uma página pública. Restrinja o acesso ao PostgreSQL e aos backups às pessoas e serviços necessários.

## Fontes e participação

- [Documentação da API de consultas do Portal da Transparência de Roraima](https://api2.transparencia.rr.gov.br/transparencia/swagger-ui/#/) — origem dos registros usados nas páginas.
- [Ouvidoria de Roraima](https://ouvidoria.rr.gov.br/) — canal oficial para pedidos de informação ou esclarecimento.
- [Guia de interface do projeto](docs/design-system.md) — padrões de componentes e estilos para contribuições.

Encontrou um erro de apresentação, um termo pouco claro ou um comportamento inesperado? Abra uma issue com a página, o período exibido, o resultado observado e, quando possível, o registro correspondente na fonte. Evite incluir CPF, senha ou outros dados sensíveis no relato.
