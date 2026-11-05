# Mapeamento de código para OpenAPI

Regras para transformar as rotas encontradas no código em uma especificação OpenAPI 3.x. Agnóstico de framework: os exemplos ilustram padrões comuns, não uma lista fechada.

## 1. Versão da especificação

- Especificação existente: manter a versão dela.
- Especificação nova: usar `openapi: 3.0.3`, que tem o suporte mais amplo em ferramentas (Swagger UI, Postman, geradores). Usar `3.1.0` apenas se o usuário pedir ou se o projeto já usar JSON Schema 2020-12.
- Diferença prática: em 3.0.3, campos anuláveis usam `nullable: true`; em 3.1.0, usam `type: [string, "null"]`.

## 2. Localização das rotas

Procurar, nesta ordem, até encontrar o mecanismo usado pelo projeto:

1. **Arquivos de rotas dedicados:** nomes como `routes/`, `routes.*`, `router.*`, `urls.py`, `api.php`, `web.php`.
2. **Chamadas de registro:** `get(`, `post(`, `put(`, `patch(`, `delete(`, `route(`, `add_url_rule(`, `HandleFunc(`, `Handle(`, `Map(Get|Post|...)(`, seguidas de uma string iniciada por `/`.
3. **Anotações, atributos e decorators:** `@Get(`, `@GetMapping(`, `@RequestMapping(`, `@app.get(`, `@router.post(`, `#[Route(`, `[HttpGet(`, `@api_view(`.
4. **Roteamento por arquivos:** diretórios como `pages/api/`, `app/api/**/route.*`, `server/api/`, em que o caminho do arquivo é a rota.
5. **Recursos/CRUD automáticos:** `resources(`, `apiResource(`, `ViewSet`, `router.register(`, que geram várias rotas a partir de uma declaração. Expandir para as rotas efetivamente geradas, respeitando `only`/`except` e equivalentes.

Ao montar o caminho completo, aplicar todos os prefixos: grupos de rotas, controllers com prefixo, `app.use('/prefixo', router)`, `include()`, `setGlobalPrefix`, versionamento (`/v1`) e o prefixo padrão do framework (por exemplo, `/api` em arquivos de rotas de API).

Ignorar rotas de páginas HTML, assets estáticos, health checks internos e rotas de debug, a menos que o usuário peça. Listá-las no relatório como ignoradas.

## 3. Caminhos e parâmetros de caminho

- Converter a sintaxe do framework para `{nome}`: `:id`, `<id>`, `<int:id>`, `[id]`, `{id:int}`, `{id?}` → `{id}`.
- Todo `{nome}` do caminho precisa de um parâmetro `in: path` com `required: true`. Parâmetros opcionais de caminho (`{id?}`) não existem em OpenAPI: documentar duas operações ou registrar `x-revisar`.
- Restrições de tipo na rota (`<int:id>`, `where('id', '[0-9]+')`, `ParseIntPipe`) definem o `schema` do parâmetro.
- Parâmetros comuns a todas as operações de um caminho vão no nível do path item.

## 4. Query, cabeçalhos e corpo

- **Query:** leituras explícitas da query string (`req.query.x`, `$request->query('x')`, `request.args.get`, parâmetros de função anotados como query). Paginação, ordenação e filtros recorrentes viram `components/parameters`.
- **Cabeçalhos:** documentar apenas cabeçalhos de negócio lidos pelo handler (por exemplo, `X-Idempotency-Key`). `Authorization`, `Content-Type` e `Accept` não são parâmetros: autenticação vai em `security` e tipos de mídia em `content`.
- **Corpo (`requestBody`):** extrair de, em ordem de preferência:
  1. Regras de validação (form requests, schemas Joi/Zod/Yup/Pydantic/marshmallow, Bean Validation, DTOs com class-validator).
  2. Tipos declarados (DTOs, structs, records, interfaces).
  3. Campos lidos do corpo no handler. Neste caso, marcar `x-revisar`.
