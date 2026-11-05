# Padrões de Qualidade para Skills

## 1. Objetivo

Este documento estabelece os padrões de qualidade que devem ser aplicados durante a criação, revisão e melhoria de Skills para Claude Code.

Toda Skill deve ser útil, especializada, clara, eficiente, segura, testável e fácil de manter.

O idioma segue a regra do `SKILL.md` (pt-BR).

## 2. Responsabilidade única

Cada Skill deve possuir uma responsabilidade principal claramente definida.

### Boas práticas

- Definir um objetivo específico.
- Delimitar o escopo.
- Identificar entradas e saídas.
- Evitar funcionalidades independentes.
- Separar responsabilidades quando necessário.

### Evitar

- Skills genéricas que tentam resolver qualquer problema.
- Misturar funcionalidades sem relação.
- Instruções que extrapolem o objetivo principal.
- Dependências desnecessárias entre Skills.

## 3. Qualidade das instruções

As instruções devem ser:

- Claras.
- Objetivas.
- Executáveis.
- Consistentes.
- Organizadas.
- Verificáveis.

### Instruções inadequadas

"Analise o código cuidadosamente."

"Produza um resultado de alta qualidade."

"Utilize as melhores práticas."

Essas instruções são vagas e não definem ações verificáveis.

### Instruções adequadas

"Identifique consultas SQL sem filtros seletivos e explique os possíveis impactos no desempenho."

"Verifique se existem credenciais expostas nos arquivos analisados."

"Classifique os problemas identificados por gravidade e apresente recomendações justificadas."

Prefira instruções que indiquem exatamente o comportamento esperado.

## 4. Qualidade dos metadados

O frontmatter YAML deve começar na primeira linha do arquivo, ser válido e utilizar apenas as propriedades listadas em `references/arquitetura.md` §7.

### Nome

O nome deve:

- Ser curto.
- Ser descritivo.
- Utilizar kebab-case.
- Evitar ambiguidades.
- Representar a responsabilidade da Skill.

### Descrição

A descrição deve responder:

1. O que a Skill faz?
2. Quando deve ser utilizada?
3. Quais solicitações ou contextos justificam seu acionamento?

### Exemplo

    ---
    name: sql-performance
    description: Analisa consultas SQL para identificar problemas de desempenho, índices e planos de execução. Utilize quando o usuário solicitar otimização de queries ou análise de consultas lentas.
    ---

Evite descrições excessivamente genéricas.

Inclua exemplos de pedidos que devem acionar a Skill e, quando houver Skills parecidas, o que a diferencia.

Não utilize propriedades de configuração sem verificar seu suporte.

## 5. Eficiência de contexto

O `SKILL.md` deve conter apenas as instruções necessárias para orientar a execução.

### Boas práticas

- Evitar repetição de regras.
- Utilizar referências para documentação extensa.
- Carregar arquivos complementares sob demanda.
- Manter exemplos curtos e relevantes.
- Evitar explicações conceituais desnecessárias.
- Manter o `SKILL.md` com menos de 500 linhas.

### Evitar

- Repetir as mesmas instruções em vários arquivos.
- Incluir documentação completa de ferramentas.
- Criar referências que nunca serão utilizadas.
- Carregar todos os documentos em todas as execuções.

A quantidade de arquivos não é um indicador de qualidade.

## 6. Organização dos arquivos

Utilize uma estrutura proporcional à complexidade da Skill. No padrão da biblioteca, toda estrutura inclui `examples/como-usar.md` (ver "Guia de uso" abaixo).

### Skill simples

    nome-da-skill/
    ├── SKILL.md
    └── examples/
        └── como-usar.md

### Skill com documentação complementar

    nome-da-skill/
    ├── SKILL.md
    ├── examples/
    │   └── como-usar.md
    └── references/
        └── documentacao.md

### Skill com automação e testes

    nome-da-skill/
    ├── SKILL.md
    ├── examples/
    ├── references/
    ├── scripts/
    └── evals/

Não crie diretórios vazios apenas para seguir um modelo.

Cada arquivo deve possuir uma finalidade identificável.

### Guia de uso (padrão da biblioteca)

