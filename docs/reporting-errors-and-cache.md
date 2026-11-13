# Erros HTTP e cache dos relatórios

Contrato da pipeline comum dos relatórios VL, DPI/EID, TB GeneXpert, TB cultura
e dos seis GET de dicionários. A [matriz de acesso](access-control.md) continua
a determinar as permissões. Login e webhooks mantêm os seus contratos próprios.

## Respostas HTTP

| Resultado | HTTP | Corpo |
| --- | --- | --- |
| Lista ou objecto de sucesso, incluindo resultados vazios | 200 | Formato actual do serviço |
| `InvalidParameter` | 400 | `status: error`, `code: 400`, mensagem de validação |
| Erro de parsing Flask-RESTful | 400 | Formato actual com `message` e o campo inválido |
| Token ausente ou inválido | 401 | Mensagem fixa de autenticação |
| Papel sem acesso à rota | 403 | Mensagem fixa de acesso negado |
| Erro 4xx declarado pelo serviço | Código declarado | Campos públicos do erro, sem o detalhe interno `error` |
| Erro 5xx declarado pelo serviço ou `HTTPException` | Código declarado, por exemplo 500 ou 503 | Apenas o envelope genérico abaixo |
| Excepção inesperada ou erro do serviço com código inválido | 500 | Apenas o envelope genérico abaixo |

```json
{
  "status": "error",
  "code": 500,
  "message": "An error occurred"
}
```

Para um erro 503, o HTTP e o campo `code` são 503. Campos adicionais como
`error`, `details`, `trace`, SQL, dados parciais ou mensagens do driver não são
incluídos nas respostas 5xx. Uma lista vazia continua a ser um sucesso; não é
transformada num 404. Os filtros e as consultas dos indicadores não são alterados.

Os seis GET de dicionários usam a mesma pipeline: as listas de sucesso e os
parâmetros repetidos `province`/`district` são preservados. Uma excepção do serviço
passa a dar HTTP 500 genérico, em vez de HTTP 200 com o texto da excepção.

## Consulta e gravação do cache

1. Verificar token, identidade e papel persistido antes de consultar o cache.
2. Determinar se o pedido pertence ao conjunto de agregados já elegíveis.
3. Servir um HIT apenas se o ficheiro tiver envelope válido, chave igual à do
   pedido, timestamp com timezone não futuro e dentro do prazo, e dados de
   sucesso em lista/objecto. Um corpo com `status: error` nunca é um HIT.
4. Se a entrada estiver ausente, expirada, corrompida ou inválida, executar o
   relatório. Uma falha de acesso ao cache também permite esta execução normal.
5. Gravar apenas o sucesso. Um erro conserva o HTTP adequado e não substitui uma
   entrada anterior. Falhas de escrita não impedem a resposta do relatório.

O cache mantém os prefixos VL, EID e TB GX, as janelas temporais e exclusões de
filtros já existentes. Dicionários, TB cultura, pacientes e pedidos por unidade
sanitária continuam sem cache. O prazo padrão continua a ser 24 horas, controlado
por `REPORT_CACHE_MAX_AGE_HOURS`; `REPORT_CACHE_ENABLED` e `REPORT_CACHE_DIR`
mantêm o significado anterior. Não é necessária uma migração ou limpeza geral.

As escritas continuam atómicas. Se a serialização, abertura ou substituição do
ficheiro falhar, a entrada anterior fica intacta e o temporário é removido,
incluindo o descritor aberto no Windows. O warm-up ignora envelopes e chaves
malformados, mas conserva chaves antigas válidas para recomputação.

| Headers | Significado |
| --- | --- |
| `X-Report-Cache: HIT` e `X-Report-Computed-At` | Sucesso obtido de entrada validada |
| `X-Report-Cache: MISS` e `X-Report-Computed-At` | Sucesso calculado e gravado |
| Headers ausentes | Pedido sem cache, falha do cache ou resposta de erro |

Não há fallback para resultados expirados quando o serviço falha: o cliente
recebe o erro actual. Uma entrada inválida é ignorada e só é substituída quando
uma execução válida consegue gravar um novo resultado.

## Verificação e limites

```powershell
python -m pytest tests/test_reporting_error_contract.py tests/test_reporting_errors.py tests/test_report_cache.py tests/test_report_cache_failures.py tests/test_dictionary_errors.py tests/test_dashboard_roles.py tests/test_swagger_docstrings.py -q
python -m pytest -q
git diff --check
```

As regressões usam contas SQLite, tokens e dados sintéticos, serviços simulados
e ficheiros temporários. Cobrem os códigos HTTP nas quatro famílias, os seis
dicionários, autorização antes do cache, ficheiros inválidos, falhas de escrita
e o warm-up. Não validam os indicadores SQL nem a conectividade de produção.
O [registo da etapa 4](priority-improvements.md#etapa-4--erros-http-e-cache)
identifica os resultados e a integração. A protecção dos dados de pacientes
nos logs continua reservada à etapa 5.
