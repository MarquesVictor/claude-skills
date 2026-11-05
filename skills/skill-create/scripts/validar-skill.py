#!/usr/bin/env python3
"""Validação estrutural de Skills do Claude Code.

Uso:
    python3 validar-skill.py <caminho-da-skill> [--estrito] [--biblioteca]

Argumentos:
    caminho-da-skill  Diretório da Skill (que contém o SKILL.md) ou o próprio SKILL.md.
    --estrito         Trata avisos como erros.
    --biblioteca      Aplica o padrão da biblioteca pessoal: exige examples/como-usar.md
                      com as seções mínimas. Sem esta opção, só o SKILL.md é obrigatório
                      e problemas no guia, se ele existir, viram avisos.

Códigos de saída:
    0  Nenhum erro encontrado.
    1  Erros encontrados (ou avisos, no modo --estrito).
    2  Uso incorreto ou caminho inexistente.

Somente leitura: o script não altera nenhum arquivo.
Requer apenas a biblioteca padrão do Python 3.
"""

import os
import re
import sys
import unicodedata

# Propriedades de frontmatter suportadas pelo Claude Code.
# Conferidas em https://code.claude.com/docs/en/skills em 2026-11-05.
PROPRIEDADES_SUPORTADAS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "model", "effort", "context", "agent", "background",
    "hooks", "paths", "shell", "metadata", "license", "compatibility",
}
LIMITE_DESCRICAO = 1536  # description + when_to_use na listagem
LIMITE_LINHAS = 500
PADRAO_NOME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PREFIXOS_REFERENCIA = ("references/", "scripts/", "assets/", "evals/", "examples/")
GUIA_USO = "examples/como-usar.md"
# Seções mínimas do guia: (rótulo, palavras-chave procuradas nos títulos, sem acentos).
SECOES_GUIA = [
    ("Objetivo", ("objetivo", "finalidade")),
    ("Como invocar", ("invoca",)),
    ("Exemplos de solicitações", ("exemplo",)),
    ("Entradas", ("entrada",)),
    ("Resultados esperados", ("resultado", "saida")),
    ("Dependências e pré-requisitos", ("dependencia", "pre-requisito", "prerequisito")),
    ("Limitações conhecidas", ("limitac",)),
]
LIMITE_LINHAS_DUPLICADAS = 3  # linhas longas copiadas do SKILL.md antes de avisar
PADROES_PERIGOSOS = [
    (re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f|rm\s+-[a-zA-Z]*f[a-zA-Z]*r"), "rm -rf"),
    (re.compile(r"git\s+push\s+[^\n]*--force|git\s+push\s+-f\b"), "git push --force"),
    (re.compile(r"git\s+reset\s+--hard"), "git reset --hard"),
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.I), "DROP TABLE/DATABASE"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "TRUNCATE TABLE"),
    (re.compile(r"chmod\s+(-R\s+)?777"), "chmod 777"),
    (re.compile(r"curl[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"), "curl | sh"),
    (re.compile(r"--dangerously-skip-permissions"), "--dangerously-skip-permissions"),
]


class Relatorio:
    def __init__(self):
        self.erros = 0
        self.avisos = 0

    def ok(self, msg):
        print(f"[OK]    {msg}")

    def erro(self, msg):
        self.erros += 1
        print(f"[ERRO]  {msg}")

    def aviso(self, msg):
        self.avisos += 1
        print(f"[AVISO] {msg}")


def ler_frontmatter(linhas):
    """Retorna (dicionário de propriedades de primeiro nível, índice da linha de fechamento)."""
    fim = None
    for i in range(1, len(linhas)):
        if linhas[i].rstrip() == "---":
            fim = i
            break
    if fim is None:
        return None, None
    props = {}
    atual = None
    for linha in linhas[1:fim]:
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:(.*)$", linha)
        if m and not linha[0].isspace():
            atual = m.group(1)
            props[atual] = m.group(2).strip()
        elif atual is not None:
            # Continuação de valor (bloco, lista ou mapa aninhado).
            props[atual] = (props[atual] + " " + linha.strip()).strip()
    for chave, valor in props.items():
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            props[chave] = valor[1:-1]
        elif valor in (">", "|", ">-", "|-"):
            props[chave] = ""
        elif valor[:2] in ("> ", "| ") or valor[:3] in (">- ", "|- "):
            props[chave] = valor.split(" ", 1)[1]
    return props, fim