O `examples/como-usar.md` é obrigatório para Skills criadas ou mantidas sob o padrão da biblioteca pessoal. Para o Claude Code, continua opcional: uma Skill sem ele funciona normalmente.

Público e finalidade: o `SKILL.md` orienta o comportamento do Claude; o guia orienta a pessoa que vai usar a Skill. O guia:

- É escrito integralmente em pt-BR, preservando comandos, nomes de arquivos, propriedades e demais identificadores técnicos.
- Explica o que a pessoa faz e o que ela recebe, sem repetir regras, fluxos internos ou critérios de decisão do `SKILL.md`. Quando um detalhe for necessário, resumir em uma frase.
- Usa exemplos realistas e coerentes com o escopo e os limites da Skill; nunca promete o que a Skill não faz.
- Não contém credenciais, hosts internos ou dados pessoais reais.

Seções mínimas (verificadas por `scripts/validar-skill.py --biblioteca` pelos títulos `##`/`###`, que devem ter conteúdo):

| Seção | Conteúdo |
|---|---|
| Objetivo | Problema que a Skill resolve e para que serve. |
| Como invocar | Comando `/nome-da-skill` com argumentos, acionamento automático (se houver) e instalação. |
| Exemplos de solicitações | Pedidos práticos, cobrindo os usos principais. |
| Entradas e resultados esperados | O que a pessoa precisa fornecer e o que recebe (arquivos, relatórios, respostas). |
| Dependências e pré-requisitos | Ferramentas, bibliotecas e configurações; se não houver, declarar "Nenhuma além do Claude Code". |
| Limitações conhecidas | O que a Skill não faz e casos em que pode falhar. |

Seções extras, como problemas comuns, são permitidas quando úteis.

Modelo:

    # Como usar a Skill <nome-da-skill>

    ## Objetivo

    <Uma ou duas frases: o problema que a Skill resolve e para que serve.>

    ## Como invocar

    ```text
    /nome-da-skill <argumentos>
    ```

    <Acionamento automático, se houver, e como instalar.>

    ## Exemplos de solicitações

    ```text
    /nome-da-skill <pedido prático>
    ```

    ## Entradas e resultados esperados

    - **Entradas:** <o que a pessoa fornece>.
    - **Resultados:** <o que a Skill entrega>.

    ## Dependências e pré-requisitos

    - <Ferramenta ou "Nenhuma além do Claude Code".>

    ## Limitações conhecidas

    - <O que não faz ou onde pode falhar.>

## 7. Qualidade dos scripts

Quando uma Skill utilizar scripts:

- Utilize nomes descritivos.
- Documente os parâmetros.
- Valide as entradas.
- Trate erros previsíveis.
- Evite dependências desnecessárias.
- Utilize códigos de saída adequados.
- Não exponha credenciais.
- Evite alterações destrutivas por padrão.

Sempre que possível, permita executar validações sem modificar os arquivos analisados.

Não considere um script funcional sem executá-lo ou registrar explicitamente que não foi testado.

## 8. Segurança

Toda Skill deve respeitar o princípio do menor privilégio.

### Verificações obrigatórias

- A Skill solicita apenas permissões necessárias?
- Existem comandos destrutivos?
- Existem alterações irreversíveis?
- Há risco de exposição de informações sensíveis?
- Existem dependências externas não confiáveis?
- A Skill modifica arquivos sem autorização?
- Há risco de execução de instruções provenientes de fontes não confiáveis?

### Operações sensíveis

Solicite confirmação apropriada antes de:

- Excluir arquivos importantes.
- Sobrescrever informações sem recuperação segura.
- Modificar ambientes de produção.
- Executar operações destrutivas em bancos de dados.
- Alterar permissões sensíveis.
- Enviar informações confidenciais para serviços externos.

Nunca inclua senhas, tokens ou credenciais reais nos arquivos gerados.

## 9. Qualidade das saídas

Toda Skill deve definir o resultado esperado.

Quando aplicável, estabeleça:

- Formato de resposta.
- Informações obrigatórias.
- Organização dos resultados.
- Critérios de classificação.
- Tratamento de informações ausentes.
- Indicação de limitações.

Evite exigir relatórios extensos para tarefas simples.

A resposta deve ser proporcional à complexidade da solicitação.