- Campos obrigatórios vão em `required`. Restrições de validação mapeiam para `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `enum`, `format`.
- Uploads (`multipart/form-data`) usam `type: string, format: binary`.

## 5. Tabela de tipos

| Origem no código | OpenAPI |
|---|---|
| inteiro, `int`, `Integer`, `int32` | `type: integer` (`format: int32` quando explícito) |
| `long`, `int64`, `bigint`, IDs autoincrementais grandes | `type: integer, format: int64` |
| `float`, `double`, `decimal`, `number` | `type: number` (`format: float`/`double` quando explícito) |
| valores monetários como `decimal` serializado em string | `type: string, format: decimal` + `x-revisar` se não for certo |
| `bool`, `boolean` | `type: boolean` |
| `string`, `str`, `text` | `type: string` |
| data | `type: string, format: date` |
| data e hora, timestamp | `type: string, format: date-time` |
| UUID | `type: string, format: uuid` |
| e-mail, URL validados | `type: string, format: email` / `format: uri` |
| enum, `in:a,b,c` | `type: string, enum: [a, b, c]` |
| lista, array | `type: array, items: {...}` |
| objeto, mapa | `type: object, properties: {...}` |
| arquivo enviado | `type: string, format: binary` |

Tipos não identificados: `type: string` com `x-revisar`.

## 6. Respostas

- Código de sucesso: usar o explícito no código (`201`, `204`, `HttpCode(201)`, `status=201`). Sem indicação, usar o padrão do framework (geralmente `200`; criação em recursos REST costuma ser `201` apenas se o código definir).
- Schema: extrair de resources/serializers/transformers/DTOs de resposta, dos tipos de retorno ou do objeto montado no `return`. Respeitar envelopes (`{ data: ..., meta: ... }`) aplicados por middlewares ou classes base.
- Erros: documentar apenas os que o handler ou o tratador global efetivamente produzem, por exemplo `404` em `findOrFail`/`get_object_or_404`, `422`/`400` em falhas de validação, `401`/`403` em rotas protegidas. Reutilizar via `components/responses`.
- `204` não tem `content`.

## 7. Autenticação

- Identificar middlewares, guards, decorators ou filtros de autenticação (`auth`, `auth:sanctum`, `jwt`, `@UseGuards`, `@login_required`, `[Authorize]`, `IsAuthenticated`).
- Declarar o mecanismo em `components/securitySchemes`:
  - Bearer/JWT: `type: http, scheme: bearer, bearerFormat: JWT`.
  - Chave em cabeçalho: `type: apiKey, in: header, name: <nome do cabeçalho>`.
  - Basic: `type: http, scheme: basic`.
  - Sessão/cookie: `type: apiKey, in: cookie, name: <nome do cookie>`.
  - OAuth2: `type: oauth2` com os fluxos e escopos encontrados no código; URLs não encontradas viram `x-revisar`.
- Se quase todas as rotas forem protegidas, usar `security` global e `security: []` nas públicas. Caso contrário, declarar `security` por operação.
- Permissões e papéis (`can:`, `@Roles`, `has_permission`) vão na `description` da operação.

## 8. Estrutura do documento

```yaml
openapi: 3.0.3
info:
  title: <nome do projeto>
  version: <versão do manifesto ou 1.0.0>
  description: <uma frase sobre a API>
servers:
  - url: http://localhost:<porta>
tags:
  - name: <Módulo>
    description: <descrição curta>
paths:
  /recurso/{id}:
    parameters:
      - $ref: '#/components/parameters/Id'
    get:
      tags: [<Módulo>]
      operationId: obterRecurso
      summary: <ação em uma frase curta>
      security:
        - bearerAuth: []
      responses:
        '200':
          description: <descrição>
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Recurso'
        '404':
          $ref: '#/components/responses/NaoEncontrado'
components:
  schemas: {}
  parameters: {}
  responses: {}
  securitySchemes: {}
```

Convenções:

- **Tags:** uma por módulo, controller ou recurso.
- **operationId:** único, em camelCase, derivado do handler quando o nome dele for claro (`PedidoController@store` → `criarPedido`). Em atualização, manter os existentes.
- **Schemas:** nomes em PascalCase iguais às entidades do código (`Pedido`, `PedidoCriacao`). Separar schema de entrada e de saída quando os campos diferirem.
- **Códigos de status** sempre entre aspas (`'200'`), para não virarem números no YAML.
- Omitir seções de `components` que ficarem vazias.

## 9. Marcação `x-revisar`

Extensão própria desta Skill para lacunas. Valor: string com o motivo e onde confirmar.

```yaml
quantidade:
  type: integer
  x-revisar: "Sem validação explícita; tipo inferido do uso em PedidoService.php:88."
```

Pode ser colocada em qualquer objeto (operação, parâmetro, schema, propriedade, resposta). O validador lista todas as ocorrências para o relatório. Ferramentas OpenAPI ignoram extensões `x-`, então a marcação não quebra o uso do arquivo.
