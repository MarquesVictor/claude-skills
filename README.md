# Claude Skills

Repositório pessoal dedicado ao desenvolvimento, organização e versionamento de **Skills para Claude Code**.

O objetivo é construir uma biblioteca de Skills reutilizáveis que permitam especializar o Claude Code em diferentes tarefas, automatizar processos e padronizar fluxos de trabalho.

## Objetivos

- Criar Skills especializadas para diferentes necessidades.
- Padronizar a estrutura e a qualidade das Skills.
- Manter o histórico de alterações utilizando Git.
- Facilitar a instalação e reutilização em diferentes projetos.
- Documentar e validar o comportamento das Skills.

## Estrutura do repositório

```text
claude-skills/
├── README.md
├── .gitignore
└── skills/
    └── skill-create/
        ├── SKILL.md
        ├── examples/
        ├── references/
        ├── scripts/
        └── evals/
```

Toda Skill da biblioteca inclui `examples/como-usar.md`, um guia prático de utilização em pt-BR. Para o Claude Code, apenas o `SKILL.md` é obrigatório.

A estrutura será expandida conforme novas Skills forem desenvolvidas.

## Skills disponíveis

### skill-create

**Status:** Em desenvolvimento.

Skill especializada na criação, revisão, melhoria e validação de outras Skills para Claude Code.

Principais funcionalidades:

- Levantamento de requisitos.
- Planejamento da arquitetura.
- Geração de arquivos `SKILL.md`.
- Organização de documentação complementar.
- Validação estrutural e comportamental.
- Avaliação de qualidade e segurança.

**Comando de utilização:**

```text
/skill-create
```

## Instalação

As Skills poderão ser instaladas no Claude Code por meio de links simbólicos, permitindo utilizar diretamente os arquivos versionados neste repositório.

As instruções específicas de instalação serão adicionadas após a implementação inicial.

## Padrões

- Documentação e instruções em português brasileiro (pt-BR).
- Nomes de Skills em kebab-case.
- Estruturas simples e organizadas.
- Responsabilidades claramente definidas.
- Validação antes da disponibilização.
- Versionamento utilizando Git.

## Licença

Repositório de uso pessoal. Nenhuma licença de distribuição pública foi definida até o momento.