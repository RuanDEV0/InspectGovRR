# Pagamentos do estado

A consulta pública em `/pagamentos/` abre com o resumo do estado e um painel para cada área (saúde, segurança pública e educação). Cada painel leva ao detalhe da área, de um órgão, de um tipo de despesa ou de um recebedor, e por fim aos registros que compõem o valor. A data do pagamento determina o mês da consulta. A coleta mais recente pode incluir um mês em andamento, até a data de atualização mostrada na página.

## Fonte e cálculo

A coleta usa `/api/v1/pagamento/json` e confere o número de linhas com `totalElements` de `/api/v1/pagamento` para o mesmo filtro. A validação de 12/11/2026 trouxe 81.247 registros para janeiro a novembro. As 11 exportações corresponderam às contagens mensais, todas as datas pertenceram ao mês solicitado e a chave unidade + número do pagamento foi única no conjunto. A execução levou cerca de 6 min e 9 s em um banco local isolado. Esse tempo depende do volume e da resposta da API.

O coletor usa `anoInicio`, `anoFinal`, `mesInicio` e `mesFinal`. Na validação, consultas a outro mês e ano retornaram datas de pagamento correspondentes. O endpoint `top-valor-total-pagamento` retornou HTTP 400 para os filtros tentados. A validação dos valores contra um total independente da fonte permanece pendente.

O total mostrado é a soma de `valorPagamento` com o sinal recebido, para o período e os filtros selecionados. A contagem informa o número de registros que entram nessa soma. A amostra trouxe valores zerados e nenhum negativo. A forma como a fonte representa estornos permanece pendente.

## Resumo e painéis

A abertura mostra o resumo do estado e, no ano com regra de áreas, um painel por área. Ao escolher uma área, “Outros órgãos”, “Todos os órgãos” ou um órgão, a página mostra o mesmo painel para esse conjunto. Com um tipo de despesa ou um recebedor escolhido, ela vai direto aos registros. Todos os números abaixo são cálculos do InspectGovRR sobre os registros importados e não existem como campos da API.

| Número | Fórmula |
| --- | --- |
| Total | Soma de `valorPagamento` dos registros do conjunto no período. |
| Média por dia | Total dividido pelos dias corridos do período. No mês da última coleta, a contagem vai até a data da atualização. |
| De cada R$ 100 pagos pelo estado | Total do conjunto dividido pelo total do estado no período, vezes 100. |
| Folha, de cada R$ 100 | Soma dos registros com `descTipoDespesa` igual a “Folha de Pagamento” dividida pelo total do conjunto, vezes 100. |
| “De cada R$ 100” por tipo | Soma de cada natureza de despesa dividida pelo total, vezes 100, com duas casas. Mostra as cinco maiores naturezas; “Demais tipos de despesa” recebe o que falta para R$ 100. O bloco é omitido quando o total não é positivo ou quando alguma natureza soma valor negativo. |
| Valor por mês | Soma por mês da data de pagamento. Aparece quando nenhum mês está selecionado; o último mês pode estar em andamento. |
| Quem mais recebeu fora da folha | Registros com formato de CNPJ e tipo diferente de “Folha de Pagamento”, somados pelo nome do credor. Como o CNPJ é descartado na coleta, nomes idênticos de credores diferentes seriam somados juntos, e a lista pode incluir órgãos públicos e bancos. O filtro `credor` da página usa o mesmo nome. |
| Parte paga a órgãos do próprio estado | Soma dos registros cuja natureza de despesa tem modalidade de aplicação 91 (3º e 4º dígitos do código), que a classificação orçamentária reserva às operações entre órgãos, fundos e entidades do mesmo orçamento. |
| Maiores pagamentos | Os dez registros de maior `valorPagamento`. Nos painéis da abertura, o maior fora da folha. Pessoa física aparece sem nome. |

A lista de registros vem ordenada pelos maiores valores; a ordem por data é opcional. Os resumos ficam em cache por conjunto publicado e mês (uma hora, na memória do processo), porque um conjunto publicado não muda.

O total é a soma dos registros de pagamento e não o dinheiro que deixou os cofres públicos. Entram nele pagamentos a outros órgãos e fundos do estado, a bancos e à previdência; em registros de folha, o credor informado pode ser o próprio órgão. A página diz isso junto ao número e não desconta nenhuma parcela, porque só a modalidade 91 identifica essas operações de forma determinística. Na coleta de 12/11/2026 a modalidade 91 somou R$ 284,8 milhões em 1.405 registros, de um total de R$ 7,81 bilhões.

