#!/usr/bin/env bash
# Monta um repositório sintético (com remoto bare local) para testar a release-seletiva.
# Uso: montar-repo-teste.sh <diretorio-novo-ou-vazio>
# Cenários cobertos: projeto promovido com -x (antigo), promovido sem -x (hotfixado),
# commit duplicado com hash diferente (financeiro/pagamentos), merge com resolução manual
# (pagamentos), branch criada sobre outra (relatorios sobre estoque), dependência que gera
# conflito (cadastro sobre estoque), suspeito de promoção (suspeito) e commit direto na develop.
set -euo pipefail
R="${1:?informe um diretório novo ou vazio}"
if [ -e "$R" ] && [ -n "$(ls -A "$R")" ]; then echo "ERRO: $R não está vazio." >&2; exit 1; fi
mkdir -p "$R" && cd "$R"
git init -q --bare remoto.git
git init -q -b master trabalho && cd trabalho
git config user.name "Ana Teste"; git config user.email "ana@exemplo.com"
git remote add origin ../remoto.git
c() { git add -A && git commit -qm "$1"; }

printf 'linha1\nlinha2\nlinha3\n' > rotas.txt; printf 'fin v1\n' > fin.txt; echo base > README.md; c "chore: inicial"
git switch -qc develop

# antigo: promovido em release anterior com cherry-pick -x
git switch -qc development/antigo develop; echo antigo > antigo.txt; c "feat: antigo"; A=$(git rev-parse HEAD)
git switch -q develop; git merge -q --no-ff development/antigo -m "Merge branch 'development/antigo' into 'develop'"
git switch -q master; git cherry-pick -x "$A"; git switch -q develop

# hotfixado: mesma alteração aplicada na master sem -x
git switch -qc development/hotfixado develop; echo hotfix > hotfix.txt; c "fix: hotfix"; H=$(git rev-parse HEAD)
git switch -q develop; git merge -q --no-ff development/hotfixado -m "Merge branch 'development/hotfixado' into develop"
git switch -q master; git cherry-pick "$H"; git switch -q develop

# financeiro: 2 commits + correção compartilhada (duplicada em pagamentos)
git switch -qc development/financeiro develop
printf 'fin v2\n' > fin.txt; c "feat: financeiro calcula juros"
echo "util corrigido" > util.txt; c "fix: corrige util"; U=$(git rev-parse HEAD)
git switch -q develop; git merge -q --no-ff development/financeiro -m "Merge branch 'development/financeiro' into develop"

# pagamentos: recebe a mesma correção (cherry-pick sem -x) e conflita com financeiro na develop
git switch -qc development/pagamentos master
git cherry-pick "$U"
printf 'fin pagamentos\n' > fin.txt; c "feat: pagamentos altera fin"
git switch -q develop
git merge -q --no-ff development/pagamentos -m "Merge remote-tracking branch 'origin/development/pagamentos' into develop" || true
printf 'fin v2 + pagamentos\n' > fin.txt; git add fin.txt; git -c core.editor=true commit -q --no-edit

# estoque: altera rotas.txt
git switch -qc development/estoque develop
printf 'linha1\nlinha2 estoque\nlinha3\n' > rotas.txt; c "feat: estoque rota"
echo est > estoque.txt; c "feat: estoque tela"
# relatorios: criado a partir da branch de estoque (entrelaçado)
git switch -qc development/relatorios
echo rel > relatorios.txt; c "feat: relatorios"
git switch -q develop; git merge -q --no-ff development/estoque -m "Merge branch 'development/estoque' into develop"
git merge -q --no-ff development/relatorios -m "Merge branch 'development/relatorios' into develop"

# cadastro: criado da develop depois do estoque, altera a mesma linha de rotas.txt
git switch -qc development/cadastro develop
printf 'linha1\nlinha2 estoque cadastro\nlinha3\n' > rotas.txt; c "feat: cadastro rota"
echo cad > cadastro.txt; c "feat: cadastro tela"
git switch -q develop; git merge -q --no-ff development/cadastro -m "Merge pull request #7 from org/development/cadastro"

# suspeito: mesmo autor/data/assunto na master, patch diferente, sem -x
git switch -qc development/suspeito develop
echo "sus develop" > suspeito.txt; GIT_AUTHOR_DATE="2026-10-01T10:00:00" c "feat: suspeito"
git switch -q develop; git merge -q --no-ff development/suspeito -m "Merge branch 'development/suspeito' into develop"
git switch -q master; echo "sus master" > suspeito.txt; GIT_AUTHOR_DATE="2026-10-01T10:00:00" c "feat: suspeito"

# commit direto na develop
git switch -q develop; echo "doc" >> README.md; c "docs: ajuste direto na develop"

git push -q origin master develop
git switch -q master
echo "Repositório de teste pronto em $R/trabalho"
