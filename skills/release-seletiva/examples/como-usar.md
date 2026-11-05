# Como usar a Skill release-seletiva

## Objetivo

Montar uma release só com alguns projetos que já estão na `develop`, sem levar o resto. A Skill mostra o que ainda não foi para produção, monta um plano de cherry-pick com os riscos encontrados e, depois que você confirma, prepara a branch `release/DD-MM-AA/HHhMM` a partir da `master`. Push, merge e deploy continuam com você.

## Como invocar

Abra o Claude Code na raiz do repositório e digite:

```text
/release-seletiva [projetos] [--base master] [--origem develop]
```

- Sem argumentos, a Skill lista os projetos pendentes e pergunta quais entram.
- Também é acionada quando você pede, por exemplo, para "montar uma release só com o financeiro".

### Instalação

Criar a pasta no repositório não instala a Skill. Confira se o destino está livre e crie o link simbólico:

```bash
ls -la ~/.claude/skills/
ln -s /CAMINHO/ABSOLUTO/claude-skills/skills/release-seletiva ~/.claude/skills/release-seletiva
```

Se já existir uma `release-seletiva` em `~/.claude/skills/`, decida antes o que fazer com ela: as duas não podem ter o mesmo nome no mesmo escopo. Abra uma sessão nova do Claude Code depois de instalar.

## Exemplos de solicitações

```text
/release-seletiva
```

```text
/release-seletiva financeiro,estoque
```

```text
O que está na develop e ainda não foi para produção?
```

```text
Monta uma release só com o projeto de cadastro e o commit direto a1b2c3d.
```

```text
/release-seletiva --base main --origem homolog
```

## Entradas e resultados esperados

- **Entradas:** o repositório com `master` e `develop` (ou os nomes que você informar), a escolha dos projetos e a sua confirmação do plano.
- **Resultados:**
  - Lista dos projetos pendentes por branch de origem (`development/<projeto>`), com commits, autores, arquivos e alertas.
  - Plano com a ordem dos cherry-picks, o que será pulado e por quê (já em produção ou duplicado), conflitos previstos, alertas de dependência, os projetos que ficam fora e as autorizações que a preparação vai exigir.
  - A branch de release local, criada só depois da sua confirmação.
  - Um resumo final com commits aplicados (hash original → novo), verificações e os comandos de push/MR para você executar, se aprovar.

Os comandos do script podem ser usados diretamente (`listar`, `planejar` e `resumo` não alteram nada):

```bash
python3 ~/.claude/skills/release-seletiva/scripts/release.py listar
python3 ~/.claude/skills/release-seletiva/scripts/release.py planejar --projetos financeiro
```

### Dependências e autorizações

Se um projeto escolhido foi desenvolvido sobre alterações de um projeto que ficou de fora (por exemplo, `projeto_b` altera um valor de `src/config.php` que o `projeto_a` introduziu), o plano mostra a dependência e a linha `Autorizações exigidas pelo preparar: --aceitar-atencao`. Sem essa flag, a preparação é recusada antes de criar qualquer branch. Você decide entre três caminhos: incluir o projeto de que depende, retirar o projeto escolhido ou aceitar o risco.

```text
DEPENDÊNCIAS DE PROJETOS NÃO SELECIONADOS: 1
  - development/projeto_b depende de development/projeto_a em src/config.php (commits não incluídos: 614bbfaec)

Projetos pendentes que ficam FORA da release: 1 — development/projeto_a
Autorizações exigidas pelo preparar: --aceitar-atencao (1 dependência(s))
```

A preparação tem três autorizações independentes. Cada uma libera só o seu tipo de risco, e nenhuma libera as outras:

