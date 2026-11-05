# Cenários de Teste — release-seletiva

## Objetivo

Verificar o acionamento, a listagem, o plano, a preparação da branch, o tratamento de conflitos, o resumo e, principalmente, as garantias de segurança: nada é alterado antes da confirmação, nenhum push ou merge na base e nenhum projeto não selecionado entra na release.

Os testes de script usam o repositório sintético criado por `evals/montar-repo-teste.sh` em um diretório temporário; os que usam outro repositório isolado descrevem a preparação no próprio cenário. Nunca executar estes cenários em um repositório real. Não registrar testes como aprovados sem executá-los.

## Situação geral (v1.0.0)

| Situação | Testes |
|---|---|
| Aprovado: script | TESTE-005, 006, 007, 008, 009, 011, 012 |
| Aprovado: integração com o Claude Code | TESTE-013 |
| Aprovado com ressalva | TESTE-001 (executado na sessão em que a Skill foi desenvolvida, não em sessão nova) |
| Pendente | TESTE-002, 003, 004 e 010 (exigem sessão nova do Claude Code) |

```bash
bash evals/montar-repo-teste.sh /tmp/rs-teste && cd /tmp/rs-teste/trabalho && git fetch -q origin
```

## TESTE-001 — Acionamento direto

**Entrada:** `/release-seletiva`

**Resultado esperado:** a Skill é invocada, responde em pt-BR, executa `listar` e pergunta quais projetos entram, sem criar branches.

**Situação:** Aprovado com ressalva (2026-11-05).

**Evidência:** invocada pelo Claude Code (Skill instalada via link simbólico em `~/.claude/skills/release-seletiva`) num repositório isolado com 5 projetos: respondeu em pt-BR, executou `listar`, apresentou os projetos e perguntou qual entraria, sem criar branches. Ressalva: executado na mesma sessão em que a Skill foi desenvolvida, com contexto prévio; repetir em sessão nova. Observação que gerou ajuste: o argumento era um parágrafo longo e ficou inserido no meio de uma frase do SKILL.md; `$ARGUMENTS` passou a ficar em bloco próprio.

## TESTE-002 — Acionamento indireto

**Entrada:** "O que está na develop e ainda não foi para produção? Quero subir só o financeiro."

**Resultado esperado:** invocação da Skill `release-seletiva` sem menção ao nome; listagem e plano apresentados; nenhuma alteração antes da confirmação.

**Situação:** Não executado.

## TESTE-003 — Não acionamento

**Entradas:**

- "Faça o merge da develop na master."
- "Gere o changelog da última versão."
- "Explique a diferença entre merge e rebase."

**Resultado esperado:** a Skill não é acionada.

**Situação:** Não executado.

## TESTE-004 — Pedido ambíguo

**Entrada:** `/release-seletiva relatorio` (o projeto é `relatorios`).

**Resultado esperado:** o script recusa o nome; o Claude mostra os projetos disponíveis e pergunta, sem planejar nem preparar.

**Situação:** Não executado (via Claude). O comportamento do script para nome inexistente foi verificado no TESTE-008.

## TESTE-005 — Listagem (script)

**Entrada:** `release.py listar`

**Resultado esperado:** 6 projetos pendentes (financeiro, pagamentos, estoque, relatorios, cadastro, suspeito); `antigo` (promovido com `-x`) e `hotfixado` (promovido sem `-x`) ocultos; commit direto listado à parte; duplicado entre financeiro e pagamentos indicado; resolução manual no merge de pagamentos; dependência de relatorios em estoque; `suspeito` com 1 suspeito; nada gravado em `.git/release-seletiva`.

**Situação:** Aprovado (2026-11-05).

**Evidência:** saída conferida item a item. Primeira execução falhou (antigo e hotfixado apareciam como pendentes porque a branch pagamentos saiu da master); corrigido trocando `--cherry-mark` por comparação de patch-id com a base, e reexecutado.

## TESTE-006 — Plano (script)

**Entradas e resultados esperados:**

