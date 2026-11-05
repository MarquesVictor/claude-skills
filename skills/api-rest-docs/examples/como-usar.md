# Como usar a Skill api-rest-docs

## Objetivo

A `api-rest-docs` lê o código-fonte de uma API REST e gera (ou atualiza) a especificação OpenAPI 3.x em YAML, pronta para abrir no Swagger UI, Redoc, Postman ou Insomnia. Ela documenta apenas o que o código implementa e marca com `x-revisar` tudo o que precisou deduzir, para você conferir.

## Como invocar

Abra o Claude Code na raiz do projeto da API e digite:

```text
/api-rest-docs [escopo] [arquivo de destino]
```

- Sem argumentos, documenta o projeto inteiro em `docs/openapi.yaml` (ou na especificação que já existir).
- A Skill também é acionada automaticamente quando você pede para documentar a API, gerar o Swagger ou atualizar o `openapi.yaml`.

### Instalação

Criar a pasta no repositório não instala a Skill. Confira se o destino está livre e crie o link simbólico:

```bash
ls -la ~/.claude/skills/
ln -s /CAMINHO/ABSOLUTO/claude-skills/skills/api-rest-docs ~/.claude/skills/api-rest-docs
```

Abra uma sessão nova do Claude Code depois de instalar.

## Exemplos de solicitações

```text
/api-rest-docs
```

```text
/api-rest-docs só o módulo de pedidos
```

```text
/api-rest-docs rotas em src/routes/admin, gravar em docs/admin.openapi.yaml
```

```text
Atualize o openapi.yaml com as rotas que adicionei nesta branch.
```

```text
Gere o swagger dos endpoints de autenticação.
```

## Entradas e resultados esperados

- **Entradas:** o projeto com o código da API (qualquer linguagem ou framework) e, opcionalmente, o escopo e o arquivo de destino.
- **Resultados:**
  - O arquivo OpenAPI em YAML, com rotas, parâmetros, corpos, respostas, autenticação e schemas reutilizáveis. Textos descritivos em pt-BR.
  - Um relatório na conversa: quantos endpoints foram documentados, as pendências `x-revisar`, as rotas que não puderam ser documentadas e o resultado da validação.
  - Em atualizações: o que foi adicionado ou alterado e os endpoints que estão na especificação mas não no código (eles não são removidos sem a sua confirmação).

Para validar o arquivo por conta própria:

```bash
python3 ~/.claude/skills/api-rest-docs/scripts/validar-openapi.py docs/openapi.yaml
```

## Dependências e pré-requisitos

- Python 3.
- Para ler YAML no validador: PyYAML (`python3 -m pip install pyyaml`) **ou** Ruby. No macOS, o Ruby do sistema já atende. Sem nenhum dos dois, a especificação é gerada, mas a validação automática fica pendente e o relatório informa isso.

## Limitações conhecidas

- Não executa a API nem faz requisições: tudo vem da leitura do código. Rotas registradas dinamicamente (a partir de banco, configuração em tempo de execução ou laços complexos) podem ficar de fora; elas aparecem no relatório.
- Tipos e formatos de resposta montados dinamicamente são deduzidos e marcados com `x-revisar`.
- O validador faz verificação estrutural (campos obrigatórios, parâmetros de caminho, referências, códigos de status, credenciais aparentes). Ele não valida o JSON Schema completo; para isso, use uma ferramenta dedicada, como `npx @redocly/cli lint`.
- Não documenta GraphQL, gRPC, SOAP ou WebSocket, não gera SDKs nem publica a documentação.
- Não altera o código do projeto (não adiciona anotações de Swagger aos controllers).
