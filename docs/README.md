# Guia do projeto para pessoas e assistentes de IA

Este diretório registra as decisões que devem orientar qualquer mudança no InspectGovRR. Leia o [README principal](../README.md) para instalação, operação e arquitetura existente. Leia o [design system](design-system.md) antes de alterar a interface.

| Documento | Para que serve |
| --- | --- |
| [Produto e linguagem](produto-e-linguagem.md) | Objetivo, público, histórias de usuário, regras de conteúdo e critérios de aceitação. |
| [Dados e privacidade](dados-e-privacidade.md) | Origem, transformações, dicionário, limites dos conjuntos e revisão de LGPD. |
| [Engenharia e operação](engenharia-e-operacao.md) | Estrutura do código, comentários, testes, performance, erros, fallback e auditoria. |
| [Design system](design-system.md) | Componentes, estilos, acessibilidade e responsividade já usados. |

## Como usar estes documentos

1. Antes de mudar uma tela ou coleta, identifique a fonte, o período, o limite e os campos pessoais afetados.
2. Diferencie **estado atual** de **regra para novas mudanças** e **pendência**. Uma regra documentada não significa que todo o código já a cumpre.
3. Se a API não fornecer um dado ou a sua definição, não o deduza como fato. Uma métrica calculada pode ser publicada quando a fórmula, o recorte e a fonte dos insumos forem claros.
4. Preserve a distinção entre dado oficial, transformação do portal e explicação editorial. Não apresente interpretação como registro do governo. Use “API Transparência RR” na interface como abreviação da API de consultas do Portal da Transparência do Governo de Roraima.
5. Em cada entrega, informe o que mudou, o que foi testado, os riscos de dados, privacidade e performance e o que ficou pendente.

## Critério de pronto para mudanças

- A página funciona em tela estreita, com teclado e sem depender de JavaScript para ler a informação principal.
- O período, a última atualização, a fonte e o alcance dos dados são compreensíveis.
- Ausência de dados, erro de filtro e indisponibilidade têm mensagens diferentes e não atribuem culpa à pessoa usuária.
- Mudanças de coleta têm testes de payload válido, inválido e incompleto; um erro não publica um conjunto parcial como completo.
- Campos pessoais, logs e novos cruzamentos de dados passaram pela revisão de [privacidade](dados-e-privacidade.md).
- A revisão humana recebe um resumo dos riscos concretos de correção, disponibilidade e desempenho.
