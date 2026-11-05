# Processo de Validação de Skills — Claude Code

## 1. Objetivo

Este documento define o processo de validação utilizado pelo Skill Create para verificar a estrutura, o comportamento, a segurança e a qualidade de Skills para Claude Code.

A validação deve produzir evidências verificáveis.

Nunca declarar que uma Skill foi testada ou aprovada sem evidências suficientes.

O idioma dos relatórios segue a regra do `SKILL.md` (pt-BR).

## 2. Princípios de validação

Toda validação deve seguir estes princípios:

1. Definir o resultado esperado antes de executar o teste.
2. Utilizar cenários representativos.
3. Separar inspeção estática de execução real.
4. Registrar falhas e limitações.
5. Evitar alterações desnecessárias no ambiente.
6. Não inventar resultados.
7. Repetir testes relevantes após correções.
8. Priorizar riscos de segurança.

A profundidade da validação deve ser proporcional à complexidade e aos riscos da Skill.

### Versão completa e versão reduzida

- **Completa:** todas as etapas da seção 3 e os cinco cenários de acionamento (A a E). Obrigatória para Skills que executam comandos, alteram arquivos, acessam serviços externos ou manipulam dados sensíveis.
- **Reduzida:** permitida para Skills simples, somente de instruções e sem operações de risco. Inclui a validação estrutural pelo script, a validação semântica e, no mínimo, os cenários A (acionamento direto), B (indireto) e C (não acionamento).

Ao usar a versão reduzida, registrar essa escolha e os cenários omitidos no relatório.

## 3. Etapas de validação

O processo possui cinco etapas:

1. Validação estrutural.
2. Validação semântica.
3. Validação de acionamento.
4. Validação comportamental.
5. Validação de segurança.

Após essas etapas, produzir um relatório consolidado.

## 4. Validação estrutural

Verificar a organização e a integridade dos arquivos.

### Validação automatizada

Executar, a partir do diretório da Skill `skill-create`:

    python3 scripts/validar-skill.py <caminho-da-skill-avaliada> [--estrito] [--biblioteca]

Opções:

- `--estrito`: trata avisos como erros.
- `--biblioteca`: aplica o padrão da biblioteca pessoal e exige `examples/como-usar.md`. Usar em toda Skill criada pela `skill-create` e em Skills da biblioteca mantidas por ela. Não usar para avaliar Skills de terceiros ou de plugins, para as quais só o `SKILL.md` é obrigatório.

O script verifica: existência do `SKILL.md`; frontmatter na primeira linha (sem linha em branco ou BOM antes); fechamento do frontmatter; presença e tamanho da `description`; formato do `name`; propriedades desconhecidas; tamanho do `SKILL.md`; existência dos arquivos referenciados em `references/`, `scripts/`, `assets/` e `evals/`; arquivos e diretórios vazios; padrões de comandos perigosos (somente sinalizados para revisão manual); e o guia `examples/como-usar.md`.

Verificações do guia:

| Verificação | Com `--biblioteca` | Sem `--biblioteca` |
|---|---|---|
| Arquivo ausente | ERRO | Não verificado (OK informativo) |
| Arquivo vazio, seção mínima ausente ou sem conteúdo | ERRO | AVISO |
| Invocação `/nome-da-skill` não mencionada | ERRO | AVISO |
| Três ou mais linhas longas idênticas ao `SKILL.md` | AVISO | AVISO |

As seções mínimas (objetivo, como invocar, exemplos de solicitações, entradas, resultados esperados, dependências e pré-requisitos, limitações conhecidas) são reconhecidas por palavras-chave nos títulos `##` e `###`, sem diferenciar acentos ou maiúsculas. O modelo está em `references/padroes-qualidade.md` §6.

Códigos de saída: `0` sem erros, `1` com erros (ou avisos no modo `--estrito`), `2` uso incorreto. Requer apenas Python 3 (biblioteca padrão).

O script não valida YAML complexo (listas e blocos aninhados são aceitos sem verificação detalhada) nem a qualidade das instruções. No guia, verifica apenas a presença das seções e da invocação: o idioma, a exatidão dos exemplos e a ausência de duplicação além de linhas idênticas exigem inspeção. Os itens abaixo continuam exigindo inspeção.

### Checklist

- O arquivo `SKILL.md` existe?
- O frontmatter começa com `---` na primeira linha e está sintaticamente correto?
- O campo `description` está presente?
- As propriedades utilizadas são suportadas?
- Os arquivos referenciados existem?
- Os caminhos relativos estão corretos?
- Existem dependências não documentadas?
- Existem arquivos ou diretórios desnecessários?
- No padrão da biblioteca: `examples/como-usar.md` existe, está em pt-BR, é coerente com o `SKILL.md` (comando, entradas, limites) e se dirige ao usuário sem copiar as instruções?