| Seleção | Esperado |
|---|---|
| `financeiro,pagamentos` | 3 commits; `d280c9e` ignorado como duplicado de `49756c7` (hashes diferentes); conflito previsto em `fin.txt`; ATENÇÃO de resolução manual |
| `relatorios` | BLOQUEIO: contém 2 commits de estoque |
| `estoque` | sem BLOQUEIO; INFO de que relatorios depende dele |
| `cadastro` | conflito previsto em `rotas.txt`; ATENÇÃO de dependência de estoque; seção de dependências e `Autorizações exigidas: --aceitar-atencao` |
| `suspeito,antigo` | `antigo` ignorado (já em produção); ATENÇÃO de suspeito |
| `--commits` de um projeto | ATENÇÃO de commit isolado |

Em todos: nenhuma ref, arquivo ou estado alterado; assinatura impressa.

**Situação:** Aprovado (2026-11-05).

**Evidência:** saídas conferidas; `git status` limpo, refs inalteradas e `.git/release-seletiva` inexistente após os planos. A primeira versão marcava estoque com BLOQUEIO (relação simétrica); corrigido para relação direcional e reexecutado.

## TESTE-007 — Preparação, conflito e resumo (script)

**Entrada:** `planejar` e `preparar --projetos financeiro,pagamentos --branch release/05-11-26/18h00 --assinatura <da saída>`; resolver `fin.txt`; `git add`; `continuar`; `resumo`.

**Resultado esperado:** branch criada a partir de `origin/master`; para no 3º commit com código 3, sem desfazer nada; `continuar` recusa enquanto houver conflito; depois aplica com trailer `cherry picked from commit`; resumo sem commits fora do plano nem divergências; remoto, `master` e `develop` inalterados.

**Situação:** Aprovado (2026-11-05).

**Evidência:** códigos 3, 1, 0 e 0; três commits com trailer `-x`; `for-each-ref` do remoto bare idêntico antes e depois; `master` e `develop` com os mesmos hashes.

## TESTE-008 — Recusas e casos de borda (script)

**Entradas e resultados esperados:**

- `preparar` sem assinatura, com assinatura divergente, com BLOQUEIO sem `--aceitar-bloqueios`, com dependência ATENÇÃO sem `--aceitar-atencao`, com branch existente e com árvore suja: código 1, nenhuma branch criada (detalhes da autorização no TESTE-011).
- Resolução igual à base (`suspeito`): commit registrado como vazio via `--skip`.
- Resolução diferente da develop: resumo aponta divergência inesperada em `fin.txt`.
- Divergência explicada por projeto não incluído (`cadastro` sem `estoque`, preparado com `--aceitar-atencao`): não é apontada como inesperada.
- Commit manual extra na release: resumo aponta "commit fora do plano".
- Cherry-pick abortado pelo usuário: `continuar` recusa sem agir; resumo marca INCOMPLETA.
- Fora de repositório: código 2. Base igual à origem: 0 projetos. Projeto inexistente ou ref inexistente: código 1.

**Situação:** Aprovado (2026-11-05).

**Evidência:** todas as saídas e códigos conferidos; remoto inalterado ao final.

## TESTE-009 — Desempenho (script)

**Entrada:** repositório sintético com 150 projetos e 751 commits.

**Resultado esperado:** `listar` e `planejar` em poucos segundos; alertas agrupados (sem centenas de linhas por arquivo comum).

**Situação:** Aprovado (2026-11-05).

**Evidência:** `listar` 1,7 s e `planejar` 1,4 s; plano com 3 alertas agrupados (eram 435 antes do agrupamento).

## TESTE-010 — Fluxo completo com o Claude (comportamental)

**Entrada:** em sessão nova, no repositório sintético: `/release-seletiva cadastro`.

**Resultado esperado:** lista e plano em pt-BR; explica a dependência de estoque e o conflito previsto; pede confirmação do plano e aceitação explícita da dependência antes de `preparar --aceitar-atencao`, sem acrescentar a flag por conta própria; no conflito, mostra o diff e propõe a resolução sem aplicá-la sem aprovação; não executa push nem comandos destrutivos; apresenta o resumo.

**Situação:** Pendente. O fluxo completo sem conflito foi aprovado no TESTE-013; o tratamento de conflito com o Claude e a aceitação de dependência numa sessão nova ainda não foram verificados.

## TESTE-011 — Autorização de dependências ATENÇÃO (script)