def remover_blocos_de_codigo(texto):
    """Remove blocos cercados e indentados, onde ficam exemplos que não são referências reais."""
    texto = re.sub(r"```.*?```", "", texto, flags=re.S)
    return "\n".join(l for l in texto.splitlines() if not l.startswith("    "))


def normalizar(texto):
    """Minúsculas e sem acentos, para comparar títulos de seção."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def secoes_markdown(texto):
    """Retorna [(título normalizado, tem_conteúdo)] dos títulos ## e ### fora de blocos de código."""
    linhas = re.sub(r"```.*?```", "```", texto, flags=re.S).splitlines()
    titulos = [(i, len(m.group(1)), m.group(2))
               for i, l in enumerate(linhas)
               for m in [re.match(r"^(#{2,3})\s+(.+?)\s*#*\s*$", l)] if m]
    resultado = []
    for n, (i, nivel, titulo) in enumerate(titulos):
        fim = next((j for j, nv, _ in titulos[n + 1:] if nv <= nivel), len(linhas))
        corpo = [l for l in linhas[i + 1:fim] if l.strip() and not l.lstrip().startswith("#")]
        resultado.append((normalizar(titulo), bool(corpo)))
    return resultado


def validar_guia(raiz, nome, rel, obrigatorio):
    """Verifica examples/como-usar.md. Falhas são erros com --biblioteca e avisos sem ela."""
    falha = rel.erro if obrigatorio else rel.aviso
    caminho = os.path.join(raiz, GUIA_USO)
    if not os.path.isfile(caminho):
        if obrigatorio:
            rel.erro(f"{GUIA_USO} ausente; obrigatório no padrão da biblioteca.")
        else:
            rel.ok(f"{GUIA_USO} não exigido (use --biblioteca para aplicar o padrão da biblioteca).")
        return
    with open(caminho, encoding="utf-8", errors="replace") as f:
        texto = f.read()
    if not texto.strip():
        falha(f"{GUIA_USO} está vazio.")
        return

    secoes = secoes_markdown(texto)
    ausentes, vazias = [], []
    for rotulo, chaves in SECOES_GUIA:
        achadas = [tem for titulo, tem in secoes if any(c in titulo for c in chaves)]
        if not achadas:
            ausentes.append(rotulo)
        elif not any(achadas):
            vazias.append(rotulo)
    if ausentes:
        falha(f"{GUIA_USO} sem as seções mínimas: " + ", ".join(ausentes) + ".")
    if vazias:
        falha(f"{GUIA_USO} com seções sem conteúdo: " + ", ".join(vazias) + ".")
    if not ausentes and not vazias:
        rel.ok(f"{GUIA_USO} contém as {len(SECOES_GUIA)} seções mínimas.")

    if not re.search(r"(?<![\w/-])/" + re.escape(nome) + r"(?![\w-])", texto):
        falha(f"{GUIA_USO} não mostra a invocação '/{nome}'.")
    else:
        rel.ok(f"{GUIA_USO} mostra a invocação '/{nome}'.")

    # Guia voltado ao usuário: não deve copiar as instruções do SKILL.md.
    with open(os.path.join(raiz, "SKILL.md"), encoding="utf-8", errors="replace") as f:
        linhas_skill = {l.strip() for l in f if len(l.strip()) >= 40}
    copiadas = [l for l in texto.splitlines() if l.strip() in linhas_skill]
    if len(copiadas) >= LIMITE_LINHAS_DUPLICADAS:
        rel.aviso(f"{GUIA_USO} repete {len(copiadas)} linha(s) idênticas ao SKILL.md; "
                  "o guia deve orientar o usuário, não duplicar as instruções.")


