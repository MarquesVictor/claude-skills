#!/usr/bin/env python3
"""Análise e preparação de releases seletivas (Skill release-seletiva), versão 1.1.0.

Uso:
    release.py listar    [opções comuns] [--detalhes]
    release.py planejar  [opções comuns] [--projetos A,B] [--commits SHA,...]
    release.py preparar  [opções comuns] [--projetos A,B] [--commits SHA,...]
                         --branch NOME --assinatura HASH [--aceitar-bloqueios] [--aceitar-atencao]
                         [--aceitar-divergencia] [--aceitar-parcial] [--aceitar-indeterminado]
    release.py continuar
    release.py resumo    [--branch NOME]

Opções comuns:
    --base REF      Branch de produção (padrão: master). Se existir <remoto>/<REF>, usa a remota.
    --origem REF    Branch de integração (padrão: develop). Mesma regra.
    --remoto NOME   Remoto usado para resolver as refs (padrão: origin).
    --desde DATA    Mostra/seleciona só projetos com merge na origem a partir de DATA (AAAA-MM-DD).

Projetos são identificados pelo nome da branch de origem do merge na develop
(ex.: development/financeiro) ou pelo nome curto (financeiro).

Efeitos no repositório:
    listar, planejar e resumo são somente leitura. A simulação de conflitos grava
    objetos em um diretório temporário fora do repositório, removido ao final.
    preparar cria a branch de release a partir da base e aplica `cherry-pick -x`;
    continuar retoma a fila após uma resolução manual. O estado fica em
    .git/release-seletiva-skill/ (fora do versionamento). Estados gravados pela v1.0.0 em
    .git/release-seletiva/<branch>.json continuam sendo lidos; nenhum outro arquivo dessa
    pasta (ex.: de outra ferramenta de release) é lido, alterado ou apagado.
    O script nunca faz push, merge, reset, rebase, revert, abort, nem apaga ou
    sobrescreve branches.

Autorizações do preparar (controles separados, ambos validados antes de criar a branch):
    --aceitar-bloqueios  libera alertas BLOQUEIO (branch com commits de projeto não selecionado).
    --aceitar-atencao    libera dependências ATENÇÃO de um projeto selecionado em alterações de
                         projetos não selecionados. Não libera BLOQUEIO.
    --aceitar-divergencia
                         libera o descarte de commits registrados como cherry-pick na base
                         (trailer `cherry picked from commit`) cujo conteúdo é diferente do
                         original. Sem ela, o preparar recusa. Para reaplicar um desses commits
                         em vez de descartá-lo, selecione-o explicitamente com --commits.
                         Vale para o commit individual e para o merge inteiro (mesma situação:
                         trailer na base com conteúdo diferente).
    --aceitar-parcial    libera aplicar só o restante de um projeto que já tem parte em produção.
    --aceitar-indeterminado
                         libera manter fora da release os commits de um merge INDETERMINADO.
    Nenhuma autorização libera outra. Dependências, divergências, parciais e indeterminados fazem
    parte da assinatura: se mudarem, a assinatura confirmada deixa de valer.

Detecção de commits já em produção (método mostrado em `listar --detalhes`):
  Por commit (cherry-pick individual):
    patch-id     conteúdo equivalente na base (com ou sem trailer): promovido.
    trailer      trailer na base, mas conteúdo diferente: DIVERGENTE, continua pendente
                 até ser revisado (alerta ATENÇÃO e --aceitar-divergencia).
    heurística   mesmo autor, data e assunto, conteúdo diferente: SUSPEITO, continua no plano.
  Por merge (`cherry-pick -x -m 1` do merge da origem), só para o que a camada por commit não
  resolveu; compara a diferença do merge em relação ao 1º pai (M^1..M):
    merge -x + patch-id      trailer aponta para M e o conteúdo é igual: CONFIRMADO.
    merge -x + reprodução    trailer aponta para M e reaplicar M sobre o pai do commit da base
                             gera exatamente a mesma árvore, sem conflito: CONFIRMADO.
    merge -x, diferente      trailer aponta para M, sem conteúdo igual nem reprodução: DIVERGENTE.
    merge, conteúdo          sem trailer, um único commit da base com o mesmo conteúdo:
                             EQUIVALENTE (sem rastreabilidade comprovada).
    sem evidência            reaplicar não muda nada, conteúdo ambíguo ou conflito em arquivos que
                             a base alterou por commits sem correspondência na origem: INDETERMINADO.
  Reaplicar sem produzir alteração nunca basta para considerar um projeto promovido.
  O plano nunca aplica commits de merge: só os commits do projeto. Alterações herdadas por merges
  internos (de outros projetos ou da base) não são reaplicadas.

Códigos de saída:
    0  Sucesso.
    1  Erro de uso ou validação (nada foi alterado pelo comando).
    2  Erro do git ou do repositório.
    3  Parado em conflito: cherry-pick em andamento aguardando resolução manual.
    No `resumo`, o código 1 também indica release incompleta ou com divergências.

Requer Python 3.8+ (biblioteca padrão) e git 2.23+ (simulação de conflitos: git 2.45+).
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict

SEP_REG = "\x1e"
SEP_CAMPO = "\x1f"
LIMITE_COMMITS_LISTA = 8
RE_TRAILER = re.compile(r"cherry picked from commit ([0-9a-f]{40})")
RE_REVERT = re.compile(r"This reverts commit ([0-9a-f]{40})")
DIR_ESTADO = "release-seletiva-skill"
DIR_ESTADO_LEGADO = "release-seletiva"   # v1.0.0; compartilhado com outras ferramentas em alguns repositórios
TRACAVEIS = ("patch-id + trailer", "patch-id + trailer do merge", "merge -x + patch-id", "merge -x + reprodução")
PADROES_MERGE = [
    re.compile(r"^Merge (?:remote-tracking )?branch '([^']+)'"),
    re.compile(r'^Merge (?:remote-tracking )?branch "([^"]+)"'),
    re.compile(r"^Merge pull request #\d+ from [^/\s]+/(\S+)"),
    re.compile(r"^Merged in (\S+) \(pull request #\d+\)"),
]
RE_BANCO = re.compile(r"(\.sql$|migrat)", re.I)


class ErroUso(Exception):
    pass


class ErroGit(Exception):
    pass


# --------------------------------------------------------------------------- git

def executar_git(args, check=True, env=None, entrada=None):
    proc = subprocess.run(
        ["git"] + list(args), input=entrada, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, encoding="utf-8", errors="replace",
    )
    if check and proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()
        raise ErroGit("`git %s` falhou: %s" % (" ".join(args), msg))
    return proc


def g(*args):
    return executar_git(args).stdout


def existe_commit(ref):
    return executar_git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"], check=False).returncode == 0


def sha_de(ref):
    return g("rev-parse", "--verify", ref + "^{commit}").strip()


def caminho_git(nome):
    return os.path.abspath(g("rev-parse", "--git-path", nome).strip())


def head_sha():
    return g("rev-parse", "HEAD").strip()


def branch_atual():
    p = executar_git(["symbolic-ref", "--short", "-q", "HEAD"], check=False)
    return p.stdout.strip() if p.returncode == 0 else None


def cherry_pick_em_andamento():
    return os.path.exists(caminho_git("CHERRY_PICK_HEAD"))


def arquivos_em_conflito():
    return [l for l in g("diff", "--name-only", "--diff-filter=U").splitlines() if l]


def curto(sha):
    return sha[:9]


class ObjetosTemporarios(object):
    """`git merge-tree` gravando objetos num diretório temporário: o repositório não é alterado."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="release-seletiva-")
        self.env = dict(os.environ, GIT_OBJECT_DIRECTORY=self.dir,
                        GIT_ALTERNATE_OBJECT_DIRECTORIES=caminho_git("objects"))
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def merge_tree(self, merge_base, nosso, deles):
        """Retorna (estado, árvore, arquivos em conflito); estado: ok, conflito ou erro."""
        p = executar_git(["merge-tree", "--write-tree", "--name-only", "--no-messages",
                          "--merge-base=" + merge_base, nosso, deles], check=False, env=self.env)
        linhas = p.stdout.splitlines()
        if p.returncode == 0 and linhas:
            return "ok", linhas[0].strip(), []
        if p.returncode == 1 and linhas:
            return "conflito", linhas[0].strip(), [l for l in linhas[1:] if l.strip()]
        return "erro", None, []


def resumir(itens, limite):
    itens = list(itens)
    texto = ", ".join(itens[:limite])
    return texto + (" e mais %d" % (len(itens) - limite) if len(itens) > limite else "")


# ---------------------------------------------------------------- resolução de refs

def resolver_ref(nome, remoto, avisos):
    remota = "%s/%s" % (remoto, nome)
    if not nome.startswith(remoto + "/") and existe_commit("refs/remotes/" + remota):
        sha = sha_de("refs/remotes/" + remota)
        if existe_commit("refs/heads/" + nome) and sha_de("refs/heads/" + nome) != sha:
            avisos.append("A branch local '%s' difere de '%s'; usando '%s'." % (nome, remota, remota))
        return remota, sha
    if existe_commit(nome):
        return nome, sha_de(nome)
    raise ErroUso("Referência não encontrada: '%s' (nem '%s'). Informe --base/--origem." % (nome, remota))