### Resultado

Registrar cada verificação como:

- Aprovado.
- Reprovado.
- Não executado.
- Bloqueado.

Quando uma verificação falhar, explicar o motivo.

## 5. Validação semântica

Analisar a qualidade e a consistência das instruções.

### Verificações

- O objetivo está claramente definido?
- As responsabilidades são coerentes?
- O escopo está delimitado?
- As instruções são executáveis?
- Existem regras contraditórias?
- As entradas necessárias estão identificadas?
- As saídas esperadas estão definidas?
- Existem orientações para tratamento de erros?
- As instruções respeitam o idioma obrigatório?

### Regras

Não considerar uma instrução adequada apenas porque está bem escrita.

Verificar se ela realmente descreve um comportamento executável e relevante.

## 6. Validação de acionamento

Verificar se a Skill é utilizada nos contextos corretos.

### Cenário A — Acionamento direto

Criar uma solicitação que mencione explicitamente a função da Skill.

Exemplo:

"Utilize a Skill de revisão PHP para analisar este arquivo."

Resultado esperado:

A Skill deve ser selecionada ou invocada quando disponível e autorizada.

### Cenário B — Acionamento indireto

Criar uma solicitação que esteja dentro do escopo, mas não mencione o nome da Skill.

Exemplo:

"Analise este código PHP e identifique possíveis problemas de segurança."

Resultado esperado:

O Claude deve reconhecer a relevância da Skill quando o acionamento automático estiver habilitado.

### Cenário C — Não acionamento

Criar uma solicitação semelhante, mas fora do escopo.

Exemplo:

"Explique como funciona uma variável em PHP."

Resultado esperado:

A Skill especializada em revisão de código não deve ser acionada desnecessariamente.

### Cenário D — Solicitação ambígua

Criar uma solicitação com informações insuficientes.

Exemplo:

"Analise meu projeto."

Resultado esperado:

O Claude deve identificar as informações essenciais ausentes antes de executar ações inadequadas.

### Cenário E — Falha ou exceção

Criar uma situação com arquivo ausente, dependência indisponível ou erro operacional.

Resultado esperado:

A Skill deve informar o problema e orientar a recuperação sem inventar resultados.

### Como executar os testes de acionamento

O acionamento depende da listagem de Skills carregada no início da sessão. Por isso, os testes devem rodar em uma **sessão nova**, depois que a Skill estiver instalada, nunca na sessão em que ela foi criada ou alterada.

1. Confirmar a instalação: a Skill deve aparecer com a `description` correta na listagem de Skills (se aparecer `---` ou um texto do corpo, o frontmatter não foi lido).
2. Executar cada cenário em modo não interativo, a partir de um diretório temporário, registrando os eventos:

        claude -p "<pedido do cenário>" --output-format stream-json --verbose --max-turns 2 > resultado.jsonl

3. Verificar se houve invocação da Skill, procurando um uso da ferramenta `Skill` com o nome esperado:

        grep -o '"name":"Skill","input":{[^}]*}' resultado.jsonl

4. Registrar o trecho encontrado (ou sua ausência) como evidência.

Observações:

- Cada execução consome uso da conta. Informar o usuário antes de rodar uma bateria de testes.
- O acionamento é probabilístico. Para cenários críticos, repetir algumas vezes e registrar a taxa de acerto.
- Se `claude -p` não estiver disponível, usar um subagent sem contexto da conversa ou pedir ao usuário que teste em uma sessão nova; caso contrário, registrar o cenário como **Bloqueado**.
- Não executar em modo não interativo cenários que possam realizar operações destrutivas.

### Observação

Quando a Skill for configurada para acionamento exclusivamente manual, adaptar os testes à sua configuração.

Não reprovar uma Skill por não ser acionada automaticamente quando isso não fizer parte de seu comportamento esperado.

## 7. Validação comportamental

Verificar se a Skill produz os resultados esperados.

Para cada cenário, registrar:

- Identificador.
- Objetivo.
- Entrada.
- Pré-condições.
- Comportamento esperado.
- Resultado esperado.
- Resultado observado.
- Situação.
- Evidências.

### Modelo de caso de teste

    ID: TESTE-001

    Objetivo:
    Verificar o comportamento principal da Skill.

    Entrada:
    Solicitação representativa do usuário.

    Pré-condições:
    Skill instalada e disponível.

    Comportamento esperado:
    Executar o fluxo principal definido.

    Resultado esperado:
    Produzir a saída especificada.

    Resultado observado:
    Preencher somente após a execução.

    Situação:
    Não executado.

    Evidências:
    Registrar logs, arquivos ou resultados relevantes.

