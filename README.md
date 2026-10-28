# InspectGovRR

Aplicação Django para consultar e apresentar dados de transparência pública de Roraima. O portal usa PostgreSQL e importa dados da API Fiplan em um processo separado das páginas públicas. As telas consultam os dados locais, e a sincronização pode ser manual ou automática.

## Estrutura

A interface usa componentes compartilhados em templates Django e CSS padrão. Consulte [o guia de componentes e estilos](docs/design-system.md) antes de criar ou modificar um módulo.

- `integrations/fiplan_api/client.py`: autenticação e requisições HTTP à Fiplan.
- `unidades/`: modelo, página, rota, administração, template, CSS e sincronização de unidades orçamentárias.
- `receita_arrecadada/`: painel Top 5 por unidade, snapshot local e comando de atualização diária.
- `remuneracoes/`: ranking de até 50 remunerações, comparação em salários mínimos, matrículas e detalhamento local.
- `integrations/sync/`: orquestração da coleta, estatísticas por credor e, opcionalmente, diárias.
- `integrations/management/commands/`: comandos manual e automático de sincronização.
- `integrations/selectors.py` e `integrations/views.py`: consultas e páginas públicas, sem chamadas externas.
- `integrations/models.py`: diárias, estatísticas por credor e histórico das execuções de sincronização.

O app `unidades` assume a tabela física `integrations_unit`, preservando os registros e as chaves estrangeiras já existentes. As migrações transferem o estado do modelo e seu tipo de conteúdo administrativo sem recriar a tabela. Novas estatísticas por credor são registradas por unidade, exercício e natureza da despesa, vinculadas a uma execução. O ranking mostra apenas a última execução concluída para o período configurado; dados anteriores sem período definido aparecem como legado até a primeira sincronização bem-sucedida.

## Requisitos

- Python 3.12 ou superior, `pip` e suporte a `venv` para execução nativa; o contêiner de desenvolvimento usa Python 3.13. Em Debian/Ubuntu, instale o pacote `python3-venv` correspondente à sua versão do Python, se necessário.
- PostgreSQL para execução nativa, ou Docker com o plugin Docker Compose para execução em contêineres.

## Configuração do ambiente

Na raiz do projeto, crie o arquivo local de configuração:

```bash
cp .env.example .env
```

Edite `.env` antes de iniciar. `DJANGO_SECRET_KEY` e `DB_PASSWORD` devem ser alteradas para valores locais próprios. O arquivo `.env` não é versionado.

