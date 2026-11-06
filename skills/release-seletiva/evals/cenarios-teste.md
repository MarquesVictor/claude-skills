# Cenários de Teste — release-seletiva

## Objetivo

Verificar o acionamento, a listagem, o plano, a preparação da branch, o tratamento de conflitos, o resumo e, principalmente, as garantias de segurança: nada é alterado antes da confirmação, nenhum push ou merge na base e nenhum projeto não selecionado entra na release.

Os testes de script usam os repositórios sintéticos criados por `evals/montar-repo-teste.sh` e `evals/montar-repo-merges.sh` (promoções por `cherry-pick -m 1` de merges) em diretórios temporários; os que usam outro repositório isolado descrevem a preparação no próprio cenário. Nunca executar estes cenários em um repositório real. Não registrar testes como aprovados sem executá-los.

## Situação geral (v1.1.0)

| Situação | Testes |
|---|---|
| Aprovado: script | TESTE-005, 006, 007, 008, 009, 011, 012, 014, 015, 017 |
| Aprovado: repositório real, somente leitura | TESTE-016 |
| Aprovado: integração com o Claude Code | TESTE-013 |
| Aprovado com ressalva | TESTE-001 (executado na sessão em que a Skill foi desenvolvida, não em sessão nova) |
| Pendente | TESTE-002, 003, 004 e 010 (exigem sessão nova do Claude Code); continuam pendentes na v1.1.0, como na v1.0.0 |

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

**Situação:** Aprovado (2026-11-05). Revisto na camada de merge (TESTE-015): nos casos (1) e (2), o projeto passou a ser **parcialmente promovido** (A1 em produção, A2 e A3 a aplicar), e o `preparar` exige `--aceitar-parcial`. A mudança é intencional; a detecção de A1 é a mesma.

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

## TESTE-014 — Promoções por `cherry-pick -m 1` de merges (script)

**Preparação:** `bash evals/montar-repo-merges.sh <dir>` (sem remoto; base `master`, origem `develop`).

**Entradas e resultados esperados (`listar --detalhes`, `planejar`, `preparar`):**

| Cenário | Projeto | Esperado | Obtido |
|---|---|---|---|
| T1 `-x -m 1` limpo | p1 | confirmado: `merge: trailer -x + patch-id igual` | igual |
| T2 `-m 1` sem `-x` | p2 | equivalente, sem rastreabilidade | igual |
| T3 trecho herdado da `master` já presente na base | p3 (2 commits) | confirmado: `trailer -x + reprodução exata`; nota de alteração herdada em `shared.txt` | igual |
| T3 idem, não promovido | p3b | pendente; plano aplica só `p3b.txt`; nota de herança em `shared2.txt` | igual |
| T4 `-x -m 1` editado à mão | p4 | divergente; `preparar` exige `--aceitar-divergencia` | igual |
| T5 base mudou a mesma linha por commit só dela | p5 | indeterminado (conflito em arquivo alterado só na base) | igual |
| T5 conteúdo já presente, patch diferente, sem `-x` | p6 | indeterminado (arquivos idênticos na base e na origem); `--commits` simula "ficaria vazio" | igual |
| T6 dois merges, só o 1º promovido | p7 | parcial; o commit do 1º merge é rastreável (`patch-id + trailer -x do merge`); `preparar` exige `--aceitar-parcial` e aplica só `p7b` | igual |
| T7 promovido e revertido na base | p8 (2 commits) | confirmado + aviso de reversão, inclusive no `listar` sem `--detalhes` | igual |
| T8 branch que incorporou a do p1 | p9 | pendente; plano aplica só o commit do p9 | igual |