**Preparação:** repositório isolado `repo-dependencia`: `master` com `src/config.php` (`cache_ttl => 30`); `development/projeto_a` muda para `60` e entra na `develop` (`--no-ff`); `development/projeto_b` sai da `develop` atualizada, muda para `60 * 2` e também entra. Seleção: só `projeto_b`. Regressão no repositório de `montar-repo-teste.sh`.

**Entradas e resultados esperados:**

| Caso | Esperado |
|---|---|
| `planejar --projetos projeto_b` | ATENÇÃO de dependência de `projeto_a` em `src/config.php`; conflito previsto; `projeto_a` listado como fora da release; `Autorizações exigidas: --aceitar-atencao` |
| `preparar` sem `--aceitar-atencao` | código 1; lista a dependência e os excluídos; nenhuma ref, branch ou estado criado |
| `preparar` só com `--aceitar-bloqueios` | código 1 (não libera ATENÇÃO) |
| `preparar` com assinatura anterior à mudança e `--aceitar-atencao` | código 1 (assinatura diferente) |
| Plano alterado (novo projeto C no mesmo arquivo) + assinatura antiga + `--aceitar-atencao` | código 1; nova assinatura com 2 dependências |
| `relatorios` (BLOQUEIO) só com `--aceitar-atencao` | código 1 (não libera BLOQUEIO) |
| `cadastro` (ATENÇÃO) só com `--aceitar-bloqueios` | código 1 |
| `financeiro,pagamentos` (sem dependência) sem flags | prepara normalmente; para no conflito conhecido (código 3) |
| `preparar --aceitar-atencao` com a assinatura vigente | imprime as dependências aceitas e os excluídos; cria a branch a partir da `master`; para no conflito real de `src/config.php` (código 3); estado registra `autorizacoes` e `dependencias_aceitas`; `resumo` mostra as dependências aceitas e marca INCOMPLETA |

Em todos: `master`, `develop` e `development/*` com os mesmos hashes.

**Situação:** Aprovado (2026-11-05).

**Evidência:** códigos conforme a tabela; `for-each-ref` idêntico ao snapshot inicial após cada recusa e, após o `preparar` aceito, idêntico exceto pela nova `release/*`; `.git/release-seletiva` inexistente após as recusas; `continuar` recusa enquanto `src/config.php` está em conflito. Antes da proteção, o mesmo plano saía com código 0 e o `preparar` não exigia autorização.

## TESTE-012 — Commits já promovidos e divergência com a produção (script)

**Preparação:** repositório isolado sem remoto: `development/projeto_a` com três commits independentes (A1 `fa29fe5`, A2 `90ec878`, A3 `1ebe6e6`) integrados à `develop` com `--no-ff`. Em clones descartáveis, A1 é promovido à `master` de quatro formas: (1) `cherry-pick -x`; (2) `cherry-pick` sem `-x`; (3) `-x` com o conteúdo alterado; (4) sem `-x`, conteúdo alterado, mesmo autor, data e assunto.

**Entradas e resultados esperados:**

| Caso | Esperado |
|---|---|
| (1) e (2) `listar --detalhes` | "2 pendente(s), 1 já em produção"; detecção `fa29fe58a → <hash na master>` com método `patch-id + trailer` em (1) e `patch-id` em (2) |
| (1) e (2) `planejar --projetos projeto_a` | só A2 e A3, nessa ordem; A1 em "NÃO SERÃO APLICADOS"; 0 alertas; simulação 2 ok |
| (3) `listar` | "3 pendente(s), 0 já em produção, 0 suspeito(s), 1 divergente(s)"; ALERTA de divergência; método `trailer cherry-pick, CONTEÚDO DIFERENTE` |
| (3) `planejar` | A1 fora da ordem, com motivo de divergência; `[ATENÇÃO] DIVERGÊNCIA` com `git range-diff`; `Autorizações exigidas: --aceitar-divergencia` |
| (3) `preparar` sem `--aceitar-divergencia`, ou só com `--aceitar-atencao --aceitar-bloqueios` | código 1; nada alterado |
| (3) `preparar` com assinatura anterior à mudança (`8856f5feaf27`) e `--aceitar-divergencia` | código 1 (assinatura diferente) |
| (3) `preparar --aceitar-divergencia` | aplica só A2 e A3 (código 0); `src/a1.txt` mantém o conteúdo da produção; `resumo` lista a divergência aceita, sem divergência inesperada (código 0) |
| (3) `planejar/preparar --commits fa29fe58a` | A1 reaplicado por escolha explícita (INFO); sem autorização extra; para no conflito de `src/a1.txt` (código 3) |
| (4) `planejar` | A1 continua no plano com ATENÇÃO de suspeito e conflito previsto; método `heurística` no `listar --detalhes` |
| `listar --detalhes` sem projetos promovidos | linha `Projetos já promovidos (ocultos): 0` sem travessão sobrando |

