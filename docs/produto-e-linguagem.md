# Produto, público e regras de linguagem

## Objetivo

O InspectGovRR transforma dados disponibilizados pela API de consultas do Portal da Transparência do Governo de Roraima (abreviada como “API Transparência RR” na interface) em páginas que uma pessoa sem formação em orçamento público consiga consultar. O portal é independente. Os registros têm origem governamental; seleção, agrupamento, cálculos, visualização e explicações são responsabilidade deste projeto.

O valor do sistema é responder perguntas concretas, como “quanto entrou?”, “quem recebe?” e “com quem o governo contratou?”, mostrando o período e a fonte de cada resposta. A consulta não deve exigir que a pessoa conheça os nomes dos endpoints ou termos como “unidade orçamentária”.

## Público e histórias de usuário

**Pessoa principal:** cidadã ou cidadão que usa mais o telefone que o computador, pode ter conexão lenta e não conhece a linguagem da administração pública. Também atendemos jornalistas, estudantes, pesquisadores e servidores, sem fazer a interface depender do conhecimento desses grupos.

| História | Aceitação observável |
| --- | --- |
| Como pessoa sem conhecimento técnico, quero começar por uma pergunta simples para encontrar o assunto certo. | A navegação usa perguntas e termos comuns; o nome oficial aparece como referência, com explicação acessível. |
| Como pessoa no celular, quero entender uma tabela sem ampliar a tela ou rolar horizontalmente. | Informações essenciais, período e fonte cabem e são legíveis em 320–390 px; detalhes podem ser distribuídos em cartões ou linhas. |
| Como pessoa com internet limitada, quero abrir a página sem baixar conteúdo desnecessário. | Conteúdo principal é HTML renderizado no servidor; recursos são pequenos, reutilizáveis e não exigem JavaScript. |
| Como pessoa que vê um número surpreendente, quero saber de onde ele veio e o que ele representa. | A página mostra a fonte, o período, a data da coleta, o recorte (por exemplo, Top 5) e o caminho para conferir o registro oficial quando existir. |
| Como pessoa que não encontrou resultados, quero saber se faltam registros importados, se meu filtro não retornou resultado ou se houve falha. | Cada situação recebe mensagem e próximo passo próprios; ausência de resultado nunca é descrita como ausência de gasto ou pagamento. |

## Regras de negócio e de redação

1. **A fonte deve ser rastreável.** Identifique “API Transparência RR” na interface, explique o nome completo no aviso de origem e, sempre que possível, indique o endpoint ou a documentação oficial. Não chame os cálculos do portal de “dados brutos do governo”.
2. **Não invente valores nem preencha lacunas com suposições.** Guarde apenas os campos necessários para consultas e relações previstas. Transformações determinísticas são permitidas com fórmula e recorte documentados. Se um campo vier nulo, apresente “não informado” em vez de zero, salvo quando a semântica da API justificar zero.
3. **Não faça imputações.** Valor alto, concentração, aditivo, remuneração ou diferença de datas não provam crime, fraude ou irregularidade. Evite selos de “suspeito” e frases que insinuem culpa. Ao destacar um valor, explique o recorte e hipóteses neutras compatíveis com os dados.
4. **Não transforme falta de dado em fato negativo.** “Não há dados importados para este período” é diferente de “não houve pagamento”. Em falha de coleta, mantenha o último conjunto válido e sinalize sua data.
5. **Explique unidades e limites.** Diferencie valor empenhado, liquidado e pago; contrato assinado e pagamento; remuneração bruta e líquida. Rankings Top 5 e Top 50 são amostras limitadas, não totais estaduais.
6. **Dê prioridade ao celular.** Use títulos curtos, texto direto, alvos de toque confortáveis, foco visível, contraste e HTML semântico. Confira largura de 320–390 px e 1440 px, inclusive estados vazios e valores longos.
7. **Evite custo desnecessário.** Não consulte a API externa durante a navegação. Paginação, consultas ao banco, imagens, fontes e scripts devem ser avaliados pelo efeito em aparelhos modestos e redes lentas.

## Linguagem recomendada

| Evite | Prefira |
| --- | --- |
| “Órgão não arrecadou” quando não há snapshot | “Ainda não há dados importados para este período.” |
| “Fornecedor suspeito” | “Fornecedor com maior valor contratado neste recorte.” |
| “O governo gastou R$ X” quando o campo é valor contratado | “O valor contratado foi de R$ X; pagamento é uma etapa diferente.” |
| “Dados sem alterações” | “Registros da API organizados e, quando indicado, calculados pelo portal.” |

As explicações de `portal/glossary.py` e o catálogo `portal/modules.py` são os pontos de manutenção da linguagem comum. Uma explicação contextual deve ser claramente geral quando o endpoint não detalha a origem de um valor.