Autorizações (cópia descartável): `preparar` recusa com código 1 e refs idênticas em p7 sem flag ou só com as outras quatro flags; p4,p9 sem flag ou com `--aceitar-indeterminado --aceitar-parcial`; p5,p6,p9 sem flag ou com `--aceitar-divergencia --aceitar-parcial`; p7,p9 com a assinatura do plano p7. Aceita (código 0) p7 com `--aceitar-parcial` (aplica só `p7b`), p5,p6,p9 com `--aceitar-indeterminado` e p4,p9 com `--aceitar-divergencia` (aplicam só `p9`); `resumo` lista os riscos aceitos e não acusa commits fora do plano nem divergências inesperadas; `master`, `develop` e `development/*` intactas; estado gravado em `.git/release-seletiva-skill/`.

**Situação:** Aprovado (2026-11-06).

**Evidência:** saídas conferidas cenário a cenário. Ajustes feitos durante o teste: (a) commits de projetos de um commit reconhecidos por patch-id passaram a contar como rastreáveis quando o commit da base cita o merge que os introduziu; (b) o cenário T5 foi refeito porque o patch-id ignora diferenças só de espaços (`x = 2;` × `x = 2 ;` era reconhecido como conteúdo equivalente); (c) o aviso de reversão passou a valer também para detecções por commit.

## TESTE-015 — Regressão, compatibilidade de estado e desempenho (script)

**Entradas e resultados esperados:**

- `listar`, `listar --detalhes` e `planejar` da v1.0.0 × versão atual em 7 repositórios (25 saídas): planos e assinaturas idênticos, exceto as mudanças intencionais: `repo-promovido` e `repo-promovido-sem-x` passam a parciais (assinaturas `47f319a69465` → `d305fdf965ee` e `fd861672ea77` → `7f8f1d1b40e3`); linhas novas de "Situação" em projetos parciais e divergentes; `--detalhes` separa confirmados de equivalentes.
- `preparar` dos TESTE-007, 008, 011 e 012 com os mesmos códigos: BLOQUEIO só com as quatro outras flags → 1; dependência sem flag ou só com `--aceitar-indeterminado --aceitar-parcial` → 1; sem assinatura ou com assinatura divergente → 1; fluxo do TESTE-007 → 3, 1, 0 e 0 com 3 trailers `-x`; divergência por commit com `--aceitar-indeterminado` → 1 e com `--aceitar-divergencia` → 0; remoto bare inalterado.
- Estado da v1.0.0: release preparada pela v1.0.0 até o conflito (código 3), com `released.txt` e `.env` de "outra ferramenta" na mesma pasta; a versão atual lê o estado legado no `resumo`, conclui com `continuar` (código 0), grava em `.git/release-seletiva-skill/` e não altera nenhum arquivo de `.git/release-seletiva/` (checksums iguais).
- Desempenho com 150 projetos (826 commits, 75 promovidos por `-x -m 1`): v1.0.0 lista 150 pendentes em 1,73 s; a versão atual lista os 75 corretos em 1,8–2,1 s (`planejar` 1,8 s).

**Situação:** Aprovado (2026-11-06).

**Evidência:** comparação arquivo a arquivo das saídas. Primeira execução apontou falso positivo no critério de "commit sem correspondência na base" (o commit inicial do repositório, comum à origem, era considerado); corrigido para usar só commits exclusivos da base (`origem..base`) e reexecutado. A primeira medição de desempenho (3,4 s) levou a trocar uma comparação por projeto por um único `git diff --name-only` entre base e origem.

## TESTE-016 — Repositório real `unicphp`, somente leitura

**Entrada:** `release.py listar --detalhes --base origin/main --origem origin/develop`, sem `fetch`, com `GIT_OPTIONAL_LOCKS=0`.

**Resultado esperado:** reconhecer os 16 projetos promovidos por `cherry-pick -x -m 1` que a v1.0.0 listava como pendentes; tratar `feat/remover-ac-vinculo` com cautela; não alterar refs, índice, árvore nem os arquivos da outra ferramenta em `.git/release-seletiva/`.

**Situação:** Aprovado (2026-11-06).