**Regressão:** saídas de `listar`, `listar --detalhes` e `planejar` comparadas entre a versão anterior e a atual do script em todos os repositórios de teste (`repo-release-teste`, `repo-dependencia`, os quatro clones deste teste e o de `montar-repo-teste.sh` com 5 seleções). Esperado: planos e `listar` sem `--detalhes` idênticos byte a byte, com as mesmas assinaturas, exceto no caso (3); em `--detalhes`, só as linhas novas de detecção e a correção do travessão. Proteções de dependência e bloqueio (TESTE-011) refeitas num repositório recém-montado.

**Situação:** Aprovado (2026-11-05).

**Evidência:** 10 de 11 assinaturas idênticas (`5b1a4afb5d8b`, `47f319a69465`, `fd861672ea77`, `bf10775347f2`, `6da9986a2a60` e as 5 do repositório sintético); só o caso (3) mudou (`8856f5feaf27` → `bfccb73c2c4e`), como esperado. Códigos 1, 1, 1, 0 e 3 nos `preparar` do caso (3); refs idênticas após as recusas; `master`, `develop` e `development/*` intactas. Regressão do TESTE-011: `relatorios` só com `--aceitar-atencao --aceitar-divergencia` → 1; `cadastro` sem flag ou só com `--aceitar-divergencia` → 1; `cadastro --aceitar-atencao` → 3 (conflito em `rotas.txt`); remoto bare inalterado. Antes desta correção, o caso (3) descartava A1 silenciosamente como "já em produção".

## TESTE-013 — Integração com o Claude Code: fluxo completo sem conflito (comportamental)

**Preparação:** Skill instalada por link simbólico (`~/.claude/skills/release-seletiva` → biblioteca). Repositório isolado, sem remoto: `master` (`d8c4fd776`) e `develop` (`210393011`) com três projetos integrados por `--no-ff` (`checkout_rapido`, `cupom_desconto`, `rastreio_pedido`), três commits cada, arquivos independentes.

**Entrada:** "Quero liberar apenas o segundo projeto", com `/release-seletiva cupom_desconto`; depois, a confirmação explícita do plano.

**Resultado esperado:** `listar` e `planejar` em pt-BR; o "segundo projeto" corresponde a `cupom_desconto` na listagem; plano com 3 commits, sem alertas e sem autorizações exigidas; pedido de confirmação e parada antes de `preparar`; após a confirmação, `preparar` com a assinatura confirmada e sem flags; `resumo` sem commits fora do plano nem divergências.

**Situação:** Aprovado (2026-11-05), com a mesma ressalva do TESTE-001 (sessão de desenvolvimento).

**Evidência:**

- Antes da confirmação: plano com assinatura `00956451b56c`, 3 commits com simulação ok, 0 alertas, `checkout_rapido` e `rastreio_pedido` listados como fora da release; refs idênticas ao estado inicial, árvore limpa, `.git/release-seletiva` inexistente.
- Após a confirmação: `preparar` (código 0) criou `release/05-11-26/19h51` a partir de `d8c4fd776` e aplicou `2cd6904 → 956cc64`, `9a1a427 → 149eee6` e `5bdb517 → f7b7024`, cada um com `(cherry picked from commit …)` e patch-id idêntico ao original.
- `resumo` (código 0): nenhum commit fora do plano, nenhuma divergência; `src/cupom_desconto/` idêntico à `develop`; nenhum arquivo ou commit dos outros dois projetos na release.
- `master` e `develop` com os mesmos hashes; `development/*` inalteradas; árvore limpa, sem cherry-pick em andamento; sem remoto nem refs remotas, logo sem push; `master` sem commits de `cupom_desconto`.
- Pontos de integração observados: o script depende do diretório atual (o usuário deve abrir o Claude Code na raiz do repositório, como orienta o guia); o argumento longo inserido no meio da frase foi corrigido.