| Variável | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY` | Chave secreta do Django. |
| `DJANGO_DEBUG` | Ativa a página de depuração em desenvolvimento. |
| `DJANGO_ALLOWED_HOSTS` | Hosts aceitos, separados por vírgula. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Nome, usuário e senha do PostgreSQL. |
| `DB_HOST`, `DB_PORT` | Endereço e porta do banco na execução nativa. No Compose, o serviço web usa `db:5432`. |
| `DB_HOST_PORT` | Porta do PostgreSQL publicada no computador pelo Compose; padrão `5432`. |
| `WEB_HOST_PORT` | Porta do Django publicada no computador pelo Compose; padrão `8000`. |
| `FIPLAN_USERNAME`, `FIPLAN_PASSWORD` | Credenciais necessárias para importar dados da API Fiplan. As páginas públicas podem abrir sem elas. |
| `FIPLAN_AUTO_SYNC_ENABLED` | `True` inicia a coleta automática; `False` a pausa. Padrão: `False`. |
| `FIPLAN_SYNC_INTERVAL_MINUTES` | Minutos entre o fim de uma coleta e o início da próxima. `60` = 1 hora; `1440` = 24 horas. Valor mínimo: `1`. |
| `FIPLAN_SYNC_YEAR` | Exercício importado e exibido no ranking. Padrão do exemplo: `2026`. |
| `FIPLAN_NATURE_CODE` | Código de natureza da despesa usado na consulta de credores. |
| `FIPLAN_SYNC_DIARIAS_ENABLED` | Inclui diárias na coleta automática. Padrão: `False`, até confirmar o identificador estável fornecido pela API. |
| `FIPLAN_REVENUE_AUTO_SYNC_ENABLED` | Atualiza o Top 5 de receita a cada 24 horas, de forma independente da coleta geral. Ativo por padrão quando há credenciais Fiplan; `False` pausa apenas essa atualização. |
| `FIPLAN_PAYROLL_AUTO_SYNC_ENABLED` | Atualiza o ranking e os detalhes de remunerações a cada 24 horas. Ativo por padrão quando há credenciais; `False` pausa apenas a folha. |

O processo automático relê `FIPLAN_AUTO_SYNC_ENABLED`, `FIPLAN_SYNC_INTERVAL_MINUTES` e `FIPLAN_REVENUE_AUTO_SYNC_ENABLED` do `.env` a cada 15 segundos. Edite esses valores com os contêineres em execução para ligar ou pausar as coletas e mudar a frequência da coleta geral sem reiniciá-los. Ao ativar, a primeira coleta começa imediatamente. Alterações no exercício, natureza ou opção de diárias exigem reiniciar os processos web e scheduler para manter as páginas e a coleta no mesmo período. Uma coleta em andamento termina antes de aplicar uma pausa.

## Executar com Python e Django

1. Instale e inicie o PostgreSQL. Crie o usuário e o banco definidos em `.env` usando uma sessão de administrador do PostgreSQL. Com os valores de exemplo:

   ```sql
   CREATE USER inspectgovrr WITH PASSWORD 'change-this-local-db-password';
   CREATE DATABASE inspectgovrr OWNER inspectgovrr;
   ```

   Ajuste o SQL se você trocou os valores no `.env`. Para um PostgreSQL local, mantenha `DB_HOST=localhost` e `DB_PORT=5432` (ou informe a porta real do serviço).

2. Crie um ambiente virtual e instale as dependências na raiz do repositório:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. Aplique as migrações e inicie o servidor:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

Abra <http://127.0.0.1:8000/>. O servidor de desenvolvimento do Django recarrega as alterações em arquivos Python.

Para importar uma vez, configure `FIPLAN_USERNAME` e `FIPLAN_PASSWORD` e execute em outro terminal, com o ambiente virtual ativo:

```bash
python manage.py sync_fiplan
```

Para atualizar somente o painel de receita arrecadada com uma consulta à API:

```bash
python manage.py sync_revenue
```

Para manter a sincronização automática, execute em outro terminal:

```bash
python manage.py run_sync_scheduler
```

Com `FIPLAN_AUTO_SYNC_ENABLED=False`, o processo ainda atualiza diariamente o painel de receita se houver credenciais e `FIPLAN_REVENUE_AUTO_SYNC_ENABLED` não estiver definido como `False`. Você pode alterar as flags e o intervalo da coleta geral no `.env` enquanto ele roda. Para outro exercício, use `python manage.py sync_fiplan --year 2025` na importação manual.

## Executar com Docker Compose

Com Docker e Compose disponíveis, crie e configure `.env` como descrito acima e execute:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Abra <http://localhost:8000/> (ou use a porta escolhida em `WEB_HOST_PORT`). O Compose inicia PostgreSQL, aplica as migrações e inicia `web` e `scheduler` como processos separados. A atualização diária da receita funciona mesmo com a coleta geral desativada, quando há credenciais configuradas. O banco fica no volume `postgres_data`, e o código local é montado em `/app`: ao salvar arquivos Python ou templates, a aplicação reflete as mudanças sem recriar os contêineres.

Comandos úteis, em outro terminal:

```bash
docker compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.dev.yml exec web python manage.py sync_fiplan
docker compose -f docker-compose.dev.yml exec web python manage.py sync_revenue
docker compose -f docker-compose.dev.yml logs -f web
docker compose -f docker-compose.dev.yml logs -f scheduler
docker compose -f docker-compose.dev.yml down
```

`down` encerra os contêineres e preserva os dados do PostgreSQL. Se você alterar `requirements.txt` ou `Dockerfile.dev`, reconstrua as imagens com `docker compose -f docker-compose.dev.yml up --build`. Para aplicar mudanças nas variáveis do banco, exercício ou natureza, recrie os serviços com `docker compose -f docker-compose.dev.yml up -d --force-recreate`; a flag e o intervalo de sincronização são atualizados pela leitura contínua do `.env`. Não é necessário apagar o volume do banco para atualizar o código. Se as portas padrão estiverem ocupadas, altere `DB_HOST_PORT` ou `WEB_HOST_PORT` no `.env`; para conectar uma execução nativa ao banco do Compose, use `DB_HOST_PORT` também em `DB_PORT`. Depois da primeira inicialização do volume, trocar `DB_NAME`, `DB_USER` ou `DB_PASSWORD` no `.env` não altera automaticamente o banco já criado.

## Rotas atuais

| Rota | Estado atual |
| --- | --- |
| `/` | Página inicial. |
| `/admin/` | Administração do Django. |
| `/unidades/` | Mostra as unidades já importadas no banco local. |
| `/receita-arrecadada/` | Mostra pódio e barras do Top 5 de receita por unidade no último período sincronizado. |
| `/remuneracoes/` | Ranking do último mês importado, filtros dentro dos 50 registros e links para composição e matrículas. |
| `/integrations/get-units` | Redireciona para `/unidades/` para preservar o endereço anterior. |
| `/integrations/get-dailies` | Retorna até 100 diárias já armazenadas, sem expor o CPF. |
| `/integrations/get-list-credor` | Mostra os dez credores com maior total pago na última coleta concluída do exercício e natureza configurados. |

As antigas rotas HTTP de token e importação foram substituídas pelos comandos `sync_fiplan` e `run_sync_scheduler`. A importação de diárias permanece optativa porque o campo de identificação estável da resposta Fiplan ainda precisa ser confirmado; se ele faltar, a coleta falha e o ranking mantém o último lote concluído. A paginação de credores usa o parâmetro `pagina` e interrompe a coleta se a API repetir uma página, evitando publicar um ranking incompleto. Este Compose é destinado ao desenvolvimento; o `runserver` e os valores de exemplo de `.env` não são configuração de produção.

O ranking de receita consulta `/api/v1/receita-arrecadada/top-valor-total-uo` com o exercício corrente em Roraima, meses de janeiro ao mês atual e `top=5`. A resposta observada da API não respeitou o limite nem a ordenação; por isso, a aplicação valida, ordena por `valorRealizacaoMes` e guarda apenas cinco unidades. As páginas públicas leem o snapshot local, sem fazer uma chamada à Fiplan a cada acesso.

## Remunerações

Após aplicar as migrações, execute `python manage.py sync_payroll` (no Docker, use `docker compose -f docker-compose.dev.yml exec web python manage.py sync_payroll`). O comando consulta `/api/v1/remuneracoes/rankingTotalBruto` com `limit=50`, começando no mês corrente de Roraima e recuando até 12 competências quando a resposta for vazia. Para importar um período específico, use `--year 2026 --month 8`. Respostas inválidas ou falhas não substituem o snapshot anterior.

Os detalhes são coletados por pessoa em `/api/v1/remuneracoes`, com paginação limitada a 10 páginas de 100 registros por pessoa. A coleta confirma CPF e competência, rejeita páginas repetidas e só publica o snapshot após terminar. CPF é utilizado somente durante a consulta: não é armazenado no snapshot nem enviado ao navegador. As rotas usam identificadores derivados com HMAC. Reinicie o scheduler após instalar este módulo; a flag `FIPLAN_PAYROLL_AUTO_SYNC_ENABLED` é relida do `.env` a cada ciclo, como a flag da receita.

Os filtros de órgão e múltiplas matrículas atuam sobre todo o ranking importado, **não sobre toda a folha estadual**. Matrículas são deduplicadas por órgão e número; o painel não afirma situação ativa, jornada ou irregularidade. O detalhe preserva valores do ranking e da consulta geral separadamente, sinalizando divergências. Lançamentos seguem as descrições da fonte; proventos e descontos não são classificados como violações do teto.

A referência do salário mínimo é cadastrada por ano em `remuneracoes/mappers.py`, com fonte oficial e vigência limitada ao ano validado. Inicialmente está disponível 2026 (R$ 1.621,00, Decreto nº 12.797/2025). Anos sem referência exibem os valores monetários sem comparação. Cadastre e valide a fonte de cada novo ano antes de habilitar a equivalência. A página de detalhe também oferece o canal da Ouvidoria do Executivo estadual; nenhum envio de manifestação é automático.

Validação do módulo: `python manage.py test remuneracoes receita_arrecadada unidades`.