def aviso_fetch(avisos):
    caminho = caminho_git("FETCH_HEAD")
    if not os.path.exists(caminho):
        avisos.append("Não há registro de `git fetch` neste repositório; as refs remotas podem estar desatualizadas.")
        return
    idade = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(caminho))
    if idade > datetime.timedelta(hours=12):
        avisos.append("Último `git fetch` há %d h; as refs remotas podem estar desatualizadas." % (idade.total_seconds() // 3600))


# ------------------------------------------------------------------------- análise

class Commit(object):
    __slots__ = ("sha", "pais", "autor", "email", "at", "ct", "data", "assunto", "arquivos", "ordem")

    def __init__(self, campos, arquivos, ordem):
        self.sha, pais, self.autor, self.email, self.at, self.ct, self.data, self.assunto = campos
        self.pais = pais.split()
        self.arquivos = set(arquivos)
        self.ordem = ordem

    @property
    def merge(self):
        return len(self.pais) > 1


class Projeto(object):
    def __init__(self, chave):
        self.chave = chave
        self.merges = []      # merges na first-parent da origem
        self.commits = []     # commits sem merge atribuídos ao projeto
        self.internos = []    # merges internos da branch do projeto
        self.pontas = []      # pais não principais dos merges na origem

    @property
    def nome_curto(self):
        return self.chave.split("/", 1)[1] if self.chave.startswith("development/") else self.chave


def nome_branch(assunto, remoto):
    for padrao in PADROES_MERGE:
        m = padrao.match(assunto)
        if m:
            nome = m.group(1)
            if nome.startswith(remoto + "/"):
                nome = nome[len(remoto) + 1:]
            return nome
    return None


class Analise(object):
    def __init__(self, base_ref, base_sha, origem_ref, origem_sha, remoto, desde=None):
        self.base_ref, self.base_sha = base_ref, base_sha
        self.origem_ref, self.origem_sha = origem_ref, origem_sha
        self.remoto = remoto
        self.desde = desde
        self.commits = OrderedDict()
        self.projetos = OrderedDict()
        self.avulsos = []
        self.dono = {}
        self.promovidos = {}   # sha -> descrição
        self.suspeitos = {}    # sha -> sha na base
        self.divergentes = {}  # sha -> sha na base (trailer de cherry-pick, conteúdo diferente)
        self.metodo = {}       # sha -> (método de detecção, sha na base)
        self.patch_id = {}
        self.resolucoes = {}   # merge -> arquivos com resolução manual
        self.introduzidos = {}  # merge da origem -> commits (sem merge) que ele trouxe
        self.base_pid = {}      # commit da base (janela) -> patch-id
        self.pid_contagem = {}  # patch-id -> quantos commits da base o têm
        self.base_trailers = {}  # commit da base -> origens citadas em `cherry picked from commit`
        self.trailer_merge = {}  # merge da origem -> commits da base que o citam
        self.revertidos = {}    # commit da base -> commit da base que o reverte
        self.unidades = {}      # merge da origem -> avaliação no nível de merge
        self.via_merge = {}     # commit promovido pela camada de merge -> merge
        self.revisao = {}       # commit que exige revisão (merge divergente/indeterminado) -> merge
        self.janela = None
        self._carregar()
        self._atribuir()
        self._patch_ids()
        self._promovidos()
        self._merges()
        self._resolucoes()

    # -- carga
    def _carregar(self):
        fmt = SEP_REG + SEP_CAMPO.join(["%H", "%P", "%an", "%ae", "%at", "%ct", "%ad", "%s"])
        out = g("-c", "core.quotepath=off", "log", "--no-renames", "--name-only", "--topo-order",
                "--reverse", "--date=short", "--format=" + fmt, "%s..%s" % (self.base_sha, self.origem_sha))
        for i, bloco in enumerate(out.split(SEP_REG)[1:]):
            linhas = bloco.split("\n")
            campos = linhas[0].split(SEP_CAMPO)
            c = Commit(campos, [l for l in linhas[1:] if l.strip()], i)
            self.commits[c.sha] = c
        self.primeiro_pai = g("rev-list", "--first-parent", "--reverse",
                              "%s..%s" % (self.base_sha, self.origem_sha)).split()
        self.fp = set(self.primeiro_pai)

    def _atribuir(self):
        visitados = set()
        for m in self.primeiro_pai:
            visitados.add(m)
            cm = self.commits[m]
            if not cm.merge:
                self.dono[m] = "avulso"
                self.avulsos.append(m)
                continue
            chave = nome_branch(cm.assunto, self.remoto) or "merge-%s" % curto(m)
            proj = self.projetos.setdefault(chave, Projeto(chave))
            proj.merges.append(m)
            proj.pontas.extend(cm.pais[1:])
            self.dono[m] = chave
            trazidos = self.introduzidos.setdefault(m, [])
            pilha = list(cm.pais[1:])
            while pilha:
                c = pilha.pop()
                if c in visitados or c not in self.commits:
                    continue
                visitados.add(c)
                self.dono[c] = chave
                (proj.internos if self.commits[c].merge else proj.commits).append(c)
                if not self.commits[c].merge:
                    trazidos.append(c)
                pilha.extend(self.commits[c].pais)
        for proj in self.projetos.values():
            proj.commits.sort(key=lambda s: self.commits[s].ordem)
            proj.internos.sort(key=lambda s: self.commits[s].ordem)

    def _promovidos(self):
        """Compara pelo conteúdo (patch-id), pelo registro do `cherry-pick -x` e, como suspeita, por autor/data/assunto.

        Não usa só a diferença simétrica base...origem: cherry-picks já feitos na base podem ter
        chegado à origem (ex.: branch criada a partir da master) e mesmo assim são produção.
        """
        sem_merge = [c for c in self.commits.values() if not c.merge]
        if not sem_merge:
            return
        inicio = datetime.datetime.fromtimestamp(min(int(c.ct) for c in sem_merge) - 86400)
        janela = ["--no-merges", "--since=" + inicio.strftime("%Y-%m-%d %H:%M:%S"), self.base_sha]
        self.janela = janela
        log = g("log", "-p", "--format=commit %H", *janela)
        pids_base = {}
        for linha in executar_git(["patch-id", "--stable"], entrada=log).stdout.splitlines():
            pid, sha = linha.split()
            pids_base.setdefault(pid, sha)
            self.base_pid[sha] = pid
            self.pid_contagem[pid] = self.pid_contagem.get(pid, 0) + 1
        for c in sem_merge:
            pid = self.patch_id.get(c.sha)
            if pid in pids_base:
                self.promovidos[c.sha] = "patch equivalente já está na base (%s)" % curto(pids_base[pid])
                self.metodo[c.sha] = ("patch-id", pids_base[pid])
        fmt = SEP_REG + SEP_CAMPO.join(["%H", "%ae", "%at", "%s", "%B"])
        out = g("log", "--format=" + fmt, *janela)
        indice = {}
        for bloco in out.split(SEP_REG)[1:]:
            sha, email, at, assunto, corpo = bloco.split(SEP_CAMPO, 4)
            origens = RE_TRAILER.findall(corpo)
            if origens:
                self.base_trailers[sha] = origens
            for rev in RE_REVERT.findall(corpo):
                self.revertidos.setdefault(rev, sha)
            for orig in origens:
                if orig in self.commits and self.commits[orig].merge:
                    # `cherry-pick -x -m 1` de um merge: avaliado na camada de merge (_merges)
                    self.trailer_merge.setdefault(orig, []).append(sha)
                    continue
                if orig not in self.commits:
                    continue
                if orig in self.promovidos:
                    if self.metodo.get(orig) == ("patch-id", sha):
                        self.metodo[orig] = ("patch-id + trailer", sha)
                elif orig not in self.divergentes:
                    # o trailer só registra a intenção: sem patch equivalente na base, a promoção pode
                    # ter sido parcial ou adaptada. Não conta como promovido; exige revisão.
                    self.divergentes[orig] = sha
                    self.metodo[orig] = ("trailer, conteúdo diferente", sha)
            indice[(email, at, assunto)] = sha
        for sha, c in self.commits.items():
            if c.merge or sha in self.promovidos or sha in self.divergentes:
                continue
            chave = (c.email, c.at, c.assunto)
            if chave in indice:
                self.suspeitos[sha] = indice[chave]
                self.metodo[sha] = ("heurística", indice[chave])

    def _patch_ids(self):
        pendentes = [s for s, c in self.commits.items() if not c.merge]
        if not pendentes:
            return
        log = executar_git(["log", "--no-walk=unsorted", "--stdin", "-p", "--format=commit %H"],
                           entrada="\n".join(pendentes) + "\n").stdout
        out = executar_git(["patch-id", "--stable"], entrada=log).stdout
        for linha in out.splitlines():
            pid, sha = linha.split()
            self.patch_id[sha] = pid

    # -- camada de merge: promoções por `cherry-pick -x -m 1` do merge da origem
    def _diffs_merges(self, merges):
        """merge -> (patch-id da diferença M^1..M ou None, arquivos dessa diferença). Uma chamada em lote."""
        entrada = "\n".join(merges) + "\n"
        p = executar_git(["-c", "core.quotepath=off", "log", "--no-walk=unsorted", "--stdin",
                          "--diff-merges=first-parent", "-p", "--format=commit %H"], check=False, entrada=entrada)
        if p.returncode == 0:
            texto = p.stdout
        else:  # git sem --diff-merges: um diff por merge
            texto = "".join("commit %s\n\n%s" % (m, g("-c", "core.quotepath=off", "diff", self.commits[m].pais[0], m))
                            for m in merges)
        arquivos, atual = {}, None
        for linha in texto.splitlines():
            if linha.startswith("commit ") and len(linha) == 47:
                atual = linha[7:]
                arquivos[atual] = set()
            elif linha.startswith("diff --git ") and atual:
                arquivos[atual].add(linha.rsplit(" b/", 1)[-1])
        pids = {}
        for linha in executar_git(["patch-id", "--stable"], entrada=texto).stdout.splitlines():
            pid, sha = linha.split()
            pids[sha] = pid
        return dict((m, (pids.get(m), arquivos.get(m, set()))) for m in merges)

    def _arquivos_alheios(self, pids_origem):
        """Arquivos alterados por commits que só existem na base (origem..base, na janela de datas) e não
        têm correspondência na origem (nem trailer, nem patch-id) -> commits. Ex.: correção direta na produção."""
        alheios = {}
        if not self.janela:
            return alheios
        out = g("-c", "core.quotepath=off", "log", "--no-renames", "--name-only",
                "--format=" + SEP_REG + "%H" + SEP_CAMPO, *(self.janela[:-1] + ["^" + self.origem_sha, self.base_sha]))
        for bloco in out.split(SEP_REG)[1:]:
            sha, nomes = bloco.split(SEP_CAMPO, 1)
            if any(o in self.commits for o in self.base_trailers.get(sha, [])):
                continue
            if self.base_pid.get(sha) in pids_origem:
                continue
            for f in nomes.splitlines():
                if f.strip():
                    alheios.setdefault(f.strip(), []).append(sha)
        return alheios

    def _merges(self):
        # commit reconhecido por patch-id cujo commit na base cita (-x) o merge que o introduziu: rastreável
        for c, (metodo, b) in list(self.metodo.items()):
            if metodo == "patch-id" and any(o in self.commits and c in self.introduzidos.get(o, [])
                                            for o in self.base_trailers.get(b, [])):
                self.metodo[c] = ("patch-id + trailer do merge", b)
        alvo = []
        for proj in self.projetos.values():
            for m in proj.merges:
                trazidos = self.introduzidos.get(m, [])
                if trazidos and any(c not in self.promovidos for c in trazidos):
                    alvo.append(m)
        if not alvo:
            return
        diffs = self._diffs_merges(alvo)
        pids_origem = set(self.patch_id.values()) | set(p for p, _ in diffs.values() if p)
        self._alheios_cache = None
        self._diferentes_cache = None
        base_tree = g("rev-parse", self.base_sha + "^{tree}").strip()
        with ObjetosTemporarios() as tmp:
            for m in alvo:
                u = self._avaliar_merge(m, diffs[m], tmp, base_tree, pids_origem)
                self.unidades[m] = u
                pend = [c for c in self.introduzidos[m] if c not in self.promovidos]
                if u["situacao"] in ("confirmado", "equivalente"):
                    for c in pend:
                        self.promovidos[c] = "promovido pelo merge %s em %s (%s)" % (curto(m), curto(u["base"]), u["metodo"])
                        self.metodo[c] = (u["metodo"], u["base"])
                        self.via_merge[c] = m
                        self.suspeitos.pop(c, None)
                        self.divergentes.pop(c, None)
                elif u["situacao"] in ("divergente", "indeterminado"):
                    for c in pend:
                        if c not in self.divergentes:
                            self.revisao[c] = m

    def _avaliar_merge(self, m, diff, tmp, base_tree, pids_origem):
        pid_m, arquivos_m = diff
        trazidos = self.introduzidos[m]
        pend = [c for c in trazidos if c not in self.promovidos]
        u = {"merge": m, "base": None, "metodo": None, "situacao": "pendente", "motivo": "",
             "herdados": sorted(arquivos_m - self.arquivos(trazidos)), "revertido": None}
        pai = self.commits[m].pais[0]
        bases = self.trailer_merge.get(m, [])
        if bases:
            resultados = []
            for b in bases:
                if pid_m and self.base_pid.get(b) == pid_m:
                    resultados.append(("merge -x + patch-id", b))
                    continue
                estado, arvore, _ = tmp.merge_tree(pai, b + "^1", m)
                if estado == "ok" and arvore == g("rev-parse", b + "^{tree}").strip():
                    resultados.append(("merge -x + reprodução", b))
                elif estado == "erro":
                    resultados.append(("indisponível", b))
                else:
                    resultados.append((None, b))
            confirmados = [r for r in resultados if r[0] not in (None, "indisponível")]
            if confirmados and len(confirmados) == len(resultados):
                u.update(situacao="confirmado", metodo=confirmados[0][0], base=confirmados[0][1],
                         revertido=self.revertidos.get(confirmados[0][1]))
            elif confirmados:
                u.update(situacao="indeterminado", base=confirmados[0][1],
                         motivo="citado por %d commits da base (%s) com resultados diferentes"
                         % (len(resultados), ", ".join(curto(b) for _, b in resultados)))
            elif any(r[0] == "indisponível" for r in resultados):
                u.update(situacao="indeterminado", base=bases[0],
                         motivo="registrado como cherry-pick em %s, conteúdo diferente e reprodução indisponível "
                                "(requer git 2.45+)" % curto(bases[0]))
            else:
                u.update(situacao="divergente", metodo="merge -x, diferente", base=bases[0],
                         motivo="registrado como cherry-pick em %s, mas o conteúdo é diferente e reaplicar o merge "
                                "sobre %s^1 não reproduz o commit (edição manual ou promoção parcial); revise com "
                                "`git diff %s^1 %s` × `git show %s`" % (curto(bases[0]), curto(bases[0]),
                                                                          curto(m), curto(m), curto(bases[0])))
            return u
        if pid_m and self.pid_contagem.get(pid_m) == 1:
            b = next(s for s, p in self.base_pid.items() if p == pid_m)
            u.update(situacao="equivalente", metodo="merge, conteúdo equivalente", base=b,
                     revertido=self.revertidos.get(b))
            return u
        if pid_m and self.pid_contagem.get(pid_m, 0) > 1:
            u.update(situacao="indeterminado", motivo="o conteúdo do merge aparece em %d commits da base, sem registro "
                     "de cherry-pick (correspondência ambígua)" % self.pid_contagem[pid_m])
            return u
        if len(pend) < len(trazidos):
            u.update(situacao="parcial", motivo="%d de %d commit(s) já estão na base (por commit)"
                     % (len(trazidos) - len(pend), len(trazidos)))
            return u
        if any(c in self.suspeitos or c in self.divergentes for c in pend):
            return u   # já sinalizado pela camada por commit (suspeito/divergente)
        arquivos_pend = sorted(self.arquivos(pend))
        if self._diferentes_cache is None:   # uma chamada para todos os merges
            self._diferentes_cache = set(l for l in g("-c", "core.quotepath=off", "diff", "--name-only", "--no-renames",
                                                       self.base_sha, self.origem_sha).splitlines() if l)
        if arquivos_pend and not any(f in self._diferentes_cache for f in arquivos_pend):
            u.update(situacao="indeterminado", motivo="os arquivos do projeto (%s) já estão idênticos na base e na "
                     "origem: o conteúdo atual da origem já está na produção, mas não há registro de promoção (a "
                     "alteração pode ter sido absorvida ou reescrita por outro merge)" % resumir(arquivos_pend, 3))
            return u
        estado, arvore, conflitos = tmp.merge_tree(pai, self.base_sha, m)
        if estado == "ok" and arvore == base_tree:
            u.update(situacao="indeterminado", motivo="reaplicar o merge não muda nada na base, mas não há registro de "
                     "cherry-pick nem commit com o mesmo conteúdo: a alteração pode ter entrado por outro caminho")
        elif estado == "conflito":
            if self._alheios_cache is None:
                self._alheios_cache = self._arquivos_alheios(pids_origem)
            alheios = [(f, self._alheios_cache[f]) for f in conflitos if f in self._alheios_cache]
            if alheios:
                u.update(situacao="indeterminado", motivo="conflito em %s, que a base alterou por commit(s) sem "
                         "correspondência na origem (%s): parte da alteração pode já estar na base" % (
                             resumir([f for f, _ in alheios], 3),
                             resumir(sorted(set(curto(s) for _, ss in alheios for s in ss)), 4)))
        return u

    def promocao_revertida(self, proj):
        """Algum commit da base que promoveu o projeto foi revertido depois (`This reverts commit`)."""
        return any(self.metodo.get(c, (None, None))[1] in self.revertidos for c in proj.commits if c in self.promovidos)

    def situacao(self, proj):
        """confirmado | equivalente | parcial | pendente | indeterminado | divergente | sem-commits."""
        if not proj.commits:
            return "sem-commits"
        pend = self.pendentes(proj)
        if not pend:
            return "confirmado" if all(self.metodo.get(c, ("",))[0] in TRACAVEIS for c in proj.commits) \
                else "equivalente"
        if any(c in self.divergentes for c in pend) or \
                any(self.unidades.get(self.revisao[c], {}).get("situacao") == "divergente" for c in pend if c in self.revisao):
            return "divergente"
        if any(c in self.revisao for c in pend):
            return "indeterminado"
        if len(pend) < len(proj.commits):
            return "parcial"
        return "pendente"

    def _resolucoes(self):
        for proj in self.projetos.values():
            if not self.pendentes(proj):
                continue
            for m in proj.merges + proj.internos:
                out = g("-c", "core.quotepath=off", "diff-tree", "--cc", "--name-only", "--no-commit-id", "-r", m)
                arquivos = [l for l in out.splitlines() if l.strip()]
                if arquivos:
                    self.resolucoes[m] = arquivos

    # -- consultas
    def pendentes(self, proj):
        return [c for c in proj.commits if c not in self.promovidos]

    def visivel(self, proj):
        if not self.desde:
            return True
        return any(self.commits[m].data >= self.desde for m in proj.merges)

    def arquivos(self, shas):
        r = set()
        for s in shas:
            r |= self.commits[s].arquivos
        return r

    def ancestrais(self, inicio, parar_na_origem):
        vistos, pilha = set(), list(inicio)
        while pilha:
            c = pilha.pop()
            if c in vistos or c not in self.commits:
                continue
            if parar_na_origem and c in self.fp:
                continue
            vistos.add(c)
            pilha.extend(self.commits[c].pais)
        return vistos

    def entrelacados(self, proj):
        """Ligações pela branch (não pela develop) com commits pendentes de outros projetos.

        Retorna (depende_de, base_para):
        - depende_de: a branch de `proj` contém commits atribuídos a outro projeto, que não
          vão junto se só `proj` for selecionado;
        - base_para: commits de `proj` também estão na branch de outro projeto.
        """
        depende, base = {}, {}
        for c in self.ancestrais(proj.pontas, True):
            dono = self.dono.get(c)
            if dono and dono != proj.chave and dono != "avulso" and c not in self.promovidos \
                    and not self.commits[c].merge:
                depende.setdefault(dono, set()).add(c)
        for outro in self.projetos.values():
            if outro.chave == proj.chave or not self.pendentes(outro):
                continue
            for c in self.ancestrais(outro.pontas, True):
                if self.dono.get(c) == proj.chave and c not in self.promovidos and not self.commits[c].merge:
                    base.setdefault(outro.chave, set()).add(c)
        return depende, base

    def projetos_pendentes(self):
        return [p for p in self.projetos.values() if self.pendentes(p) and self.visivel(p)]

    def resolver_projeto(self, nome):
        if nome in self.projetos:
            return self.projetos[nome]
        achados = [p for p in self.projetos.values() if p.nome_curto == nome or p.chave.endswith("/" + nome)]
        if len(achados) == 1:
            return achados[0]
        if len(achados) > 1:
            raise ErroUso("Nome de projeto ambíguo: '%s' (%s)." % (nome, ", ".join(p.chave for p in achados)))
        raise ErroUso("Projeto não encontrado entre %s..%s: '%s'. Use `listar`." % (self.base_ref, self.origem_ref, nome))

    def resolver_commit(self, ref):
        p = executar_git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"], check=False)
        sha = p.stdout.strip()
        if p.returncode != 0 or sha not in self.commits:
            raise ErroUso("Commit '%s' não está entre %s..%s." % (ref, self.base_ref, self.origem_ref))
        if self.commits[sha].merge:
            raise ErroUso("Commit '%s' é um merge; selecione o projeto ou os commits dele." % ref)
        return sha


# -------------------------------------------------------------------------- plano

FLAG_REVISAO = {"divergente": "--aceitar-divergencia", "indeterminado": "--aceitar-indeterminado"}


class Plano(object):
    def __init__(self, analise, projetos, extras):
        a = analise
        self.analise = a
        self.projetos = projetos
        self.extras = extras
        self.ordem, self.ignorados, self.alertas = [], [], []
        self.dependencias = []   # dependências ATENÇÃO de projetos selecionados em não selecionados
        self.divergencias = []   # commits com trailer na base e conteúdo diferente, que ficariam de fora
        self.revisoes = []       # merges divergentes/indeterminados cujos commits ficariam de fora
        self.parciais = []       # projetos com parte em produção dos quais só o restante seria aplicado
        chaves = set(p.chave for p in projetos)
        self.excluidos = [p.chave for p in a.projetos.values() if a.pendentes(p) and p.chave not in chaves]
        vistos_pid = {}
        for sha, c in a.commits.items():
            if c.merge or not (a.dono.get(sha) in chaves or sha in extras):
                continue
            if sha in a.promovidos:
                self.ignorados.append((sha, "já em produção: " + a.promovidos[sha]))
                continue
            if sha in a.divergentes and sha not in extras:
                base = a.divergentes[sha]
                self.ignorados.append((sha, "registrado como cherry-pick em %s na base, mas com conteúdo diferente "
                                            "(não aplicado; exige revisão e --aceitar-divergencia)" % curto(base)))
                self.divergencias.append({"commit": sha, "base": base, "projeto": a.dono.get(sha)})
                continue
            if sha in a.revisao and sha not in extras:
                m = a.revisao[sha]
                u = a.unidades[m]
                flag = FLAG_REVISAO[u["situacao"]]
                self.ignorados.append((sha, "merge %s %s (não aplicado; exige revisão e %s)"
                                       % (curto(m), u["situacao"].upper(), flag)))
                item = next((r for r in self.revisoes if r["merge"] == m), None)
                if item is None:
                    item = {"projeto": a.dono.get(sha), "merge": m, "situacao": u["situacao"], "base": u["base"],
                            "motivo": u["motivo"], "commits": []}
                    self.revisoes.append(item)
                item["commits"].append(sha)
                continue
            pid = a.patch_id.get(sha)
            if pid and pid in vistos_pid:
                self.ignorados.append((sha, "duplicado de %s (mesmo patch)" % curto(vistos_pid[pid])))
                continue
            if pid:
                vistos_pid[pid] = sha
            self.ordem.append(sha)
        aplicar = set(self.ordem)
        for proj in projetos:
            ja = [c for c in proj.commits if c in a.promovidos]
            resto = [c for c in proj.commits if c in aplicar]
            if ja and resto:
                self.parciais.append({"projeto": proj.chave, "em_producao": len(ja), "aplicados": len(resto),
                                      "merges_promovidos": [m for m in proj.merges
                                                            if a.unidades.get(m, {}).get("situacao") in
                                                            ("confirmado", "equivalente")]})
        self._alertas(chaves)

    def _alerta(self, nivel, texto):
        self.alertas.append((nivel, texto))

    def _alertas(self, chaves):
        a = self.analise
        selecionados_shas = set(self.ordem)
        arquivos_sel = a.arquivos(self.ordem)
        for sha in self.extras:
            dono = a.dono.get(sha)
            if dono not in chaves and dono != "avulso":
                self._alerta("ATENÇÃO", "%s é um commit isolado do projeto %s, que não foi selecionado inteiro."
                             % (curto(sha), dono))
        for proj in self.projetos:
            if not proj.commits:
                donos = sorted(set(a.dono.get(c) for c in a.ancestrais(proj.pontas, True)
                                   if not a.commits[c].merge and a.dono.get(c) not in (None, proj.chave)))
                self._alerta("ATENÇÃO", "%s não tem commits próprios: os commits da branch entraram na origem pelo merge "
                             "de %s. Nada será aplicado por este projeto; selecione o outro projeto ou os commits com "
                             "--commits." % (proj.chave, resumir(donos, 4) or "outro projeto"))
            elif not a.pendentes(proj):
                self._alerta("INFO", "%s: todos os commits já estão em produção." % proj.chave)
            depende, base = a.entrelacados(proj)
            for outro, shas in sorted(depende.items()):
                if outro in chaves:
                    continue
                self._alerta("BLOQUEIO", "A branch de %s contém %d commit(s) de %s (não selecionado), recebidos pela "
                             "branch e não pela develop: não é possível isolá-lo sem eles. Ex.: %s."
                             % (proj.chave, len(shas), outro, ", ".join(curto(s) for s in sorted(shas)[:3])))
            for outro, shas in sorted(base.items()):
                if outro in chaves:
                    continue
                self._alerta("INFO", "%d commit(s) de %s também estão na branch de %s (não selecionado), que depende "
                             "deles." % (len(shas), proj.chave, outro))
            for m in proj.merges + proj.internos:
                if m in a.resolucoes:
                    onde = "merge na origem" if m in a.fp else "merge interno"
                    self._alerta("ATENÇÃO", "%s: %s %s tem resolução manual de conflito em %s; essa resolução não "
                                 "é reproduzida pelo cherry-pick." % (proj.chave, onde, curto(m), ", ".join(a.resolucoes[m][:5])))
            for m in proj.internos:
                cm = a.commits[m]
                if not any(p in a.fp or p not in a.commits for p in cm.pais[1:]):
                    self._alerta("INFO", "%s: merge interno %s (\"%s\") traz commits de outra branch para o projeto."
                                 % (proj.chave, curto(m), cm.assunto[:70]))
            # dependências pela develop: alterações não selecionadas nos mesmos arquivos, anteriores ao projeto
            deps, deps_commits = {}, {}
            arquivos_proj = a.arquivos([s for s in proj.commits if s in selecionados_shas])
            for c in a.ancestrais(proj.pontas, False):
                dono = a.dono.get(c)
                cc = a.commits[c]
                if cc.merge or c in a.promovidos or c in selecionados_shas or dono in chaves or c in self.extras:
                    continue
                comuns = cc.arquivos & arquivos_proj
                if comuns:
                    chave_dep = dono if dono != "avulso" else "commit direto %s" % curto(c)
                    deps.setdefault(chave_dep, set()).update(comuns)
                    deps_commits.setdefault(chave_dep, set()).add(c)
            if deps:
                todos = set().union(*deps.values())
                self._alerta("ATENÇÃO", "%s foi desenvolvido sobre alterações não selecionadas nos mesmos arquivos (%s), "
                             "vindas de: %s." % (proj.chave, resumir(sorted(todos), 5), resumir(sorted(deps), 6)))
                for chave_dep in sorted(deps):
                    self.dependencias.append({
                        "projeto": proj.chave, "depende_de": chave_dep, "arquivos": sorted(deps[chave_dep]),
                        "commits": sorted(deps_commits[chave_dep], key=lambda s: a.commits[s].ordem)})
        for sha in self.ordem:
            if sha in a.suspeitos:
                self._alerta("ATENÇÃO", "%s (\"%s\") parece já estar em produção como %s (mesmo autor, data e assunto, "
                             "patch diferente)." % (curto(sha), a.commits[sha].assunto[:60], curto(a.suspeitos[sha])))
        for d in self.divergencias:
            self._alerta("ATENÇÃO", "DIVERGÊNCIA: %s (\"%s\") está registrado como cherry-pick em %s na base, mas o "
                         "conteúdo é diferente; a promoção pode ter sido parcial ou adaptada. Revise com "
                         "`git range-diff %s^! %s^!`. Não será aplicado: descartá-lo exige --aceitar-divergencia; "
                         "para reaplicá-lo, selecione-o com --commits." % (
                             curto(d["commit"]), a.commits[d["commit"]].assunto[:60], curto(d["base"]),
                             curto(d["commit"]), curto(d["base"])))
        for sha in sorted(self.extras, key=lambda s: a.commits[s].ordem):
            if sha in a.divergentes:
                self._alerta("INFO", "%s está registrado como cherry-pick em %s na base com conteúdo diferente; será "
                             "reaplicado por escolha explícita (--commits) e pode conflitar ou ficar vazio."
                             % (curto(sha), curto(a.divergentes[sha])))
        for r in self.revisoes:
            self._alerta("ATENÇÃO", "%s: merge %s %s — %s. Os %d commit(s) desse merge não serão aplicados: mantê-los "
                         "fora exige %s; para reaplicá-los, selecione-os com --commits." % (
                             r["projeto"], curto(r["merge"]), r["situacao"].upper(), r["motivo"],
                             len(r["commits"]), FLAG_REVISAO[r["situacao"]]))
        for sha in sorted(self.extras, key=lambda s: a.commits[s].ordem):
            if sha in a.revisao:
                self._alerta("INFO", "%s pertence ao merge %s (%s); será reaplicado por escolha explícita (--commits) e "
                             "pode conflitar ou ficar vazio." % (curto(sha), curto(a.revisao[sha]),
                                                                 a.unidades[a.revisao[sha]]["situacao"].upper()))
        for p in self.parciais:
            self._alerta("ATENÇÃO", "PARCIAL: %s já tem %d commit(s) em produção%s; serão aplicados só os %d restantes. "
                         "Confirme que o restante faz sentido sozinho (--aceitar-parcial)." % (
                             p["projeto"], p["em_producao"],
                             " (merges promovidos: %s)" % ", ".join(curto(m) for m in p["merges_promovidos"])
                             if p["merges_promovidos"] else "", p["aplicados"]))
        por_arquivo = {}
        for proj in a.projetos_pendentes():
            if proj.chave in chaves:
                continue
            for f in a.arquivos(a.pendentes(proj)) & arquivos_sel:
                por_arquivo.setdefault(f, []).append(proj.nome_curto)
        if por_arquivo:
            itens = ["%s (%s)" % (f, resumir(donos, 4)) for f, donos in sorted(por_arquivo.items())]
            self._alerta("INFO", "Arquivos da release também alterados por projetos não selecionados: %s."
                         % resumir(itens, 5))
        for f in sorted(arquivos_sel):
            if RE_BANCO.search(f):
                self._alerta("INFO", "Alteração de banco de dados na release: %s." % f)

    @property
    def bloqueios(self):
        return [t for n, t in self.alertas if n == "BLOQUEIO"]

    def assinatura(self):
        # inclui as dependências completas (não só o texto resumido do alerta): qualquer mudança nelas
        # invalida a assinatura e, com ela, uma autorização --aceitar-atencao dada para o plano anterior
        dados = {"base": self.analise.base_sha, "origem": self.analise.origem_sha,
                 "ordem": self.ordem, "alertas": self.alertas,
                 "dependencias": self.dependencias, "excluidos": self.excluidos}
        if self.divergencias:   # só quando existem, para não alterar assinaturas de planos sem divergência
            dados["divergencias"] = self.divergencias
        if self.revisoes:
            dados["revisoes"] = self.revisoes
        if self.parciais:
            dados["parciais"] = self.parciais
        return hashlib.sha256(json.dumps(dados, sort_keys=True).encode("utf-8")).hexdigest()[:12]

    def revisoes_de(self, situacao):
        return [r for r in self.revisoes if r["situacao"] == situacao]

    def linhas_revisoes(self, situacao, prefixo="  "):
        return ["%s- %s [%s] merge %s: %d commit(s) ficam fora da release%s" % (
            prefixo, r["situacao"].upper(), r["projeto"], curto(r["merge"]), len(r["commits"]),
            "; base tem %s" % curto(r["base"]) if r["base"] else "") for r in self.revisoes_de(situacao)]

    def linhas_parciais(self, prefixo="  "):
        return ["%s- %s: %d commit(s) já em produção, %d a aplicar" % (
            prefixo, p["projeto"], p["em_producao"], p["aplicados"]) for p in self.parciais]

    def linhas_divergencias(self, prefixo="  "):
        return ["%s- %s [%s] fica fora da release; base tem %s com conteúdo diferente" % (
            prefixo, curto(d["commit"]), d["projeto"], curto(d["base"])) for d in self.divergencias]

    def linhas_dependencias(self, prefixo="  "):
        linhas = []
        for d in self.dependencias:
            linhas.append("%s- %s depende de %s em %s (commits não incluídos: %s)" % (
                prefixo, d["projeto"], d["depende_de"], resumir(d["arquivos"], 5),
                resumir([curto(s) for s in d["commits"]], 6)))
        return linhas

    def linha_excluidos(self):
        return "Projetos pendentes que ficam FORA da release: %d%s" % (
            len(self.excluidos), (" — " + ", ".join(self.excluidos)) if self.excluidos else "")


def simular(analise, ordem):
    """Aplica a fila em memória com `git merge-tree`, sem tocar no repositório."""
    resultado = OrderedDict()
    objetos = caminho_git("objects")
    tmp = tempfile.mkdtemp(prefix="release-seletiva-")
    env = dict(os.environ, GIT_OBJECT_DIRECTORY=tmp, GIT_ALTERNATE_OBJECT_DIRECTORIES=objetos)
    try:
        arvore = g("rev-parse", analise.base_sha + "^{tree}").strip()
        for sha in ordem:
            pai = analise.commits[sha].pais[0]
            p = executar_git(["merge-tree", "--write-tree", "--name-only", "--no-messages",
                              "--merge-base=" + pai, arvore, sha], check=False, env=env)
            if p.returncode == 0:
                nova = p.stdout.split()[0]
                resultado[sha] = ("vazio", []) if nova == arvore else ("ok", [])
                arvore = nova
            elif p.returncode == 1:
                resultado[sha] = ("conflito", [l for l in p.stdout.splitlines()[1:] if l.strip()])
            else:
                return None, (p.stderr or p.stdout).strip().splitlines()[0:1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return resultado, None


# ----------------------------------------------------------------- saída de texto

def cabecalho(analise, avisos):
    a = analise
    print("Base (produção): %s @ %s" % (a.base_ref, curto(a.base_sha)))
    print("Origem:          %s @ %s" % (a.origem_ref, curto(a.origem_sha)))
    if a.desde:
        print("Filtro:          merges a partir de %s" % a.desde)
    for aviso in avisos:
        print("AVISO: " + aviso)
    print()


def linha_commit(a, sha, prefixo="      - "):
    c = a.commits[sha]
    print("%s%s %s (%s, %s)" % (prefixo, curto(sha), c.assunto[:90], c.autor, c.data))


def cmd_listar(args, analise, avisos):
    a = analise
    cabecalho(a, avisos)
    pendentes = a.projetos_pendentes()
    print("PROJETOS NA ORIGEM AINDA NÃO PROMOVIDOS: %d (ordem de entrada na origem)" % len(pendentes))
    contagem = {}
    for proj in pendentes:
        contagem[a.situacao(proj)] = contagem.get(a.situacao(proj), 0) + 1
    if set(contagem) - {"pendente"}:
        print("  Situação: %s" % ", ".join("%d %s" % (contagem[s], s) for s in
                                            ("pendente", "parcial", "indeterminado", "divergente") if s in contagem))
    for i, proj in enumerate(pendentes, 1):
        pend = a.pendentes(proj)
        datas = [a.commits[m].data for m in proj.merges]
        autores = sorted(set(a.commits[s].autor for s in pend))
        arquivos = a.arquivos(pend)
        print()
        print("[%d] %s   (nome curto: %s)" % (i, proj.chave, proj.nome_curto))
        situacao = a.situacao(proj)
        if situacao != "pendente":
            print("    Situação: %s" % ROTULO_SITUACAO[situacao])
        print("    Merges na origem: %d (%s → %s): %s" % (len(proj.merges), datas[0], datas[-1],
                                                         ", ".join(curto(m) for m in proj.merges)))
        divergentes = [s for s in pend if s in a.divergentes]
        print("    Commits: %d pendente(s), %d já em produção, %d suspeito(s)%s"
              % (len(pend), len(proj.commits) - len(pend), sum(1 for s in pend if s in a.suspeitos),
                 ", %d divergente(s)" % len(divergentes) if divergentes else ""))
        print("    Autores: %s" % ", ".join(autores))
        print("    Arquivos: %d — %s" % (len(arquivos), ", ".join(sorted(arquivos)[:6]) + (" …" if len(arquivos) > 6 else "")))
        mostrar = pend if args.detalhes else pend[-LIMITE_COMMITS_LISTA:]
        if len(mostrar) < len(pend):
            print("      (+%d commits mais antigos; use --detalhes)" % (len(pend) - len(mostrar)))
        for s in mostrar:
            linha_commit(a, s)
        if args.detalhes:
            imprimir_deteccao(a, proj)
        for s in divergentes:
            print("    ALERTA: %s está registrado como cherry-pick em %s na base, mas com conteúdo diferente "
                  "(promoção possivelmente parcial; revisar)." % (curto(s), curto(a.divergentes[s])))
        for m in proj.merges:
            u = a.unidades.get(m)
            if u and u["situacao"] in ("divergente", "indeterminado"):
                print("    ALERTA: merge %s %s — %s." % (curto(m), u["situacao"].upper(), u["motivo"]))
        depende, base = a.entrelacados(proj)
        for outro, shas in sorted(depende.items()):
            print("    ALERTA: a branch contém %d commit(s) de %s; não pode ir sem ele." % (len(shas), outro))
        for outro, shas in sorted(base.items()):
            print("    Nota: %s foi criado sobre %d commit(s) deste projeto." % (outro, len(shas)))
        for m in proj.merges + proj.internos:
            if m in a.resolucoes:
                print("    ALERTA: merge %s com resolução manual em %s" % (curto(m), ", ".join(a.resolucoes[m][:4])))
        meus_pids = set(a.patch_id.get(s) for s in pend) - {None}
        for outro in pendentes:
            if outro is not proj:
                dups = [s for s in a.pendentes(outro) if a.patch_id.get(s) in meus_pids]
                if dups:
                    print("    Mesmo conteúdo (hash diferente) em %s: %s" % (outro.nome_curto, ", ".join(curto(s) for s in dups)))
        comuns = []
        for outro in pendentes:
            if outro is not proj and arquivos & a.arquivos(a.pendentes(outro)):
                comuns.append(outro.nome_curto)
        if comuns:
            print("    Arquivos em comum com: %s" % resumir(comuns, 8))
    avulsos = [s for s in a.avulsos if s not in a.promovidos and (not a.desde or a.commits[s].data >= a.desde)]
    if avulsos:
        print()
        print("COMMITS DIRETOS NA ORIGEM (sem merge), selecionáveis com --commits:")
        for s in avulsos:
            linha_commit(a, s, "    - ")
    promovidos = [p for p in a.projetos.values() if not a.pendentes(p) and a.visivel(p)]
    print()
    print("Projetos já promovidos (ocultos): %d%s" % (
        len(promovidos), " — " + ", ".join(p.nome_curto for p in promovidos) if args.detalhes and promovidos else ""))
    revertidos = [p.nome_curto for p in promovidos if a.promocao_revertida(p)]
    if revertidos:
        print("  ATENÇÃO: promoção revertida depois na base em %d projeto(s): %s (veja --detalhes)."
              % (len(revertidos), ", ".join(revertidos)))
    if args.detalhes:
        if promovidos:
            conf = sum(1 for p in promovidos if a.situacao(p) == "confirmado")
            sem = sum(1 for p in promovidos if a.situacao(p) == "sem-commits")
            print("  %d confirmado(s) por rastreabilidade e conteúdo; %d com conteúdo equivalente, sem rastreabilidade "
                  "comprovada%s" % (conf, len(promovidos) - conf - sem,
                                    "; %d sem commits próprios (trazidos por outro projeto)" % sem if sem else ""))
        for proj in promovidos:
            print("  [%s] %s" % (proj.chave, a.situacao(proj)))
            imprimir_deteccao(a, proj, "    ")
    return 0


ROTULO_SITUACAO = {
    "confirmado": "PROMOVIDO CONFIRMADO (rastreabilidade e conteúdo)",
    "equivalente": "CONTEÚDO EQUIVALENTE na produção, sem rastreabilidade comprovada",
    "parcial": "PARCIALMENTE PROMOVIDO: parte já está na produção (o preparar exige --aceitar-parcial)",
    "indeterminado": "INDETERMINADO: exige revisão manual (manter fora exige --aceitar-indeterminado)",
    "divergente": "DIVERGENTE: registrado na produção com conteúdo diferente (manter fora exige --aceitar-divergencia)",
}

ROTULO_METODO = {
    "patch-id": "patch-id (conteúdo equivalente)",
    "patch-id + trailer": "patch-id + trailer cherry-pick",
    "patch-id + trailer do merge": "patch-id + trailer -x do merge que trouxe o commit",
    "trailer, conteúdo diferente": "trailer cherry-pick, CONTEÚDO DIFERENTE: divergente, continua pendente",
    "heurística": "heurística (autor, data e assunto): suspeito, continua pendente",
    "merge -x + patch-id": "merge: trailer -x + patch-id igual",
    "merge -x + reprodução": "merge: trailer -x + reprodução exata sobre o pai do commit da base",
    "merge -x, diferente": "merge: trailer -x, CONTEÚDO DIFERENTE: divergente",
    "merge, conteúdo equivalente": "merge: conteúdo equivalente, SEM trailer (rastreabilidade não comprovada)",
}


def imprimir_deteccao(a, proj, recuo="    "):
    """Lista o que foi reconhecido na produção: por merge (M → commit da base) e por commit, com o método."""
    unidades = [(m, a.unidades[m]) for m in proj.merges if m in a.unidades and a.unidades[m]["situacao"] != "pendente"]
    achados = [s for s in proj.commits if s in a.metodo and s not in a.via_merge]
    herdados = [(m, a.unidades[m]["herdados"]) for m in proj.merges if a.unidades.get(m, {}).get("herdados")]
    if not unidades and not achados and not herdados:
        return
    print("%sDetecção na produção (%s):" % (recuo, a.base_ref))
    for m, u in unidades:
        marca = "✓" if u["situacao"] in ("confirmado", "equivalente") else "!"
        destino = " → " + curto(u["base"]) if u["base"] else ""
        rotulo = ROTULO_METODO.get(u["metodo"], u["situacao"].upper()) if u["metodo"] else u["situacao"].upper()
        print("%s  %s merge %s%s  [%s] %d commit(s)%s" % (recuo, marca, curto(m), destino, rotulo,
                                                         len(a.introduzidos.get(m, [])),
                                                         "; " + u["motivo"] if u["motivo"] else ""))
        if u.get("revertido"):
            print("%s      aviso: %s foi revertido na base por %s; o conteúdo atual pode não conter o projeto."
                  % (recuo, curto(u["base"]), curto(u["revertido"])))
    for s in achados:
        metodo, base = a.metodo[s]
        print("%s  %s %s → %s  [%s] %s" % (recuo, "✓" if s in a.promovidos else "!", curto(s), curto(base),
                                           ROTULO_METODO.get(metodo, metodo), a.commits[s].assunto[:60]))
        if s in a.promovidos and base in a.revertidos:
            print("%s      aviso: %s foi revertido na base por %s; o conteúdo atual pode não conter o projeto."
                  % (recuo, curto(base), curto(a.revertidos[base])))
    for m, arquivos in herdados:
        print("%s  nota: o merge %s carrega alterações herdadas (não são commits do projeto) em %s; elas não são "
              "reaplicadas pelo plano." % (recuo, curto(m), resumir(arquivos, 4)))


def nome_branch_sugerido():
    return datetime.datetime.now().strftime("release/%d-%m-%y/%Hh%M")


def montar_plano(args, analise):
    projetos = [analise.resolver_projeto(n.strip()) for n in (args.projetos or "").split(",") if n.strip()]
    extras = [analise.resolver_commit(c.strip()) for c in (args.commits or "").split(",") if c.strip()]
    if not projetos and not extras:
        raise ErroUso("Informe --projetos e/ou --commits.")
    return Plano(analise, projetos, set(extras))


def imprimir_plano(plano, avisos, simulacao, erro_sim):
    a = plano.analise
    print("PLANO DE RELEASE (somente leitura: nada foi alterado)")
    print()
    cabecalho(a, avisos)
    print("Projetos selecionados: %s" % (", ".join(p.chave for p in plano.projetos) or "(nenhum)"))
    if plano.extras:
        print("Commits avulsos selecionados: %s" % ", ".join(curto(s) for s in sorted(plano.extras)))
    print("Branch sugerida: %s (criada a partir de %s @ %s)" % (nome_branch_sugerido(), a.base_ref, curto(a.base_sha)))
    print()
    print("ORDEM DE APLICAÇÃO: %d commit(s) com `git cherry-pick -x`" % len(plano.ordem))
    for i, sha in enumerate(plano.ordem, 1):
        c = a.commits[sha]
        sim = ""
        if simulacao is not None and sha in simulacao:
            estado, arquivos = simulacao[sha]
            sim = {"ok": "  [simulação: ok]", "vazio": "  [simulação: ficaria vazio]"}.get(
                estado, "  [simulação: CONFLITO em %s]" % ", ".join(arquivos[:4]))
        dono = a.dono.get(sha)
        print("  %2d. %s [%s] %s (%s, %s)%s" % (i, curto(sha), dono, c.assunto[:80], c.autor, c.data, sim))
    if plano.ignorados:
        print()
        print("NÃO SERÃO APLICADOS: %d" % len(plano.ignorados))
        for sha, motivo in plano.ignorados:
            print("  - %s [%s] %s — %s" % (curto(sha), a.dono.get(sha), a.commits[sha].assunto[:60], motivo))
    print()
    if erro_sim:
        print("SIMULAÇÃO DE CONFLITOS: indisponível (%s). Requer git 2.45+." % " ".join(erro_sim))
    elif simulacao is not None:
        conflitos = [s for s, (e, _) in simulacao.items() if e == "conflito"]
        vazios = [s for s, (e, _) in simulacao.items() if e == "vazio"]
        print("SIMULAÇÃO DE CONFLITOS: %d ok, %d conflito(s), %d vazio(s)." % (
            len(simulacao) - len(conflitos) - len(vazios), len(conflitos), len(vazios)))
        if conflitos:
            print("  Após o primeiro conflito, a simulação continua sem o commit conflitante (resultado indicativo).")
    print()
    print("ALERTAS: %d" % len(plano.alertas))
    for nivel, texto in plano.alertas:
        print("  [%s] %s" % (nivel, texto))
    if plano.dependencias:
        print()
        print("DEPENDÊNCIAS DE PROJETOS NÃO SELECIONADOS: %d" % len(plano.dependencias))
        for linha in plano.linhas_dependencias():
            print(linha)
    if plano.divergencias:
        print()
        print("DIVERGÊNCIAS COM A PRODUÇÃO (trailer sem conteúdo equivalente): %d" % len(plano.divergencias))
        for linha in plano.linhas_divergencias():
            print(linha)
    if plano.revisoes:
        print()
        print("MERGES QUE EXIGEM REVISÃO (commits fora da release até decisão): %d" % len(plano.revisoes))
        for situacao in ("divergente", "indeterminado"):
            for linha in plano.linhas_revisoes(situacao):
                print(linha)
    if plano.parciais:
        print()
        print("PROJETOS PARCIALMENTE PROMOVIDOS: %d" % len(plano.parciais))
        for linha in plano.linhas_parciais():
            print(linha)
    print()
    print(plano.linha_excluidos())
    print("Autorizações exigidas pelo preparar: %s" % (", ".join(autorizacoes_exigidas(plano)) or "nenhuma"))
    print()
    print("Assinatura do plano: %s" % plano.assinatura())


def autorizacoes_exigidas(plano):
    exigidas = []
    if plano.bloqueios:
        exigidas.append("--aceitar-bloqueios (%d BLOQUEIO(s))" % len(plano.bloqueios))
    if plano.dependencias:
        exigidas.append("--aceitar-atencao (%d dependência(s))" % len(plano.dependencias))
    div = len(plano.divergencias) + len(plano.revisoes_de("divergente"))
    if div:
        exigidas.append("--aceitar-divergencia (%d divergência(s))" % div)
    if plano.parciais:
        exigidas.append("--aceitar-parcial (%d projeto(s))" % len(plano.parciais))
    if plano.revisoes_de("indeterminado"):
        exigidas.append("--aceitar-indeterminado (%d merge(s))" % len(plano.revisoes_de("indeterminado")))
    return exigidas


def cmd_planejar(args, analise, avisos):
    plano = montar_plano(args, analise)
    simulacao, erro = simular(analise, plano.ordem)
    imprimir_plano(plano, avisos, simulacao, erro)
    return 0


# ------------------------------------------------------------------------- estado

def arquivo_estado(branch, legado=False):
    pasta = DIR_ESTADO_LEGADO if legado else DIR_ESTADO
    return os.path.join(caminho_git(pasta), branch.replace("/", "__") + ".json")


def salvar_estado(estado):
    caminho = arquivo_estado(estado["branch"])
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


def carregar_estado(branch):
    """Lê o estado da pasta atual; se não houver, o da v1.0.0 (só o <branch>.json desta Skill).

    O estado legado é lido, nunca alterado nem apagado; a próxima gravação vai para a pasta atual,
    que passa a ter precedência.
    """
    caminho = arquivo_estado(branch)
    if not os.path.exists(caminho):
        legado = arquivo_estado(branch, legado=True)
        if os.path.exists(legado):
            with open(legado, encoding="utf-8") as f:
                try:
                    estado = json.load(f)
                except ValueError:
                    estado = None
            if isinstance(estado, dict) and estado.get("branch") == branch and "pendentes" in estado:
                return estado
        raise ErroUso("A branch '%s' não foi preparada por esta Skill (estado não encontrado)." % branch)
    with open(caminho, encoding="utf-8") as f:
        try:
            estado = json.load(f)
        except ValueError:
            raise ErroUso("Estado da release ilegível em %s. Nada foi feito." % caminho)
    if not isinstance(estado, dict):
        raise ErroUso("Estado da release inválido em %s. Nada foi feito." % caminho)
    return estado


CHAVES_ESTADO = (("branch", str), ("base_ref", str), ("base_sha", str), ("origem_ref", str), ("origem_sha", str),
                 ("remoto", str), ("projetos", list), ("commits_avulsos", list), ("assinatura", str),
                 ("pendentes", list), ("aplicados", list), ("vazios", list), ("ignorados", list))


def validar_estado(estado, branch):
    """Coerência interna do estado e com a branch atual. Recusa (ErroUso) em qualquer inconsistência."""
    problemas = []
    for chave, tipo in CHAVES_ESTADO:
        if not isinstance(estado.get(chave), tipo):
            problemas.append("campo '%s' ausente ou inválido" % chave)
    if problemas:
        raise ErroUso("Estado da release inconsistente (%s). Nada foi feito." % "; ".join(problemas))
    if estado["branch"] != branch:
        problemas.append("o estado é da branch '%s', não de '%s'" % (estado["branch"], branch))
    for sha in [estado["base_sha"], estado["origem_sha"]] + estado["pendentes"] + estado["vazios"]:
        if not re.match(r"^[0-9a-f]{40}$", str(sha)) or not existe_commit(sha):
            problemas.append("commit inexistente ou inválido no estado: %s" % str(sha)[:40])
    em_conflito = estado.get("em_conflito")
    if em_conflito and (not estado["pendentes"] or estado["pendentes"][0] != em_conflito):
        problemas.append("o commit em conflito (%s) não é o próximo da fila" % curto(em_conflito))
    ponta = sha_de("refs/heads/" + branch) if existe_commit("refs/heads/" + branch) else None
    if ponta and existe_commit(estado["base_sha"]) and \
            executar_git(["merge-base", "--is-ancestor", estado["base_sha"], ponta], check=False).returncode != 0:
        problemas.append("a branch não parte da base registrada (%s)" % curto(estado["base_sha"]))
    for item in estado["aplicados"]:
        novo = item.get("novo") if isinstance(item, dict) else None
        if not novo or not existe_commit(novo) or (ponta and executar_git(
                ["merge-base", "--is-ancestor", novo, ponta], check=False).returncode != 0):
            problemas.append("commit aplicado ausente da branch: %s" % str(novo)[:12])
    processados = [i.get("original") for i in estado["aplicados"] if isinstance(i, dict)] + estado["vazios"]
    if len(set(processados) | set(estado["pendentes"])) != len(processados) + len(estado["pendentes"]):
        problemas.append("commits repetidos entre aplicados, vazios e pendentes")
    if problemas:
        raise ErroUso("Estado da release inconsistente: %s. Nada foi feito; revise com o usuário." % "; ".join(problemas))


def conferir_plano_do_estado(estado):
    """Recalcula o plano com os SHAs gravados e a versão atual das regras. Retorna lista de problemas."""
    a = Analise(estado["base_ref"], estado["base_sha"], estado["origem_ref"], estado["origem_sha"],
                estado["remoto"], estado.get("desde"))
    try:
        projetos = [a.resolver_projeto(c) for c in estado["projetos"]]
    except ErroUso as e:
        return [str(e)]
    extras = set(estado["commits_avulsos"])
    if any(e not in a.commits for e in extras):
        return ["commit avulso do estado fora de %s..%s" % (curto(estado["base_sha"]), curto(estado["origem_sha"]))]
    plano = Plano(a, projetos, extras)
    problemas = []
    if plano.assinatura() != estado["assinatura"]:
        problemas.append("a assinatura recalculada (%s) difere da confirmada (%s): o plano, com as regras atuais da "
                         "Skill, não é mais o mesmo" % (plano.assinatura(), estado["assinatura"]))
    fila = [i["original"] for i in estado["aplicados"]] + estado["vazios"] + estado["pendentes"]
    if sorted(fila) != sorted(plano.ordem) or plano.ordem[len(plano.ordem) - len(estado["pendentes"]):] != estado["pendentes"]:
        problemas.append("a fila gravada não corresponde à ordem do plano")
    aut = estado.get("autorizacoes", {})
    exigidas = (("aceitar_bloqueios", plano.bloqueios), ("aceitar_atencao", plano.dependencias),
                ("aceitar_divergencia", plano.divergencias or plano.revisoes_de("divergente")),
                ("aceitar_parcial", plano.parciais), ("aceitar_indeterminado", plano.revisoes_de("indeterminado")))
    for chave, risco in exigidas:
        if risco and not aut.get(chave):
            problemas.append("o plano exige --%s, que não foi registrada no preparar" % chave.replace("_", "-"))
    return problemas


def verificar_repositorio_limpo():
    for nome, descricao in (("CHERRY_PICK_HEAD", "cherry-pick"), ("MERGE_HEAD", "merge"),
                            ("REVERT_HEAD", "revert"), ("rebase-merge", "rebase"),
                            ("rebase-apply", "rebase/am"), ("BISECT_LOG", "bisect")):
        if os.path.exists(caminho_git(nome)):
            raise ErroUso("Há um %s em andamento. Conclua-o antes de preparar a release." % descricao)
    if g("status", "--porcelain", "--untracked-files=no").strip():
        raise ErroUso("Há alterações não commitadas em arquivos versionados. Commit ou stash manual antes.")


def verificar_branch_nova(nome):
    if executar_git(["check-ref-format", "--branch", nome], check=False).returncode != 0:
        raise ErroUso("Nome de branch inválido: '%s'." % nome)
    if existe_commit("refs/heads/" + nome):
        raise ErroUso("A branch '%s' já existe. Escolha outro nome; nada foi alterado." % nome)
    remotas = g("for-each-ref", "--format=%(refname)", "refs/remotes/*/" + nome).split()
    if remotas:
        raise ErroUso("Já existe a branch remota %s. Escolha outro nome." % remotas[0])


def aplicar_fila(estado):
    while estado["pendentes"]:
        sha = estado["pendentes"][0]
        antes = head_sha()
        p = executar_git(["cherry-pick", "-x", sha], check=False)
        if p.returncode == 0:
            depois = head_sha()
            if depois == antes:
                estado["vazios"].append(sha)
                print("  = %s ficou vazio (alteração já presente) — não gerou commit" % curto(sha))
            else:
                estado["aplicados"].append({"original": sha, "novo": depois, "modo": "automático"})
                print("  + %s → %s" % (curto(sha), curto(depois)))
            estado["pendentes"].pop(0)
            salvar_estado(estado)
            continue
        if not cherry_pick_em_andamento():
            salvar_estado(estado)
            raise ErroGit("cherry-pick de %s não iniciou (nada aplicado para este commit): %s"
                          % (curto(sha), (p.stderr or p.stdout).strip()))
        conflitos = arquivos_em_conflito()
        if not conflitos and executar_git(["diff", "--cached", "--quiet"], check=False).returncode == 0 \
                and executar_git(["diff", "--quiet"], check=False).returncode == 0:
            executar_git(["cherry-pick", "--skip"])
            estado["vazios"].append(sha)
            estado["pendentes"].pop(0)
            salvar_estado(estado)
            print("  = %s ficou vazio (alteração já presente) — não gerou commit" % curto(sha))
            continue
        estado["em_conflito"] = sha
        salvar_estado(estado)
        print()
        print("PARADO EM CONFLITO no commit %s (\"%s\")." % (curto(sha), g("log", "-1", "--format=%s", sha).strip()[:80]))
        print("Arquivos em conflito:")
        for f in conflitos:
            print("  - " + f)
        print("O cherry-pick continua em andamento. Nada foi desfeito.")
        print("Resolva os arquivos, rode `git add` neles e execute `release.py continuar`.")
        print("Restantes na fila: %d" % (len(estado["pendentes"]) - 1))
        return 3
    estado["em_conflito"] = None
    estado["concluido_em"] = datetime.datetime.now().isoformat(timespec="seconds")
    salvar_estado(estado)
    print()
    print("Fila concluída: %d aplicado(s), %d vazio(s). Execute `release.py resumo`."
          % (len(estado["aplicados"]), len(estado["vazios"])))
    return 0


def cmd_preparar(args, analise, avisos):
    if not args.branch or not args.assinatura:
        raise ErroUso("`preparar` exige --branch e --assinatura (obtida em `planejar`).")
    verificar_repositorio_limpo()
    verificar_branch_nova(args.branch)
    plano = montar_plano(args, analise)
    if plano.assinatura() != args.assinatura:
        raise ErroUso("O plano mudou desde a confirmação (assinatura %s ≠ %s). Rode `planejar` de novo e "
                      "confirme o plano atualizado. Nada foi alterado." % (plano.assinatura(), args.assinatura))
    # controles separados: --aceitar-atencao nunca libera BLOQUEIO e vice-versa
    recusas = []
    if plano.bloqueios and not args.aceitar_bloqueios:
        recusas.append("O plano tem %d BLOQUEIO(s) e --aceitar-bloqueios não foi informado:" % len(plano.bloqueios))
        recusas.extend("  - " + t for t in plano.bloqueios)
    if plano.dependencias and not args.aceitar_atencao:
        recusas.append("O plano tem %d dependência(s) ATENÇÃO de projetos não selecionados e --aceitar-atencao "
                       "não foi informado:" % len(plano.dependencias))
        recusas.extend(plano.linhas_dependencias())
    if plano.divergencias and not args.aceitar_divergencia:
        recusas.append("O plano descartaria %d commit(s) registrados como cherry-pick na base com conteúdo diferente "
                       "e --aceitar-divergencia não foi informado:" % len(plano.divergencias))
        recusas.extend(plano.linhas_divergencias())
        recusas.append("  Revise cada um com `git range-diff <original>^! <base>^!`; para reaplicar, use --commits.")
    if plano.revisoes_de("divergente") and not args.aceitar_divergencia:
        recusas.append("O plano deixaria fora %d merge(s) DIVERGENTE(S) (registro -x do merge com conteúdo diferente) "
                       "e --aceitar-divergencia não foi informado:" % len(plano.revisoes_de("divergente")))
        recusas.extend(plano.linhas_revisoes("divergente"))
    if plano.revisoes_de("indeterminado") and not args.aceitar_indeterminado:
        recusas.append("O plano deixaria fora %d merge(s) INDETERMINADO(S) e --aceitar-indeterminado não foi "
                       "informado:" % len(plano.revisoes_de("indeterminado")))
        recusas.extend(plano.linhas_revisoes("indeterminado"))
    if plano.parciais and not args.aceitar_parcial:
        recusas.append("O plano aplicaria só o restante de %d projeto(s) PARCIALMENTE PROMOVIDO(S) e --aceitar-parcial "
                       "não foi informado:" % len(plano.parciais))
        recusas.extend(plano.linhas_parciais())
    if recusas:
        recusas.append(plano.linha_excluidos())
        recusas.append("Avalie cada risco com o usuário (incluir o que falta, retirar o projeto, reaplicar o commit ou "
                       "aceitar explicitamente) e passe só a autorização que ele aceitou. Nada foi alterado.")
        raise ErroUso("\n".join(recusas))
    if not plano.ordem:
        raise ErroUso("Não há commits a aplicar. Nada foi alterado.")
    if plano.dependencias:
        print("DEPENDÊNCIAS ACEITAS com --aceitar-atencao (assinatura %s):" % plano.assinatura())
        for linha in plano.linhas_dependencias():
            print(linha)
    if plano.bloqueios:
        print("BLOQUEIOS ACEITOS com --aceitar-bloqueios:")
        for t in plano.bloqueios:
            print("  - " + t)
    if plano.divergencias:
        print("DIVERGÊNCIAS ACEITAS com --aceitar-divergencia (commits não reaplicados):")
        for linha in plano.linhas_divergencias():
            print(linha)
    if plano.revisoes_de("divergente"):
        print("MERGES DIVERGENTES ACEITOS com --aceitar-divergencia (commits não reaplicados):")
        for linha in plano.linhas_revisoes("divergente"):
            print(linha)
    if plano.revisoes_de("indeterminado"):
        print("MERGES INDETERMINADOS ACEITOS com --aceitar-indeterminado (commits não reaplicados):")
        for linha in plano.linhas_revisoes("indeterminado"):
            print(linha)
    if plano.parciais:
        print("PARCIAIS ACEITOS com --aceitar-parcial (só o restante será aplicado):")
        for linha in plano.linhas_parciais():
            print(linha)
    print(plano.linha_excluidos())
    if args.aceitar_atencao and not plano.dependencias:
        print("(--aceitar-atencao informado, mas o plano não tem dependências a aceitar.)")
    if args.aceitar_divergencia and not (plano.divergencias or plano.revisoes_de("divergente")):
        print("(--aceitar-divergencia informado, mas o plano não tem divergências a aceitar.)")
    if args.aceitar_parcial and not plano.parciais:
        print("(--aceitar-parcial informado, mas o plano não tem projetos parciais.)")
    if args.aceitar_indeterminado and not plano.revisoes_de("indeterminado"):
        print("(--aceitar-indeterminado informado, mas o plano não tem merges indeterminados.)")
    if plano.dependencias or plano.bloqueios or plano.divergencias or plano.revisoes or plano.parciais \
            or args.aceitar_atencao or args.aceitar_divergencia or args.aceitar_parcial or args.aceitar_indeterminado:
        print()
    estado = {
        "versao": 2, "branch": args.branch, "branch_anterior": branch_atual() or head_sha(),
        "base_ref": analise.base_ref, "base_sha": analise.base_sha,
        "origem_ref": analise.origem_ref, "origem_sha": analise.origem_sha,
        "remoto": analise.remoto, "desde": analise.desde,
        "projetos": [p.chave for p in plano.projetos], "commits_avulsos": sorted(plano.extras),
        "assinatura": plano.assinatura(), "alertas": plano.alertas,
        "autorizacoes": {"aceitar_bloqueios": bool(plano.bloqueios and args.aceitar_bloqueios),
                         "aceitar_atencao": bool(plano.dependencias and args.aceitar_atencao),
                         "aceitar_divergencia": bool((plano.divergencias or plano.revisoes_de("divergente"))
                                                     and args.aceitar_divergencia),
                         "aceitar_parcial": bool(plano.parciais and args.aceitar_parcial),
                         "aceitar_indeterminado": bool(plano.revisoes_de("indeterminado") and args.aceitar_indeterminado)},
        "dependencias_aceitas": plano.dependencias if args.aceitar_atencao else [],
        "divergencias_aceitas": plano.divergencias if args.aceitar_divergencia else [],
        "revisoes_aceitas": [r for r in plano.revisoes
                             if (r["situacao"] == "divergente" and args.aceitar_divergencia)
                             or (r["situacao"] == "indeterminado" and args.aceitar_indeterminado)],
        "parciais_aceitos": plano.parciais if args.aceitar_parcial else [],
        "bloqueios_aceitos": plano.bloqueios if args.aceitar_bloqueios else [],
        "projetos_excluidos": plano.excluidos,
        "ignorados": [[s, m] for s, m in plano.ignorados],
        "pendentes": list(plano.ordem), "aplicados": [], "vazios": [], "em_conflito": None,
        "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    g("switch", "--no-track", "-c", args.branch, analise.base_sha)
    salvar_estado(estado)
    print("Branch %s criada a partir de %s @ %s. Aplicando %d commit(s):"
          % (args.branch, analise.base_ref, curto(analise.base_sha), len(plano.ordem)))
    return aplicar_fila(estado)


def cmd_continuar(args):
    branch = branch_atual()
    if not branch:
        raise ErroUso("HEAD não está em uma branch. Volte para a branch de release.")
    estado = carregar_estado(branch)
    validar_estado(estado, branch)
    problemas = conferir_plano_do_estado(estado)
    if problemas:
        raise ErroUso("A release não pode ser retomada: %s. Nada foi feito. Rode `planejar` de novo e decida com o "
                      "usuário (a branch parcial não é apagada)." % "; ".join(problemas))
    sha = estado.get("em_conflito")
    if not sha:
        if not estado["pendentes"]:
            print("Nada pendente nesta release. Execute `release.py resumo`.")
            return 0
        return aplicar_fila(estado)
    if cherry_pick_em_andamento():
        conflitos = arquivos_em_conflito()
        if conflitos:
            raise ErroUso("Ainda há arquivos em conflito: %s" % ", ".join(conflitos))
        if executar_git(["diff", "--quiet"], check=False).returncode != 0:
            raise ErroUso("Há alterações não adicionadas ao índice. Rode `git add` nos arquivos resolvidos.")
        if executar_git(["diff", "--cached", "--quiet"], check=False).returncode == 0:
            executar_git(["cherry-pick", "--skip"])
            estado["vazios"].append(sha)
            print("  = %s resolvido sem diferença em relação à release — não gerou commit" % curto(sha))
        else:
            executar_git(["-c", "core.editor=true", "cherry-pick", "--continue"])
            estado["aplicados"].append({"original": sha, "novo": head_sha(), "modo": "resolução manual"})
            print("  + %s → %s (resolução manual)" % (curto(sha), curto(head_sha())))
    else:
        corpo = g("log", "-1", "--format=%B", "HEAD")
        if sha not in RE_TRAILER.findall(corpo):
            raise ErroUso("O cherry-pick de %s não está em andamento e não aparece em HEAD (pode ter sido abortado). "
                          "Nenhuma ação tomada; decida com o usuário como seguir." % curto(sha))
        estado["aplicados"].append({"original": sha, "novo": head_sha(), "modo": "resolução manual"})
        print("  + %s → %s (commit feito manualmente)" % (curto(sha), curto(head_sha())))
    estado["pendentes"].pop(0)
    estado["em_conflito"] = None
    salvar_estado(estado)
    return aplicar_fila(estado)


def cmd_resumo(args):
    branch = args.branch or branch_atual()
    if not branch:
        raise ErroUso("Informe --branch.")
    estado = carregar_estado(branch)
    validar_estado(estado, branch)
    problemas_plano = conferir_plano_do_estado(estado)
    ponta = sha_de("refs/heads/" + branch)
    a = Analise(estado["base_ref"], estado["base_sha"], estado["origem_ref"], estado["origem_sha"],
                estado["remoto"], estado.get("desde"))
    incompleta = estado["pendentes"] or estado.get("em_conflito")
    print("RESUMO DA RELEASE %s%s" % (branch, " — INCOMPLETA" if incompleta else ""))
    print()
    print("Base:   %s @ %s (atual: %s)" % (estado["base_ref"], curto(estado["base_sha"]),
                                         curto(sha_de(estado["base_ref"])) if existe_commit(estado["base_ref"]) else "?"))
    print("Origem: %s @ %s" % (estado["origem_ref"], curto(estado["origem_sha"])))
    print("Ponta da release: %s" % curto(ponta))
    print("Projetos incluídos: %s" % (", ".join(estado["projetos"]) or "(nenhum)"))
    if estado["commits_avulsos"]:
        print("Commits avulsos incluídos: %s" % ", ".join(curto(s) for s in estado["commits_avulsos"]))
    print()
    print("APLICADOS: %d" % len(estado["aplicados"]))
    for item in estado["aplicados"]:
        c = a.commits.get(item["original"])
        print("  + %s → %s %s%s" % (curto(item["original"]), curto(item["novo"]), c.assunto[:70] if c else "",
                                   "" if item["modo"] == "automático" else "  [%s]" % item["modo"]))
    if estado["vazios"]:
        print("VAZIOS (alteração já presente na base): %s" % ", ".join(curto(s) for s in estado["vazios"]))
    if estado["ignorados"]:
        print("IGNORADOS NO PLANO: %d" % len(estado["ignorados"]))
        for sha, motivo in estado["ignorados"]:
            print("  - %s — %s" % (curto(sha), motivo))
    if incompleta:
        print("PENDENTES: %d (em conflito: %s)" % (len(estado["pendentes"]), curto(estado["em_conflito"] or "-")))
    if estado.get("dependencias_aceitas"):
        print("DEPENDÊNCIAS ACEITAS (--aceitar-atencao):")
        for d in estado["dependencias_aceitas"]:
            print("  - %s depende de %s em %s (commits não incluídos: %s)" % (
                d["projeto"], d["depende_de"], resumir(d["arquivos"], 5), resumir([curto(s) for s in d["commits"]], 6)))
    if estado.get("bloqueios_aceitos"):
        print("BLOQUEIOS ACEITOS (--aceitar-bloqueios):")
        for t in estado["bloqueios_aceitos"]:
            print("  - " + t)
    if estado.get("divergencias_aceitas"):
        print("DIVERGÊNCIAS ACEITAS (--aceitar-divergencia; commits não reaplicados):")
        for d in estado["divergencias_aceitas"]:
            print("  - %s [%s] base tem %s com conteúdo diferente" % (curto(d["commit"]), d["projeto"], curto(d["base"])))
    for situacao, flag in (("divergente", "--aceitar-divergencia"), ("indeterminado", "--aceitar-indeterminado")):
        itens = [r for r in estado.get("revisoes_aceitas", []) if r["situacao"] == situacao]
        if itens:
            print("MERGES %sS ACEITOS (%s; commits não reaplicados):" % (situacao.upper(), flag))
            for r in itens:
                print("  - [%s] merge %s: %d commit(s)%s" % (r["projeto"], curto(r["merge"]), len(r["commits"]),
                                                            "; base tem %s" % curto(r["base"]) if r["base"] else ""))
    if estado.get("parciais_aceitos"):
        print("PARCIAIS ACEITOS (--aceitar-parcial; só o restante aplicado):")
        for p in estado["parciais_aceitos"]:
            print("  - %s: %d já em produção, %d aplicado(s)" % (p["projeto"], p["em_producao"], p["aplicados"]))

    # verificação: commits fora do plano
    esperados = set(i["original"] for i in estado["aplicados"])
    inesperados = []
    for bloco in g("log", "--format=" + SEP_REG + "%H" + SEP_CAMPO + "%B", "%s..%s" % (estado["base_sha"], ponta)).split(SEP_REG)[1:]:
        sha, corpo = bloco.split(SEP_CAMPO, 1)
        origens = RE_TRAILER.findall(corpo)
        if not origens or not set(origens) <= esperados:
            inesperados.append(sha)
    # verificação: arquivos comparados com a origem
    selecionados = set(estado["projetos"])
    # divergências aceitas: o commit ficou de fora de propósito, então seus arquivos podem diferir da origem
    aceitas = set(d["commit"] for d in estado.get("divergencias_aceitas", []))
    aceitas.update(c for r in estado.get("revisoes_aceitas", []) for c in r["commits"])
    nao_incluidos = [s for s, c in a.commits.items() if not c.merge and s not in a.promovidos
                     and (a.dono.get(s) not in selecionados or s in aceitas)
                     and s not in esperados and s not in estado["vazios"]]
    arquivos_nao_incluidos = a.arquivos(nao_incluidos)
    # alterações que só existem na base (ex.: hotfix direto na produção), sem equivalente na origem
    arquivos_base = set()
    log_base = g("-c", "core.quotepath=off", "log", "--left-only", "--cherry-pick", "--no-merges", "--no-renames",
                 "--name-only", "--format=" + SEP_REG + "%B" + SEP_CAMPO, "%s...%s" % (estado["base_sha"], estado["origem_sha"]))
    for bloco in log_base.split(SEP_REG)[1:]:
        corpo, nomes = bloco.split(SEP_CAMPO, 1)
        if any(o in a.commits or o in a.promovidos for o in RE_TRAILER.findall(corpo)):
            continue
        arquivos_base.update(l for l in nomes.splitlines() if l.strip())
    arquivos_release = set(l for l in g("-c", "core.quotepath=off", "diff", "--name-only", "--no-renames",
                                        estado["base_sha"], ponta).splitlines() if l)
    alvo = sorted(arquivos_release | a.arquivos(esperados & set(a.commits)))
    divergentes = []
    if alvo:
        dif = set(l for l in executar_git(["-c", "core.quotepath=off", "diff", "--name-only", "--no-renames", ponta,
                                           estado["origem_sha"], "--"] + alvo).stdout.splitlines() if l)
        for f in alvo:
            if f in dif and f not in arquivos_nao_incluidos and f not in arquivos_base:
                divergentes.append(f)
    print()
    print("VERIFICAÇÕES")
    print("  Plano confirmado × regras atuais: %s" % ("; ".join(problemas_plano) if problemas_plano else "compatível"))
    print("  Commits fora do plano na release: %s" % (", ".join(curto(s) for s in inesperados) or "nenhum"))
    print("  Arquivos alterados pela release: %d" % len(arquivos_release))
    print("  Divergências inesperadas em relação à origem: %s" % (", ".join(divergentes) or "nenhuma"))
    banco = sorted(f for f in arquivos_release if RE_BANCO.search(f))
    if banco:
        print("  Alterações de banco de dados: %s" % ", ".join(banco))
    restantes = [p.chave for p in a.projetos_pendentes() if p.chave not in selecionados]
    print("  Projetos que continuam só na origem: %d%s" % (len(restantes), (" — " + ", ".join(restantes)) if restantes else ""))
    print()
    print(g("diff", "--stat", estado["base_sha"], ponta).rstrip() or "(sem diferenças em relação à base)")
    print()
    print("Nada foi enviado ao remoto, nem mesclado na base. Passos manuais, se aprovar:")
    print("  git push -u %s %s   # e abrir MR/PR de %s para %s" % (estado["remoto"], branch, branch,
                                                                  estado["base_ref"].split("/")[-1]))
    print("Para voltar à branch anterior: git switch %s" % estado["branch_anterior"])
    return 1 if (incompleta or inesperados or divergentes or problemas_plano) else 0


# --------------------------------------------------------------------------- main

def main(argv):
    parser = argparse.ArgumentParser(description="Release seletiva por cherry-pick (pt-BR).")
    sub = parser.add_subparsers(dest="comando")
    for nome in ("listar", "planejar", "preparar"):
        sp = sub.add_parser(nome)
        sp.add_argument("--base", default="master")
        sp.add_argument("--origem", default="develop")
        sp.add_argument("--remoto", default="origin")
        sp.add_argument("--desde")
        if nome == "listar":
            sp.add_argument("--detalhes", action="store_true")
        else:
            sp.add_argument("--projetos")
            sp.add_argument("--commits")
        if nome == "preparar":
            sp.add_argument("--branch")
            sp.add_argument("--assinatura")
            sp.add_argument("--aceitar-bloqueios", action="store_true")
            sp.add_argument("--aceitar-atencao", action="store_true")
            sp.add_argument("--aceitar-divergencia", action="store_true")
            sp.add_argument("--aceitar-parcial", action="store_true")
            sp.add_argument("--aceitar-indeterminado", action="store_true")
    sub.add_parser("continuar")
    sp = sub.add_parser("resumo")
    sp.add_argument("--branch")
    args = parser.parse_args(argv)
    if not args.comando:
        parser.print_help()
        return 1
    try:
        if executar_git(["rev-parse", "--is-inside-work-tree"], check=False).returncode != 0:
            raise ErroGit("O diretório atual não é um repositório git.")
        if args.comando == "continuar":
            return cmd_continuar(args)
        if args.comando == "resumo":
            return cmd_resumo(args)
        if args.desde and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.desde):
            raise ErroUso("--desde deve estar no formato AAAA-MM-DD.")
        avisos = []
        base_ref, base_sha = resolver_ref(args.base, args.remoto, avisos)
        origem_ref, origem_sha = resolver_ref(args.origem, args.remoto, avisos)
        if base_ref.startswith(args.remoto + "/") or origem_ref.startswith(args.remoto + "/"):
            aviso_fetch(avisos)
        analise = Analise(base_ref, base_sha, origem_ref, origem_sha, args.remoto, args.desde)
        return {"listar": cmd_listar, "planejar": cmd_planejar, "preparar": cmd_preparar}[args.comando](
            args, analise, avisos)
    except ErroUso as e:
        print("ERRO: %s" % e, file=sys.stderr)
        return 1
    except ErroGit as e:
        print("ERRO DO GIT: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
