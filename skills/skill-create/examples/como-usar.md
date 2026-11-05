# Como usar a Skill Create

## Objetivo

A `skill-create` ajuda você a criar, revisar, melhorar e testar Skills para Claude Code. Ela conduz o trabalho do levantamento de requisitos até a validação, para que cada Skill da biblioteca saia com escopo claro, estrutura válida, cenários de teste e um guia de uso como este. Toda a comunicação e a documentação gerada ficam em português brasileiro (pt-BR).

## Como invocar

Abra o Claude Code no projeto em que você vai trabalhar:

```bash
claude
```

Digite o comando, com ou sem um pedido:

```text
/skill-create [criar|revisar|melhorar|testar] <descrição ou caminho da Skill>
```

Sem argumentos, o Claude pergunta se você quer criar, revisar, melhorar ou testar uma Skill.

A Skill também pode ser acionada automaticamente quando você fala de Skills sem citar o comando, por exemplo: "minha skill não está sendo acionada, por quê?".

### Instalação

Criar uma pasta no repositório **não instala** a Skill no Claude Code. Para disponibilizá-la em todos os projetos, crie um link simbólico depois de conferir que o destino ainda não existe:

```bash
ls -la ~/.claude/skills/
mkdir -p ~/.claude/skills
ln -s /CAMINHO/ABSOLUTO/claude-skills/skills/skill-create ~/.claude/skills/skill-create
```

Substitua `/CAMINHO/ABSOLUTO/` pelo caminho real. Para usar apenas em um projeto, coloque a Skill em `.claude/skills/` desse projeto.

## Exemplos de solicitações

### Criar uma Skill

```text
/skill-create Crie uma Skill para revisar código PHP 8.2, identificando problemas de segurança e desempenho.
```

Com requisitos mais completos:

```text
/skill-create Quero uma Skill chamada sql-performance para revisar consultas MariaDB. Ela deve analisar queries e planos EXPLAIN, sugerir índices e nunca alterar o banco. Crie-a no repositório claude-skills e apresente testes de exemplo.
```

### Revisar uma Skill

```text
/skill-create Revise a Skill em skills/skill-create. Avalie acionamento, clareza, segurança e eficiência. Não altere arquivos.
```

Revisar não significa editar: você recebe problemas, recomendações justificadas e uma pontuação de qualidade.

### Melhorar uma Skill

```text
/skill-create Melhore a Skill em skills/sql-performance. Reduza instruções repetidas sem mudar o comportamento e execute as validações disponíveis.
```

### Testar uma Skill

```text
/skill-create Teste a Skill em skills/skill-create. Verifique estrutura, acionamento e comportamento. Separe testes executados dos não executados.
```

### Diagnosticar acionamento

```text
Minha skill em ~/.claude/skills/deploy não está sendo acionada automaticamente, por quê?
```

## Entradas e resultados esperados

**Entradas:**

- O modo desejado (criar, revisar, melhorar ou testar). Se você não disser, o Claude pergunta.
- Para criar: o problema que a Skill vai resolver, quem vai usá-la e o que ela deve ou não fazer. O Claude pergunta apenas o que faltar e mudar o resultado.
- Para revisar, melhorar ou testar: o caminho da Skill.
- Opcionalmente: onde criar a Skill e restrições ("não altere arquivos", "não instale").

**Resultados:**

| Modo | Você recebe |
|---|---|
| Criar | Planejamento, arquivos da Skill (`SKILL.md`, `examples/como-usar.md` e, quando necessário, `references/`, `scripts/`, `evals/`), validação e instruções de uso |
| Revisar | Relatório de problemas, recomendações e pontuação de qualidade, sem alterar arquivos |
| Melhorar | Arquivos ajustados, comportamento preservado e validações repetidas |
| Testar | Relatório com cada teste classificado como **Aprovado**, **Reprovado**, **Não executado** ou **Bloqueado** |

Toda Skill criada segue o padrão da biblioteca: além do `SKILL.md`, inclui um `examples/como-usar.md` com objetivo, invocação, exemplos, entradas e resultados, dependências e limitações.

### Exemplo de conversa

**Você:**

```text
/skill-create Quero criar uma Skill para documentar APIs REST.
```

**Claude (comportamento esperado):**

1. Pergunta quais linguagens ou frameworks serão atendidos, se isso for essencial.
2. Confirma o formato de saída esperado (por exemplo, Markdown ou OpenAPI).
3. Propõe nome, escopo e arquivos necessários.
4. Cria os arquivos, incluindo o guia de uso, após obter as autorizações aplicáveis.
5. Valida a estrutura e informa quais testes foram efetivamente executados.

### Onde as novas Skills ficam

Neste repositório, as Skills ficam em `skills/`:

```text
claude-skills/
└── skills/
    ├── skill-create/
    ├── sql-performance/
    └── php-code-review/
```

Em outros projetos, o Claude pergunta se a Skill deve ser pessoal (`~/.claude/skills/`), do projeto (`.claude/skills/`) ou de um plugin.

## Dependências e pré-requisitos

- Claude Code instalado e autenticado.
- A Skill instalada em `~/.claude/skills/skill-create` ou em `.claude/skills/skill-create` (ver "Instalação").
- Python 3 para a validação estrutural automática. Sem ele, a validação é feita apenas por inspeção.
- Para testes de acionamento em sessão nova: o comando `claude -p` disponível. Cada execução consome uso da sua conta.

## Limitações conhecidas

- A validação automática verifica estrutura (frontmatter, arquivos referenciados, seções do guia), não a qualidade das instruções. A análise do conteúdo é feita pelo Claude e pode precisar da sua revisão.
- O acionamento automático é probabilístico. Um teste aprovado uma vez não garante o mesmo resultado sempre.
- Testes de acionamento só valem em uma sessão nova, depois de a Skill estar instalada; não na sessão em que ela foi criada.
- A pontuação de qualidade é uma convenção deste repositório, não uma certificação oficial.
- A Skill não instala nada nem cria links simbólicos sem sua autorização, e não executa operações destrutivas em nome da Skill que está sendo criada.
- Não serve para dúvidas gerais de programação nem para configurar hooks, settings ou `CLAUDE.md` sem relação com Skills.

## Problemas comuns

### `/skill-create` não aparece

Confira se o caminho existe e se há um `SKILL.md` válido dentro dele:

```bash
ls -l ~/.claude/skills/skill-create
```

Reinicie a sessão do Claude Code se necessário.

### A Skill não é acionada automaticamente

Revise a `description` no frontmatter do `SKILL.md`: ela deve explicar o que a Skill faz e quando usá-la. Verifique também se o arquivo começa com `---` na primeira linha.

### A Skill quer criar arquivos fora do repositório

Informe o destino explicitamente:

```text
Crie em ~/www/claude-skills/skills/ e não instale globalmente sem minha confirmação.
```

### Os testes não foram executados

Peça um relatório que diferencie verificações estáticas de testes reais e explique bloqueios ou dependências ausentes.

## Referência

Documentação oficial: https://code.claude.com/docs/en/skills