def validar(raiz, rel, biblioteca=False):
    caminho_skill = os.path.join(raiz, "SKILL.md")
    nome_dir = os.path.basename(os.path.abspath(raiz))
    print(f"Validando a Skill em: {raiz}\n")

    # 1. Existência
    if not os.path.isfile(caminho_skill):
        rel.erro("SKILL.md não encontrado.")
        return
    rel.ok("SKILL.md encontrado.")

    with open(caminho_skill, "rb") as f:
        bruto = f.read()

    # 2. Codificação e início do arquivo
    if bruto.startswith(b"\xef\xbb\xbf"):
        rel.erro("SKILL.md começa com BOM UTF-8; o frontmatter não será lido. Salve sem BOM.")
        bruto = bruto[3:]
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        rel.erro("SKILL.md não está em UTF-8.")
        return
    linhas = texto.splitlines()

    if not linhas or linhas[0].rstrip() != "---":
        primeira = next((i for i, l in enumerate(linhas) if l.strip()), None)
        if primeira is not None and linhas[primeira].rstrip() == "---":
            rel.erro(f"Frontmatter começa na linha {primeira + 1}, não na linha 1. "
                     "Remova as linhas antes do '---'; caso contrário, name e description são ignorados.")
        else:
            rel.erro("SKILL.md não começa com frontmatter ('---' na linha 1).")
        return
    rel.ok("Frontmatter inicia na linha 1.")

    # 3. Frontmatter
    props, fim = ler_frontmatter(linhas)
    if props is None:
        rel.erro("Frontmatter sem a linha de fechamento '---'.")
        return
    rel.ok(f"Frontmatter fechado na linha {fim + 1}.")

    desconhecidas = sorted(set(props) - PROPRIEDADES_SUPORTADAS)
    if desconhecidas:
        rel.aviso("Propriedades não reconhecidas (serão ignoradas pelo Claude Code): "
                  + ", ".join(desconhecidas))
    else:
        rel.ok("Todas as propriedades do frontmatter são suportadas.")

    # 4. description
    descricao = props.get("description", "")
    if not descricao:
        rel.erro("Propriedade 'description' ausente ou vazia; o acionamento automático fica prejudicado.")
    else:
        total = len(descricao) + len(props.get("when_to_use", ""))
        if total > LIMITE_DESCRICAO:
            rel.aviso(f"description + when_to_use com {total} caracteres; o excedente de "
                      f"{LIMITE_DESCRICAO} será truncado na listagem.")
        elif total < 50:
            rel.aviso(f"description muito curta ({total} caracteres); explique o que faz e quando usar.")
        else:
            rel.ok(f"description presente ({total} caracteres).")
        if "<" in descricao or ">" in descricao:
            rel.aviso("description contém '<' ou '>', que aparecem como &lt; e &gt; na listagem.")

    # 5. name
    nome = props.get("name")
    if nome is None:
        rel.ok(f"name ausente; será usado o nome do diretório ('{nome_dir}').")
    elif not PADRAO_NOME.match(nome):
        rel.erro(f"name '{nome}' fora do padrão kebab-case (minúsculas, números e hifens).")
    else:
        rel.ok(f"name '{nome}' em kebab-case.")
        if nome != nome_dir:
            rel.aviso(f"name '{nome}' difere do nome do diretório '{nome_dir}'.")
        if nome.startswith("anthropic-skills"):
            rel.erro("O prefixo 'anthropic-skills' é reservado.")

    # 6. Tamanho
    if len(linhas) > LIMITE_LINHAS:
        rel.aviso(f"SKILL.md com {len(linhas)} linhas (recomendado: menos de {LIMITE_LINHAS}). "
                  "Mova detalhes para references/.")
    else:
        rel.ok(f"SKILL.md com {len(linhas)} linhas.")

    # 7. Arquivos referenciados (em todos os .md da Skill, fora de blocos de código)
    faltando = set()
    verificados = set()
    for base, _, arquivos in os.walk(raiz):
        for arq in arquivos:
            if not arq.endswith(".md"):
                continue
            with open(os.path.join(base, arq), encoding="utf-8", errors="replace") as f:
                conteudo = remover_blocos_de_codigo(f.read())
            candidatos = re.findall(r"`([^`\s]+)`", conteudo) + re.findall(r"\]\(([^)\s]+)\)", conteudo)
            for ref in candidatos:
                ref = ref.split("#")[0]
                if not ref.startswith(PREFIXOS_REFERENCIA) or ref.endswith("/"):
                    continue
                if any(c in ref for c in "<>*{}$"):
                    continue
                verificados.add(ref)
                if not os.path.exists(os.path.join(raiz, ref)):
                    faltando.add(ref)
    for ref in sorted(faltando):
        if os.path.isdir(os.path.join(raiz, os.path.dirname(ref))):
            rel.erro(f"Arquivo referenciado não existe: {ref}")
        else:
            # A pasta do arquivo não existe na Skill: provavelmente é um caminho do projeto do usuário.
            rel.aviso(f"Caminho citado não existe na Skill (confirmar se é do projeto do usuário): {ref}")
    if not faltando:
        rel.ok(f"Arquivos referenciados existem ({len(verificados)} verificados).")

    # 8. Arquivos e diretórios vazios
    vazios = []
    for base, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if base != raiz and not dirs and not [a for a in arquivos if not a.startswith(".")]:
            vazios.append(os.path.relpath(base, raiz) + "/")
        for arq in arquivos:
            p = os.path.join(base, arq)
            if not arq.startswith(".") and os.path.getsize(p) == 0:
                vazios.append(os.path.relpath(p, raiz))
    for v in vazios:
        rel.aviso(f"Vazio: {v}")
    if not vazios:
        rel.ok("Nenhum arquivo ou diretório vazio.")

    # 9. Comandos perigosos (apenas sinalização)
    achados = []
    for base, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for arq in arquivos:
            p = os.path.join(base, arq)
            if os.path.abspath(p) == os.path.abspath(__file__):
                continue  # este script contém os padrões propositalmente
            try:
                with open(p, encoding="utf-8") as f:
                    conteudo = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            for padrao, rotulo in PADROES_PERIGOSOS:
                for m in padrao.finditer(conteudo):
                    linha = conteudo.count("\n", 0, m.start()) + 1
                    achados.append(f"{os.path.relpath(p, raiz)}:{linha} ({rotulo})")
    for a in achados:
        rel.aviso(f"Comando potencialmente perigoso, revisar se há confirmação: {a}")
    if not achados:
        rel.ok("Nenhum padrão de comando perigoso encontrado.")

    # 10. Guia de uso (padrão da biblioteca)
    validar_guia(raiz, nome if nome and PADRAO_NOME.match(nome) else nome_dir, rel, biblioteca)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opcoes = [a for a in argv[1:] if a.startswith("--")]
    if len(args) != 1 or any(o not in ("--estrito", "--biblioteca") for o in opcoes):
        print(__doc__.strip())
        return 2
    raiz = args[0]
    if os.path.basename(raiz) == "SKILL.md":
        raiz = os.path.dirname(raiz) or "."
    if not os.path.isdir(raiz):
        print(f"[ERRO]  Diretório não encontrado: {raiz}")
        return 2

    rel = Relatorio()
    validar(raiz, rel, biblioteca="--biblioteca" in opcoes)
    estrito = "--estrito" in opcoes
    print(f"\nResumo: {rel.erros} erro(s), {rel.avisos} aviso(s).")
    if rel.erros or (estrito and rel.avisos):
        print("Resultado: REPROVADO")
        return 1
    print("Resultado: APROVADO" + (" com avisos" if rel.avisos else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
