#!/usr/bin/env python3
"""Validação estrutural de especificações OpenAPI 3.x geradas pela Skill api-rest-docs.

Uso:
    python3 validar-openapi.py <arquivo.yaml|arquivo.yml|arquivo.json> [--estrito]

Argumentos:
    arquivo    Especificação OpenAPI em YAML ou JSON.
    --estrito  Trata avisos como erros.

Verificações:
    - Versão `openapi` 3.x e campos obrigatórios de `info`.
    - Caminhos iniciados por `/`, chaves válidas em cada path item.
    - Toda operação com `responses` e códigos de status válidos.
    - Parâmetros de caminho: todo `{nome}` declarado como `in: path` com
      `required: true`, e nenhum parâmetro de caminho sem `{nome}` correspondente.
    - `operationId` duplicados.
    - Referências internas (`$ref: '#/...'`) que não existem.
    - Valores que parecem credenciais reais (tokens, chaves, chaves privadas).
    - Lista as marcações `x-revisar` como pendências (não conta como erro).

Leitura de YAML: usa PyYAML se instalado; senão, Ruby (`ruby -ryaml`); JSON não
precisa de dependências.

Códigos de saída:
    0  Nenhum erro encontrado.
    1  Erros encontrados (ou avisos, no modo --estrito).
    2  Uso incorreto ou arquivo inexistente.
    3  Nenhum leitor de YAML disponível (instale PyYAML ou Ruby, ou use JSON).

Somente leitura: o script não altera nenhum arquivo.
"""

import json
import os
import re
import shutil
import subprocess
import sys

METODOS_HTTP = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]
CHAVES_PATH_ITEM = set(METODOS_HTTP) | {"summary", "description", "servers", "parameters", "$ref"}
PADRAO_STATUS = re.compile(r"^[1-5](\d\d|XX)$")
PADRAO_PARAM_CAMINHO = re.compile(r"\{([^{}]+)\}")
PADROES_SEGREDO = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "token JWT"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "chave de acesso AWS"),
    (re.compile(r"\b(sk|rk)_live_[A-Za-z0-9]{10,}"), "chave secreta Stripe"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "token GitHub"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "token Slack"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "chave de API Google"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "chave privada"),
    (re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"), "URL com usuário e senha"),
]

RUBY_YAML_PARA_JSON = (
    "require 'date'; src = File.read(ARGV[0]); "
    "begin; d = YAML.safe_load(src, permitted_classes: [Date, Time], aliases: true); "
    "rescue ArgumentError; d = YAML.safe_load(src, [Date, Time], [], true); end; "
    "puts JSON.generate(d)"
)


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


class SemLeitorYaml(Exception):
    pass