**Evidência:** 1 projeto não promovido (era 17): `feat/remover-ac-vinculo` como **indeterminado**, porque `functions.php` já está idêntico em `origin/main` e `origin/develop` (a alteração foi reescrita dentro da própria `develop` por um merge interno e a correção equivalente `2b361391` faz parte do histórico comum). 40 projetos ocultos, todos confirmados por rastreabilidade e conteúdo: os 16 pela camada de merge (14 por patch-id, `fundo-fixo` e `apr-sessao-insert` por reprodução exata, com nota de alteração herdada no segundo) e os 24 anteriores, agora identificados como rastreáveis pelo trailer do merge. Tempo: 1,10–1,30 s. Refs, status, índice e os 5 arquivos da outra ferramenta idênticos antes e depois; `.git/release-seletiva-skill/` não foi criada.

## TESTE-017 — Revisão de segurança antes da versão estável (script)

**Preparação:** cópias descartáveis de `montar-repo-merges.sh` e `montar-repo-teste.sh`, de `repo-promovido-x-alterado` e um repositório entrelaçado próprio (branch `x` incorpora `y` antes de `y` entrar na `develop`; `x` promovido com `-x -m 1`; `y` entra depois com `y3`; `z` é um merge sem commits próprios).

**Entradas e resultados esperados:**

| Ponto | Caso | Esperado | Obtido |
|---|---|---|---|
| Arquivos idênticos não provam promoção | p6 (arquivo idêntico em `master` e `develop`) | listado como INDETERMINADO, fora da lista de promovidos; plano não aplica nem descarta em silêncio; `preparar` sem flag → 1 | igual |
| Indeterminado não é excluído nem reaplicado em silêncio | unidade indeterminada com 2 commits, só 1 reaplicado com `--commits` | o reaplicado entra com INFO; o outro continua exigindo `--aceitar-indeterminado` (sem flag → 1); com os 2 em `--commits`, nenhuma flag de indeterminado | igual |
| Estado | JSON ilegível; commit estranho na fila; conflito fora da fila; assinatura adulterada; estado de outra branch; commit aplicado ausente da branch | `continuar` recusa com código 1 e mensagem clara, sem traceback e sem agir | igual |
| Estado | v1.0.0 cujo plano mudou nas regras atuais (p5 pendente na v1, indeterminado agora) | `continuar` recusa (assinatura, fila e `--aceitar-indeterminado` não registrada); cherry-pick continua em andamento; `resumo` aponta a incompatibilidade e sai com 1 | igual |
| Estado | v1.0.0 compatível (`financeiro,pagamentos`, mesma assinatura `f36f8bd80462`) | `continuar` conclui (0); `resumo`: "Plano confirmado × regras atuais: compatível"; estado legado intacto | igual |
| Flags independentes | BLOQUEIO, dependência, divergência por commit, divergência por merge, parcial, indeterminado | com as outras 4 flags → 1 e refs intactas; só a própria → 0 (3 quando a simulação prevê conflito); plano com parcial + indeterminado só com `--aceitar-parcial` → 1 | igual |
| Refs | base local, origem local e `origin/master` após `fetch` avançam | assinatura muda; `preparar` com a antiga → 1; nenhuma branch criada | igual |
| Herança | `y` com `y1`/`y2` promovidos dentro de `x` | plano de `y` aplica só `y3`; `x` sem nada a aplicar; sem a promoção de `x`, `y` recebe BLOQUEIO | igual |
| Herança | `z` sem commits próprios | identificado como "sem commits próprios", não como confirmado; plano avisa (ATENÇÃO) que os commits entraram por `development/w` e não aplica nada | igual |

**Situação:** Aprovado (2026-11-06).

**Evidência:** a revisão encontrou e corrigiu três pontos antes dos testes: (1) `continuar` não validava o estado nem recalculava o plano (um JSON ilegível gerava traceback, e um estado da v1.0.0 com plano diferente nas regras atuais seria retomado); (2) não havia verificação estrutural do estado; (3) um projeto sem commits próprios aparecia como "confirmado" e gerava plano vazio sem explicação. Regressão v1.0.0 × final nas 25 saídas: idêntica à rodada aprovada do TESTE-015 (única diferença: idade do último `fetch` no aviso).
