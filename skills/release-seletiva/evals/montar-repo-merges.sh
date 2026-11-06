#!/usr/bin/env bash
# Monta um repositório sintético (sem remoto) com promoções por `cherry-pick -m 1` de merges da develop.
# Uso: montar-repo-merges.sh <diretorio-novo-ou-vazio>
# Projetos (master = produção; cada projeto entra na develop por merge --no-ff):
#   p1  T1  cherry-pick -x -m 1 limpo                          → confirmado (trailer + patch-id)
#   p2  T2  cherry-pick -m 1 sem -x                            → equivalente (sem rastreabilidade)
#   p3  T3  2 commits + merge interno da master; trecho herdado já na base → confirmado (reprodução)
#   p3b T3  igual ao p3, mas não promovido                     → pendente; só o commit próprio é aplicado
#   p4  T4  cherry-pick -x -m 1 editado à mão                  → divergente
#   p5  T5  base mudou a mesma linha por outro commit (sem -x) → indeterminado (conflito)
#   p6  T5  conteúdo já presente na base, sem -x nem patch igual → indeterminado (reaplicar não muda nada)
#   p7  T6  dois merges do mesmo projeto, só o 1º promovido    → parcial
#   p8  T7  2 commits, promovido com -x -m 1 e revertido na base → confirmado + aviso de reversão
#   p7a     (1 commit) reconhecido por commit, com trailer do merge → rastreável
#   p9  T8  incorpora a branch do p1 (já na develop e promovido) → pendente; não reaplica commits do p1
set -euo pipefail
R="${1:?informe um diretório novo ou vazio}"
if [ -e "$R" ] && [ -n "$(ls -A "$R")" ]; then echo "ERRO: $R não está vazio." >&2; exit 1; fi
mkdir -p "$R" && cd "$R"
git init -q -b master
git config user.name "Ana Teste"; git config user.email "ana@exemplo.com"
c() { git add -A && git commit -qm "$1"; }
mergedev() { git switch -q develop; git merge -q --no-ff "development/$1" -m "Merge branch 'development/$1' into 'develop'"; git rev-parse HEAD; }
promover() { git switch -q master; git cherry-pick ${2:+"$2"} -m 1 "$1" >/dev/null; git switch -q develop; }

printf 'linha a\n' > shared.txt; printf 'linha a\n' > shared2.txt; printf 'x = 1\n' > conf.txt; echo base > README.md; c "chore: inicial"
git branch develop

# p9 nasce cedo (antes do p1 entrar na develop)
git switch -qc development/p9 develop; echo p9 > p9.txt; c "feat(p9): tela"

# T1
git switch -qc development/p1 develop; echo p1a > p1a.txt; c "feat(p1): a"; echo p1b > p1b.txt; c "feat(p1): b"
M1=$(mergedev p1); promover "$M1" -x
# T2
git switch -qc development/p2 develop; echo p2a > p2a.txt; c "feat(p2): a"; echo p2b > p2b.txt; c "feat(p2): b"
M2=$(mergedev p2); promover "$M2" ""
# T3: correção direta na produção; p3 incorpora a master (herda o trecho) e é promovido com -x -m 1
git switch -q master; printf 'linha b\n' > shared.txt; c "fix: corrige linha direto na produção"; git switch -q develop
git switch -qc development/p3 develop; echo p3a > p3a.txt; c "feat(p3): a"; echo p3b > p3-b.txt; c "feat(p3): b"; git merge -q --no-ff master -m "Merge branch 'master' into development/p3"
M3=$(mergedev p3); promover "$M3" -x
# T3b: outra correção direta; p3b incorpora a master e NÃO é promovido
git switch -q master; printf 'linha b\n' > shared2.txt; c "fix: corrige shared2 direto na produção"; git switch -q develop
git switch -qc development/p3b develop; echo p3b > p3b.txt; c "feat(p3b): tela"; git merge -q --no-ff master -m "Merge branch 'master' into development/p3b"
M3B=$(mergedev p3b)
# T4
git switch -qc development/p4 develop; echo p4a > p4a.txt; c "feat(p4): a"; echo p4b > p4b.txt; c "feat(p4): b"
M4=$(mergedev p4); git switch -q master; git cherry-pick -x -m 1 "$M4" >/dev/null
echo "p4a editado na produção" > p4a.txt; git add p4a.txt; git commit -q --amend --no-edit; git switch -q develop
# T5a: a base muda a mesma linha por outro caminho, com conteúdo ligeiramente diferente
# (diferenças só de espaços não servem: o patch-id as ignora e o commit seria reconhecido por conteúdo)
git switch -q master; printf 'x = 2 # hotfix\n' > conf.txt; c "fix: ajusta x direto na produção"; git switch -q develop
git switch -qc development/p5 develop; printf 'x = 2\n' > conf.txt; c "feat(p5): ajusta x"
M5=$(mergedev p5)
# T5b: o conteúdo do p6 entra na base junto com outra alteração (patch diferente, sem -x)
git switch -q master; echo p6 > p6.txt; echo extra > extra.txt; c "chore: pacote de ajustes na produção"; git switch -q develop
git switch -qc development/p6 develop; echo p6 > p6.txt; c "feat(p6): tela"
M6=$(mergedev p6)
# T6: dois merges do mesmo projeto; só o primeiro promovido
git switch -qc development/p7 develop; echo p7a > p7a.txt; c "feat(p7): a"
M7A=$(mergedev p7); promover "$M7A" -x
git switch -q development/p7; echo p7b > p7b.txt; c "feat(p7): b"
M7B=$(mergedev p7)
# T7: promovido e depois revertido na base
git switch -qc development/p8 develop; echo p8a > p8a.txt; c "feat(p8): a"; echo p8b > p8b.txt; c "feat(p8): b"
M8=$(mergedev p8); promover "$M8" -x
git switch -q master; git revert --no-edit HEAD >/dev/null; git switch -q develop
# T8: p9 incorpora a branch do p1 (já na develop e promovido) e entra depois
git switch -q development/p9; git merge -q --no-ff development/p1 -m "Merge branch 'development/p1' into development/p9"
M9=$(mergedev p9)

git switch -q master
echo "Repositório pronto em $R (base master, origem develop)"