### Critério de aprovação

Um teste somente será aprovado quando o resultado observado atender aos critérios definidos.

Não preencher resultados observados com suposições.

## 8. Validação de segurança

Avaliar os riscos associados à execução da Skill.

### Permissões

Verificar se a Skill solicita apenas os acessos necessários.

### Arquivos

Verificar se existem operações capazes de apagar, sobrescrever ou modificar arquivos indevidamente.

### Comandos

Identificar comandos destrutivos, perigosos ou irreversíveis.

### Credenciais

Verificar possíveis exposições de:

- Senhas.
- Tokens.
- Chaves privadas.
- Variáveis sensíveis.
- Informações confidenciais.

### Dependências externas

Avaliar riscos associados a bibliotecas, scripts e serviços externos.

### Instruções não confiáveis

Verificar se conteúdos externos podem tentar alterar indevidamente o comportamento da Skill.

### Aprovação

Uma falha crítica de segurança impede a aprovação da Skill até sua correção.

## 9. Execução dos testes

Antes de executar:

1. Verificar o ambiente.
2. Confirmar as dependências.
3. Identificar possíveis efeitos colaterais.
4. Preparar entradas de teste.
5. Definir resultados esperados.

Durante a execução:

1. Executar o cenário.
2. Observar o comportamento.
3. Registrar resultados.
4. Registrar falhas.
5. Preservar evidências relevantes.

Após a execução:

1. Comparar resultados.
2. Classificar a situação.
3. Identificar causas de falhas.
4. Recomendar correções.
5. Repetir testes quando necessário.

Não executar testes destrutivos em ambientes de produção.

## 10. Classificação dos resultados

Utilizar quatro situações:

### Aprovado

O teste foi executado e atendeu aos critérios definidos.

### Reprovado

O teste foi executado, mas não atendeu aos critérios.

### Não executado

O teste foi definido, mas não foi executado.

### Bloqueado

O teste não pôde ser executado devido a uma dependência, permissão ou condição ausente.

Não utilizar "Aprovado" quando o teste não tiver sido executado.

## 11. Tratamento de falhas

Quando um teste falhar:

1. Identificar o comportamento incorreto.
2. Comparar com o resultado esperado.
3. Investigar a causa.
4. Classificar a gravidade.
5. Propor uma correção.
6. Aplicar a correção quando autorizado.
7. Executar novamente o teste.
8. Verificar possíveis regressões.

Evitar correções que aumentem desnecessariamente a complexidade.

## 12. Testes de regressão

Após modificar uma Skill existente, verificar se os comportamentos anteriores continuam funcionando.

Priorizar:

- Fluxo principal.
- Condições de acionamento.
- Formatos de saída.
- Tratamento de erros.
- Permissões e segurança.

Não considerar uma melhoria concluída se ela comprometer funcionalidades essenciais.

## 13. Avaliação de qualidade

Após as validações, pontuar as seis dimensões conforme `references/padroes-qualidade.md` §12 a §14 (escala, classificação e modelo de tabela).

Não utilizar a pontuação como substituto dos testes.

## 14. Relatório final

Produzir um relatório contendo:

### Identificação

- Nome da Skill.
- Objetivo.
- Localização.
- Data da avaliação, quando disponível.

### Resumo

- Total de verificações.
- Testes aprovados.
- Testes reprovados.
- Testes não executados.
- Testes bloqueados.

### Problemas encontrados

Para cada problema:

- Descrição.
- Gravidade.
- Evidência.
- Impacto.
- Correção recomendada.

### Qualidade

- Pontuação por dimensão.
- Pontuação total.
- Classificação.
- Justificativas.

### Conclusão

Utilizar uma das classificações:

- **Aprovada:** validações obrigatórias concluídas, sem falhas impeditivas.
- **Aprovada com ressalvas:** validações essenciais concluídas, com limitações não críticas documentadas.
- **Reprovada:** falhas impeditivas identificadas.
- **Pendente de validação:** evidências insuficientes para aprovação.

Nunca classificar uma Skill como aprovada quando houver uma falha crítica conhecida.

## 15. Critérios de conclusão

O processo de validação estará concluído quando:

1. As verificações aplicáveis forem realizadas.
2. Os resultados forem registrados.
3. As falhas forem documentadas.
4. Os riscos forem avaliados.
5. As limitações forem apresentadas.
6. O relatório final estiver disponível.

Caso existam testes pendentes, indicar claramente quais são.

## 16. Diretriz final

O objetivo da validação não é apenas encontrar erros.

É produzir evidências de que a Skill atende à sua finalidade, respeita seus limites e apresenta comportamento confiável.

Nunca confundir uma implementação aparentemente correta com uma implementação comprovadamente funcional.