| Flag | Libera | Quando aparece |
|---|---|---|
| `--aceitar-bloqueios` | `BLOQUEIO` | A branch do projeto contém commits de outro projeto não selecionado; ele não pode ser isolado. |
| `--aceitar-atencao` | Dependências `ATENÇÃO` | O projeto foi desenvolvido sobre alterações de um projeto não selecionado nos mesmos arquivos. |
| `--aceitar-divergencia` | `DIVERGÊNCIA` (manter o commit fora) | Um commit está registrado como cherry-pick na `master`, mas com conteúdo diferente (veja a próxima seção). |

- O plano informa quais são necessárias na linha `Autorizações exigidas pelo preparar`. Sem a flag correspondente, a preparação é recusada sem alterar nada.
- O Claude só usa uma flag depois que você aceita aquele risco, naquele plano.
- A aceitação vale só para a assinatura confirmada. Se as dependências ou divergências mudarem, a assinatura muda, a preparação é recusada e é preciso planejar e aceitar de novo.
- Aceitar a dependência não resolve conflitos: se o código depende do outro projeto, o cherry-pick ainda para no conflito para resolução manual.

### Commits que já estão em produção

`listar --detalhes` mostra, em cada projeto, os commits reconhecidos na `master`, com o hash original, o hash correspondente na produção e o método de detecção:

```text
    Detecção na produção (master):
      ✓ fa29fe58a → caf7ee66a  [patch-id + trailer cherry-pick] feat(projeto_a): A1 cria a1
      ! 35e62161d → bfc81d2ec  [heurística (autor, data e assunto): suspeito, continua pendente] feat: suspeito
```

- **patch-id** (com ou sem o trailer `cherry picked from commit`): o conteúdo é equivalente; o commit é pulado no plano.
- **trailer com conteúdo diferente**: `DIVERGÊNCIA`. A promoção pode ter sido parcial ou adaptada, então o commit não conta como promovido. O plano mostra um alerta com o comando de comparação (`git range-diff <original>^! <base>^!`), e a preparação exige `--aceitar-divergencia` para mantê-lo fora. Para reaplicá-lo, planeje de novo com `--commits <sha>`.
- **heurística** (mesmo autor, data e assunto, conteúdo diferente): suspeito; continua no plano com alerta `ATENÇÃO`.

## Dependências e pré-requisitos

- Git 2.23 ou mais recente. Para a simulação de conflitos antes de alterar o repositório, git 2.45 ou mais recente.
- Python 3.8 ou mais recente (só biblioteca padrão).
- Árvore de trabalho sem alterações pendentes em arquivos versionados no momento de preparar a release.

## Limitações conhecidas

- Os projetos são identificados pela mensagem do merge na `develop` (`Merge branch '...'`, `Merge pull request #N from ...`). Merges com mensagem personalizada aparecem como `merge-<hash>`.
- A Skill cherry-picka os commits do projeto, não o merge. Resoluções de conflito feitas no merge da `develop` não são reproduzidas; isso é avisado no plano e conferido no resumo.
- Um commit levado à produção sem `-x` e com conteúdo alterado na resolução de conflito só é identificado como "suspeito" (mesmo autor, data e assunto). Você decide se entra. Se, além disso, o assunto ou a data forem diferentes, ele não é reconhecido e volta ao plano (normalmente parando num conflito).
- Com `-x` e conteúdo alterado, a Skill aponta a divergência, mas não sabe dizer qual parte falta na produção: a comparação é sua.
- A simulação de conflitos é indicativa depois do primeiro conflito previsto.
- Os alertas de dependência por arquivos em comum podem incluir falsos positivos em arquivos alterados por muitos projetos (rotas, configuração). Mesmo assim, eles exigem `--aceitar-atencao` na preparação.
- Dependências que não passam por arquivos em comum (por exemplo, uma função criada por outro projeto em outro arquivo) não são detectadas.
- Apenas dependências e divergências exigem autorização mecânica; os demais alertas `ATENÇÃO` (suspeito de já estar em produção, resolução manual de merge, commit isolado) dependem da sua decisão durante a conversa.
- Não faz push, merge, deploy nem changelog, e não apaga branches de tentativas anteriores.