## 10. Tratamento de erros

As instruções devem prever falhas relevantes.

Quando ocorrer um erro:

1. Identifique a operação que falhou.
2. Apresente a causa conhecida.
3. Não invente explicações.
4. Preserve os dados existentes.
5. Sugira ou execute uma correção segura quando autorizado.
6. Informe se a tarefa permanece incompleta.

Não ignore falhas para produzir uma aparência de sucesso.

## 11. Manutenibilidade

Uma Skill deve permitir alterações futuras sem exigir reestruturação completa.

### Boas práticas

- Separar responsabilidades.
- Utilizar nomes consistentes.
- Evitar duplicação.
- Documentar dependências.
- Manter referências atualizadas.
- Preservar compatibilidade quando possível.
- Revisar instruções obsoletas.

### Evitar

- Regras contraditórias.
- Dependências ocultas.
- Arquivos sem finalidade.
- Instruções que dependem de caminhos locais fixos sem justificativa.
- Configurações não documentadas.

## 12. Avaliação de qualidade

Avalie cada Skill em seis dimensões.

Atribua uma pontuação de 0 a 5 para cada dimensão.

### 12.1. Responsabilidade

Avalie se a Skill possui um objetivo claro e escopo delimitado.

### 12.2. Precisão de acionamento

Avalie se a descrição permite identificar corretamente quando a Skill deve ou não ser utilizada.

### 12.3. Clareza das instruções

Avalie se as instruções são consistentes, específicas e executáveis.

### 12.4. Eficiência de contexto

Avalie se a Skill evita informações desnecessárias e utiliza referências de maneira adequada.

### 12.5. Segurança

Avalie se as permissões, operações e riscos são tratados corretamente.

### 12.6. Testabilidade

Avalie se existem critérios objetivos e cenários capazes de verificar o comportamento.

## 13. Escala de pontuação

Utilize a seguinte interpretação:

- **0:** Critério ausente ou completamente inadequado.
- **1:** Problemas críticos.
- **2:** Problemas significativos.
- **3:** Atende parcialmente, com melhorias necessárias.
- **4:** Atende bem ao critério.
- **5:** Atende plenamente, com evidências suficientes.

Pontuação máxima: 30 pontos.

### Classificação final

- **27 a 30:** Excelente.
- **23 a 26:** Boa.
- **18 a 22:** Necessita melhorias.
- **Abaixo de 18:** Necessita revisão arquitetural.

Esta classificação é uma convenção interna do projeto.

Não representa uma certificação oficial da Anthropic.

Uma falha crítica de segurança impede a aprovação independentemente da pontuação.

## 14. Relatório de qualidade

Ao revisar ou validar uma Skill, apresente:

| Dimensão | Pontuação | Justificativa |
|---|---|---|
| Responsabilidade | 0–5 | Evidências encontradas |
| Acionamento | 0–5 | Evidências encontradas |
| Clareza | 0–5 | Evidências encontradas |
| Eficiência | 0–5 | Evidências encontradas |
| Segurança | 0–5 | Evidências encontradas |
| Testabilidade | 0–5 | Evidências encontradas |

Inclua:

- Pontuação total.
- Classificação.
- Problemas identificados.
- Recomendações prioritárias.
- Riscos restantes.
- Limitações da avaliação.

Não atribua pontuação máxima automaticamente a uma Skill recém-criada.

## 15. Critérios mínimos de aprovação

Uma Skill somente poderá ser considerada aprovada quando:

1. Possuir objetivo claro.
2. Apresentar metadados válidos.
3. Possuir instruções consistentes.
4. Definir condições de acionamento adequadas.
5. Não apresentar falhas críticas de segurança conhecidas.
6. Possuir os arquivos necessários, incluindo `examples/como-usar.md` no padrão da biblioteca.
7. Apresentar critérios de aceitação verificáveis.
8. Ter passado pelas validações obrigatórias disponíveis.

Caso existam testes não executados, informe essa limitação.

## 16. Princípio final

Qualidade não significa complexidade.

Uma Skill bem construída deve resolver seu problema com o menor conjunto de instruções, arquivos e dependências necessário.

Priorize sempre clareza, confiabilidade, segurança e manutenção.