Até 12/11/2026 o CPF mascarado não era reconhecido, e os registros de pessoa física apareciam como “Recebedor não identificado”. A correção vale para os conjuntos coletados depois dela. Na recoleta feita em seguida, 19.205 registros (R$ 50,3 milhões) foram classificados como pessoa física e 944 (R$ 346,2 milhões) não traziam CPF nem CNPJ.

Pendências: valor por habitante (depende de registrar a população do IBGE como insumo externo) e identificação do recebedor por CNPJ, que tornaria o agrupamento exato mas depende da revisão de privacidade.

## Campos usados

| Campo da API | Uso e tratamento |
| --- | --- |
| `dataPagamento` | Data ISO. A coleta exige data no mês solicitado. |
| `valorPagamento` | Valor em reais. Lido como decimal, com até duas casas decimais. Zero é preservado. |
| `codUnidadeOrcamentaria`, `descUnidadeOrcamentaria` | Código e nome obrigatórios do órgão ou fundo que consta no registro. |
| `numeroPagamento` | Número obrigatório do documento, guardado como texto. Junto ao código da unidade, detecta repetição no conjunto importado. |
| `codNaturezaDespesa`, `descNaturezaDespesa`, `descTipoDespesa` | Classificação da fonte. A consulta conserva as linhas com natureza ausente e as reúne em “Tipo de despesa não informado”. Alguns códigos têm rótulos do portal junto ao nome oficial. |
| `cpfCnpjCredor`, `nomeCredor` | O identificador serve em memória para distinguir o formato de CPF ou CNPJ. A fonte envia o CPF mascarado (por exemplo `***.***.***-12`); esse formato também é tratado como pessoa física. O portal descarta o identificador e guarda o nome somente para formato de CNPJ. Pessoa física aparece com rótulo genérico. Quando o campo não traz CPF nem CNPJ, a página mostra “Não informado no registro”. |
| `numeroEmpenho`, `numeroLiquidacao` | Referências numéricas opcionais do registro. |
| `numeroProcesso`, `linkDeAcesso` | Referências opcionais exibidas para pessoas jurídicas. O link é reconstruído a partir da rota HTTPS conhecida do SEI de Roraima e seus parâmetros públicos de acesso. |
| `descPagamento` | Texto livre potencialmente identificável. O portal descarta o campo. |

Os identificadores pessoais e o conteúdo bruto da resposta ficam fora do banco e dos logs. Falhas registram etapa e classe do erro. A revisão de finalidade, retenção e aviso de privacidade descrita em [Dados e privacidade](dados-e-privacidade.md) permanece pendente para a operação pública.

## Áreas apresentadas

O agrupamento por área é uma classificação editorial do InspectGovRR baseada no código da unidade, conferido no cadastro de unidades da API e nos registros de Pagamento. A regra atual é para 2026. Cada cartão lista as unidades cobertas. “Outros órgãos” inclui as unidades importadas sem uma área definida na regra. “Todos os órgãos” inclui todas as unidades do conjunto. A composição por unidade não mede a função orçamentária da despesa.

Saúde inclui os códigos `20101` e `20601`. Na coleta de verificação, o Fundo Estadual de Saúde (`20601`) teve registros e a Secretaria de Estado da Saúde (`20101`) apareceu apenas no cadastro de unidades. O agrupamento mantém ambas à vista. Consulte [areas.py](../pagamentos/areas.py) para as unidades de Educação e Segurança Pública.

## Operação

Execute `python manage.py migrate` e depois `python manage.py sync_payments` no ambiente com acesso à API e ao banco. O comando usa o ano corrente e pode receber `--year` e `--month-end`. O início é janeiro. Uma coleta que cubra menos meses que a já publicada para o mesmo ano é rejeitada.

As exportações são carregadas mês a mês com limite de 32 MiB de JSON por mês. O banco recebe os registros em lotes no conjunto em preparação. O PostgreSQL impede coletas simultâneas para o mesmo ano com um lock de sessão. A publicação usa uma transação para trocar o conjunto ativo. Uma falha preserva o último conjunto publicado. A troca mantém os registros da versão imediatamente anterior para consultas que já estavam em andamento. As execuções ficam consultáveis no admin.

O agendamento diário usa `FIPLAN_PAYMENTS_AUTO_SYNC_ENABLED`, desligada por padrão. A duração da coleta e a latência da página no ambiente de publicação ainda precisam ser acompanhadas.