def normalizar_chaves(valor):
    """Converte chaves não textuais (ex.: 200 lido como inteiro) para string."""
    if isinstance(valor, dict):
        return {str(k): normalizar_chaves(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [normalizar_chaves(v) for v in valor]
    return valor


def carregar(caminho):
    """Retorna (dados, leitor usado). Lança ValueError em erro de sintaxe."""
    with open(caminho, encoding="utf-8-sig") as f:
        texto = f.read()
    if caminho.lower().endswith(".json"):
        return json.loads(texto), "json"
    try:
        import yaml  # type: ignore

        return normalizar_chaves(yaml.safe_load(texto)), "PyYAML"
    except ImportError:
        pass
    except Exception as exc:  # erro de sintaxe do PyYAML
        raise ValueError(str(exc))
    if shutil.which("ruby"):
        proc = subprocess.run(
            ["ruby", "-ryaml", "-rjson", "-e", RUBY_YAML_PARA_JSON, caminho],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            linhas = proc.stderr.strip().splitlines()
            msg = linhas[0] if linhas else "erro desconhecido"
            msg = re.sub(r"^.*\(<unknown>\): ", "", msg)
            raise ValueError(re.sub(r" \(Psych::\w+\)$", "", msg))
        return json.loads(proc.stdout), "Ruby"
    raise SemLeitorYaml()


def resolver_ponteiro(raiz, ref):
    """Resolve uma referência interna '#/a/b'. Retorna (True, valor) ou (False, None)."""
    atual = raiz
    for parte in ref[2:].split("/") if ref != "#" else []:
        parte = parte.replace("~1", "/").replace("~0", "~")
        if isinstance(atual, dict) and parte in atual:
            atual = atual[parte]
        elif isinstance(atual, list) and parte.isdigit() and int(parte) < len(atual):
            atual = atual[int(parte)]
        else:
            return False, None
    return True, atual


def percorrer(valor, local=""):
    """Gera (local, chave, valor) para cada par de dicionário, recursivamente."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            filho = f"{local} › {k}" if local else str(k)
            yield local, k, v
            yield from percorrer(v, filho)
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            yield from percorrer(v, f"{local} › {i}" if local else str(i))


def strings(valor, local=""):
    if isinstance(valor, str):
        yield local, valor
    elif isinstance(valor, dict):
        for k, v in valor.items():
            yield from strings(v, f"{local} › {k}" if local else str(k))
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            yield from strings(v, f"{local} › {i}" if local else str(i))


def parametros_caminho(raiz, lista, rel, local):
    """Retorna {nome: parâmetro} dos parâmetros `in: path` de uma lista."""
    resultado = {}
    if lista is None:
        return resultado
    if not isinstance(lista, list):
        rel.erro(f"{local}: `parameters` deve ser uma lista.")
        return resultado
    for p in lista:
        if isinstance(p, dict) and isinstance(p.get("$ref"), str) and p["$ref"].startswith("#/"):
            achou, p = resolver_ponteiro(raiz, p["$ref"])
            if not achou:
                continue  # já reportado na verificação de $ref
        if isinstance(p, dict) and p.get("in") == "path" and isinstance(p.get("name"), str):
            resultado[p["name"]] = p
    return resultado


def validar(dados, rel):
    if not isinstance(dados, dict):
        rel.erro("A raiz do documento deve ser um objeto (mapa).")
        return

    versao = dados.get("openapi")
    if versao is None:
        if "swagger" in dados:
            rel.erro("Documento Swagger 2.0: esta Skill gera OpenAPI 3.x.")
        else:
            rel.erro("Campo `openapi` ausente.")
    elif not isinstance(versao, str) or not re.match(r"^3\.\d+\.\d+$", versao):
        rel.erro(f"`openapi` deve ser uma string no formato 3.x.y, por exemplo 3.0.3 (encontrado: {versao!r}).")
    else:
        rel.ok(f"Versão OpenAPI {versao}.")

    info = dados.get("info")
    if not isinstance(info, dict):
        rel.erro("Objeto `info` ausente.")
    else:
        for campo in ("title", "version"):
            if not isinstance(info.get(campo), str) or not info.get(campo).strip():
                rel.erro(f"`info.{campo}` ausente ou não textual.")

    paths = dados.get("paths")
    if not isinstance(paths, dict):
        rel.erro("Objeto `paths` ausente ou inválido.")
        paths = {}

    operation_ids = {}
    total_ops = 0
    for caminho, item in paths.items():
        if caminho.startswith("x-"):
            continue
        if not caminho.startswith("/"):
            rel.erro(f"Caminho `{caminho}` deve começar com `/`.")
        if not isinstance(item, dict):
            rel.erro(f"`{caminho}`: path item deve ser um objeto.")
            continue
        for chave in item:
            if chave not in CHAVES_PATH_ITEM and not chave.startswith("x-"):
                rel.aviso(f"`{caminho}`: chave desconhecida `{chave}` (método HTTP em maiúsculas?).")
        nomes_template = PADRAO_PARAM_CAMINHO.findall(caminho)
        if len(nomes_template) != len(set(nomes_template)):
            rel.erro(f"`{caminho}`: parâmetro de caminho repetido no template.")
        comuns = parametros_caminho(dados, item.get("parameters"), rel, caminho)

        for metodo in [m for m in METODOS_HTTP if m in item]:
            op = item[metodo]
            local = f"{metodo.upper()} {caminho}"
            if not isinstance(op, dict):
                rel.erro(f"{local}: operação deve ser um objeto.")
                continue
            total_ops += 1

            respostas = op.get("responses")
            if not isinstance(respostas, dict) or not respostas:
                rel.erro(f"{local}: `responses` ausente ou vazio.")
            else:
                for codigo in respostas:
                    if codigo != "default" and not codigo.startswith("x-") and not PADRAO_STATUS.match(codigo):
                        rel.erro(f"{local}: código de resposta inválido `{codigo}`.")

            declarados = dict(comuns)
            declarados.update(parametros_caminho(dados, op.get("parameters"), rel, local))
            for nome in nomes_template:
                p = declarados.get(nome)
                if p is None:
                    rel.erro(f"{local}: `{{{nome}}}` sem parâmetro `in: path` declarado.")
                elif p.get("required") is not True:
                    rel.erro(f"{local}: parâmetro de caminho `{nome}` precisa de `required: true`.")
            for nome in declarados:
                if nome not in nomes_template:
                    rel.erro(f"{local}: parâmetro `in: path` `{nome}` não existe no caminho.")

            op_id = op.get("operationId")
            if op_id is not None:
                if op_id in operation_ids:
                    rel.erro(f"{local}: `operationId` `{op_id}` duplicado (também em {operation_ids[op_id]}).")
                else:
                    operation_ids[op_id] = local
            if not op.get("summary") and not op.get("description"):
                rel.aviso(f"{local}: sem `summary` nem `description`.")
            if not op.get("tags"):
                rel.aviso(f"{local}: sem `tags`.")

    if total_ops:
        rel.ok(f"{total_ops} operação(ões) em {len([p for p in paths if not p.startswith('x-')])} caminho(s).")
    else:
        rel.aviso("Nenhuma operação encontrada em `paths`.")

    refs_quebradas = 0
    refs_externas = set()
    for local, chave, valor in percorrer(dados):
        if chave != "$ref" or not isinstance(valor, str):
            continue
        if valor.startswith("#"):
            achou, _ = resolver_ponteiro(dados, valor)
            if not achou:
                refs_quebradas += 1
                rel.erro(f"{local or 'raiz'}: `$ref` não encontrado: {valor}")
        else:
            refs_externas.add(valor)
    if refs_externas:
        rel.aviso(f"{len(refs_externas)} referência(s) externa(s) não verificada(s): {', '.join(sorted(refs_externas))}")
    if not refs_quebradas:
        rel.ok("Referências internas resolvidas.")

    segredos = 0
    for local, texto in strings(dados):
        for padrao, rotulo in PADROES_SEGREDO:
            if padrao.search(texto):
                segredos += 1
                rel.erro(f"{local}: valor parece {rotulo}. Substituir por dado fictício.")
                break
    if not segredos:
        rel.ok("Nenhum valor com aparência de credencial.")

    pendencias = [(local, v) for local, k, v in percorrer(dados) if k == "x-revisar"]
    if pendencias:
        print(f"\nPendências x-revisar ({len(pendencias)}):")
        for local, motivo in pendencias:
            print(f"[PENDENTE] {local or 'raiz'}: {motivo}")


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opcoes = [a for a in argv[1:] if a.startswith("--")]
    if len(args) != 1 or any(o != "--estrito" for o in opcoes):
        print(__doc__.strip())
        return 2
    caminho = args[0]
    if not os.path.isfile(caminho):
        print(f"[ERRO]  Arquivo não encontrado: {caminho}")
        return 2

    rel = Relatorio()
    try:
        dados, leitor = carregar(caminho)
    except SemLeitorYaml:
        print("[ERRO]  Nenhum leitor de YAML disponível. Instale PyYAML "
              "(python3 -m pip install pyyaml) ou Ruby, ou valide uma versão JSON do arquivo.")
        return 3
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[ERRO]  Sintaxe inválida: {exc}")
        print("\nResultado: REPROVADO")
        return 1
    rel.ok(f"Arquivo lido ({leitor}).")

    validar(dados, rel)
    print(f"\nResumo: {rel.erros} erro(s), {rel.avisos} aviso(s).")
    if rel.erros or ("--estrito" in opcoes and rel.avisos):
        print("Resultado: REPROVADO")
        return 1
    print("Resultado: APROVADO" + (" com avisos" if rel.avisos else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
