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

A preparação tem cinco autorizações independentes. Cada uma libera só o seu tipo de risco, e nenhuma libera as outras:

| Flag | Libera | Quando aparece |
|---|---|---|
| `--aceitar-bloqueios` | `BLOQUEIO` | A branch do projeto contém commits de outro projeto não selecionado; ele não pode ser isolado. |
| `--aceitar-atencao` | Dependências `ATENÇÃO` | O projeto foi desenvolvido sobre alterações de um projeto não selecionado nos mesmos arquivos. |
| `--aceitar-divergencia` | `DIVERGÊNCIA` (manter fora) | Um commit, ou o merge inteiro de um projeto, está registrado como cherry-pick na `master`, mas com conteúdo diferente (veja a próxima seção). |
| `--aceitar-parcial` | Projeto `PARCIALMENTE PROMOVIDO` | Parte do projeto já está em produção e só o restante seria aplicado. |
| `--aceitar-indeterminado` | Merge `INDETERMINADO` (manter fora) | Não há prova de promoção, mas há indício de que o conteúdo já está na produção. |

- O plano informa quais são necessárias na linha `Autorizações exigidas pelo preparar`. Sem a flag correspondente, a preparação é recusada sem alterar nada.
- O Claude só usa uma flag depois que você aceita aquele risco, naquele plano.
- A aceitação vale só para a assinatura confirmada. Se as dependências, divergências, parciais ou indeterminados mudarem, a assinatura muda, a preparação é recusada e é preciso planejar e aceitar de novo.
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

Quando a release é feita com um commit por projeto (`git cherry-pick -x -m 1` do merge da `develop`), a Skill compara a diferença total do merge com o commit da produção:

```text
    Detecção na produção (origin/main):
      ✓ merge 3fe97a24e → 69135f4bb  [merge: trailer -x + patch-id igual] 2 commit(s)
      ✓ merge 0123a94a8 → 7278b8126  [merge: trailer -x + reprodução exata sobre o pai do commit da base] 12 commit(s)
      ✓ merge d054df26c → 25a6fe41e  [merge: conteúdo equivalente, SEM trailer (rastreabilidade não comprovada)] 2 commit(s)
```

- **trailer -x + patch-id igual** ou **trailer -x + reprodução exata**: promovido confirmado. A reprodução refaz o cherry-pick do merge sobre o pai do commit da produção e exige árvore idêntica, sem conflito; ela cobre o caso em que o git descartou sozinho um trecho que a produção já tinha.
- **conteúdo equivalente, sem trailer**: o conteúdo está lá, mas a rastreabilidade não está comprovada.
- **trailer -x com conteúdo diferente**: merge `DIVERGENTE` (edição manual ou promoção parcial).

Cada projeto recebe uma situação: promovido confirmado, conteúdo equivalente, parcialmente promovido, pendente, indeterminado ou divergente. Um projeto é **indeterminado** quando não há prova de promoção, mas há indício de que o conteúdo já está na produção: os arquivos já estão idênticos na `master` e na `develop`, reaplicar não muda nada, o conflito acontece num arquivo que a produção alterou por um commit que só existe nela, ou o mesmo conteúdo aparece em mais de um commit. Reaplicar sem produzir alteração nunca basta para considerar um projeto promovido.

O plano nunca aplica commits de merge. Quando o merge de um projeto carrega alterações herdadas (por exemplo, a branch incorporou a `master`), o `--detalhes` mostra uma nota, e essas alterações não são reaplicadas. Se uma promoção foi revertida depois na produção, a listagem avisa.

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
- Apenas dependências, divergências, parciais e indeterminados exigem autorização mecânica; os demais alertas `ATENÇÃO` (suspeito de já estar em produção, resolução manual de merge, commit isolado) dependem da sua decisão durante a conversa.
- O patch-id ignora diferenças só de espaços: uma promoção que difere apenas em espaços conta como conteúdo equivalente.
- Releases que juntam vários projetos num único commit da produção não são reconhecidas por merge e tendem a aparecer como divergentes ou indeterminadas.
- A busca na produção usa uma janela de datas (a partir do commit mais antigo pendente); promoções anteriores a ela não são vistas.
- A Skill prepara releases commit a commit (`cherry-pick -x` de cada commit), mesmo em repositórios que promovem um commit por merge.
- Ao retomar uma release (`continuar`), a Skill recalcula o plano com os SHAs gravados e recusa se o estado estiver inconsistente ou se o plano, pelas regras atuais, não for mais o mesmo; o `resumo` mostra essa verificação.
- O estado da Skill fica em `.git/release-seletiva-skill/`. Estados da v1.0.0 em `.git/release-seletiva/` continuam sendo lidos; outros arquivos dessa pasta (de outras ferramentas de release) não são lidos nem alterados.
- Não faz push, merge, deploy nem changelog, e não apaga branches de tentativas anteriores.

## Histórico de versões

### v1.1.0 (2026-11-06)

- **Promoções por merge:** reconhece releases feitas com `git cherry-pick -x -m 1` do merge da `develop`, comparando a diferença do merge em relação ao 1º pai com o commit da produção (patch-id igual ou reprodução exata do cherry-pick sobre o pai do commit da produção).
- **Classificação das promoções:** cada projeto aparece como promovido confirmado, conteúdo equivalente (sem rastreabilidade), parcialmente promovido, pendente, indeterminado ou divergente. Arquivos idênticos ou reaplicação sem alteração nunca bastam para considerar um projeto promovido.
- **Autorizações independentes:** às flags `--aceitar-bloqueios`, `--aceitar-atencao` e `--aceitar-divergencia` (agora também para merges divergentes) somam-se `--aceitar-parcial` e `--aceitar-indeterminado`. Nenhuma libera as outras, e todas valem só para a assinatura confirmada.
- **Validação na retomada:** `continuar` valida o estado e recalcula o plano com os SHAs gravados; recusa estados inconsistentes, assinaturas que não batem ou autorizações que não foram dadas. O `resumo` mostra essa verificação.
- **Estado separado e compatível:** o estado passa a ficar em `.git/release-seletiva-skill/`; estados da v1.0.0 em `.git/release-seletiva/` continuam sendo lidos, e os demais arquivos dessa pasta (de outras ferramentas) nunca são tocados.
- **Mudança de comportamento:** projetos com parte já em produção passam a exigir `--aceitar-parcial` para aplicar só o restante.
- **Testes:** TESTE-014 a 017 aprovados; TESTE-002, 003, 004 e 010 continuam pendentes (exigem sessão nova do Claude Code).

### v1.0.0 (2026-11-05)

- Primeira versão: listagem dos projetos da `develop` ainda não promovidos à `master`, detecção de promoção por commit (patch-id, trailer `-x` e heurística), plano com simulação de conflitos e assinatura, preparação por `cherry-pick -x` com confirmação, retomada após conflitos e resumo com verificações.
- Autorizações `--aceitar-bloqueios`, `--aceitar-atencao` e `--aceitar-divergencia`.
