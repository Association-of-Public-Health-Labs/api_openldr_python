# Protecção dos dados de pacientes nos logs

A etapa 5 protege os diagnósticos da pipeline comum e das pesquisas de pacientes
VL, DPI/EID e TB GeneXpert. Mantém o [contrato HTTP](reporting-errors-and-cache.md),
a [matriz de acesso](access-control.md), as consultas, filtros e paginação.
Uma resposta autorizada de Admin continua a conter os campos clínicos previstos;
esses campos não são copiados para logs ou stdout.

## Diagnósticos permitidos

| Situação | Informação registada |
| --- | --- |
| Serviço devolve erro interno | Evento fixo, padrão da rota e código HTTP validado |
| Excepção inesperada na pipeline | Evento fixo, padrão da rota e classe da excepção |
| Erro de base de dados/serialização na pesquisa VL, EID ou TB GX | Módulo da pesquisa e classe da excepção |
| Token rejeitado ou falha de consulta do papel | Evento fixo, padrão da rota e classe da excepção |
| Falha de acesso ao cache | Evento fixo, padrão da rota e classe da excepção |

Os diagnósticos não incluem o texto ou objecto da excepção, traceback, SQL,
parâmetros, filtros, nomes, telefones, identificadores clínicos, linhas de
pacientes ou tokens. A protecção abrange a mensagem formatada e os valores
retidos pelo `LogRecord`, sem `exc_info` ou `stack_info` nos registos alterados.
Não basta esconder estes campos no formatter: eles não são entregues ao logger.

Usa-se o padrão registado da rota, como `/hiv/vl/patients/<patient_id>/`, em vez
de um valor dinâmico do URL. Este exemplo descreve a regra de logging; não cria
uma nova rota. As pesquisas actuais continuam nos URLs existentes.

Os serviços de pacientes devolvem apenas o erro 500 genérico quando falham, sem
incluir o detalhe interno num dicionário que possa ser registado mais tarde.
EID já seguia este padrão e foi preservado. A pipeline deixa também de registar
o campo interno `error` de outros serviços e de usar `logger.exception`.

Foram retirados os prints activos de SQL, consultas e filtros dos serviços TB
GX e dos dicionários, incluindo os dois drill-downs Admin que devolvem pacientes.
Construção de consultas e serialização dos resultados permanecem iguais. As
pesquisas de pacientes continuam reservadas a Admin e sem cache.

## Investigar um erro

Usar a hora do incidente, a rota, o código HTTP e a classe da excepção para
identificar o ponto de falha. Por exemplo:

```text
VL patient search failed: StatementError
Service error on /hiv/vl/patients/by_name/ (HTTP 500)
```

Reproduzir o caso com dados sintéticos num ambiente isolado. Não voltar a
acrescentar dumps de `req_args`, consultas com `literal_binds`, linhas ou
`str(exc)` aos diagnósticos para obter mais contexto. As mensagens de validação
400 existentes são conservadas na resposta ao cliente, sem serem registadas
pela pipeline como texto de excepção.

Em tráfego clínico, manter debug e SQL echo desactivados e evitar logging de
SQLAlchemy em INFO/DEBUG. Servidores HTTP, proxies, ODBC e SQL Server têm
configuração própria; devem omitir query strings e headers de autenticação dos
seus logs. Estes serviços externos não são reconfigurados por esta alteração.
O código também não elimina logs históricos nem altera a auditoria de contas
em `UserLogs`.

## Verificação

Os testes usam apenas dados sintéticos, SQLite e substituição da execução SQL.
As expressões SQLAlchemy e os serializadores são exercitados sem consultar uma
base clínica real. A cobertura inclui:

- As 11 rotas de pacientes: quatro VL, três EID e quatro TB GX.
- Erros devolvidos, excepções inesperadas e `StatementError` com SQL/parâmetros.
- Excepções cuja conversão para texto falha, para detectar formatação indevida.
- Ausência de dados sensíveis em stdout, stderr, argumentos dos logs e traceback.
- Sucesso paginado, campos clínicos Admin, 401/403 antes da consulta e ausência
  de cache nas pesquisas de pacientes.
- Os dois drill-downs TB Admin e os filtros dos dicionários, com consultas e
  serialização reais e execução SQL substituída.
- Rejeição de token e logging do padrão de rota sem identificadores dinâmicos.

```powershell
python -m pytest tests/test_patient_log_privacy.py tests/test_patient_drilldown_log_privacy.py -q
python -m pytest -q
git diff --check
```

Os resultados e o fluxo de integração constam do
[registo da etapa 5](priority-improvements.md#etapa-5--privacidade-dos-logs-de-pacientes).
Não constituem uma auditoria de logs externos ou históricos, nem validam
indicadores ou conectividade SQL Server reais.
