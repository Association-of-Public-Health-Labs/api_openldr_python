# Melhorias prioritárias da API

Plano de execução acordado em 12 de Novembro de 2026, antes da implementação
de doenças avançadas. Cada etapa parte de `dev`, fica numa branch própria e
só é integrada após revisão e testes. Não são desenvolvidas etapas em paralelo.

| Etapa | Branch | Âmbito | Estado |
| --- | --- | --- | --- |
| 1 | `fix/01-database-config` | Configuração SQL e recuperação da suite de testes | Concluída localmente; aguarda validação da equipa |
| 2 | `fix/02-user-create-permissions` | Autorização para criar utilizadores e atribuir papéis | Por iniciar |
| 3 | `fix/03-login-credentials` | Login local e credenciais de contas Clerk | Por iniciar |
| 4 | `fix/04-reporting-errors` | Respostas HTTP de erro dos relatórios e interacção com cache | Por iniciar |
| 5 | `fix/05-patient-log-privacy` | Protecção de dados de pacientes nos logs de erro | Por iniciar |

## Critérios por etapa

1. Confirmar que `dev` e a worktree de trabalho não contêm alterações alheias.
2. Implementar apenas a correcção da etapa, com testes de regressão e documentação.
3. Executar os testes afectados e depois a suite completa, sem ligações externas.
4. Rever o diff, verificar que não contém segredos e criar um commit identificável.
5. Integrar em `dev` apenas com os testes verdes e preservar a branch da melhoria.
6. Validar em `dev` antes de iniciar a etapa seguinte. Publicação remota e
   validação com SQL Server têm de ser identificadas separadamente nos resultados.

## Etapa 1 — Configuração SQL

### Situação inicial

A baseline de `dev` é o commit `1ff1e7d`. Os testes dirigidos de configuração e
registo de rotas apresentavam **22 falhas e 6 sucessos**. A avaliação anterior da
suite completa encontrou **1 203 sucessos, 22 falhas e 1 teste ignorado**.

As falhas envolviam precedência de configuração, interpolação de passwords no
INI, construção de strings ODBC, pooling e ausência do getter de binds esperado
pelos testes. Não foi consultada nenhuma base SQL Server.

### Alteração implementada e compatibilidade

- Variáveis de ambiente prevalecem sobre o INI tanto no Windows como no Linux.
  Um valor vazio explícito não recupera silenciosamente um valor do INI.
- O INI mantém passwords literais, incluindo `%`; valores ODBC especiais são
  protegidos sem alterar o conteúdo das credenciais.
- `get_sqlalchemy_binds(domain, bind_keys=None)` valida apenas os binds pedidos.
  A aplicação usa `cdr`; os nomes históricos de configuração são preservados.
- ReportData mantém servidor e credenciais próprios. Overrides vazios usam
  os valores principais do ambiente seleccionado, como anteriormente.
- O pooling ODBC é controlado por `pyodbc.pooling`; o pooling SQLAlchemy continua
  independente. O timeout de ligação existente é preservado.
- O diagnóstico rejeita configuração incompleta antes de criar engines e não
  imprime mensagens de excepção que possam conter credenciais.

### Validação

Validação local concluída na branch isolada:

| Verificação | Resultado |
| --- | --- |
| Configuração e registo de rotas, antes da correcção | 22 falhas, 6 sucessos |
| Configuração e registo de rotas, com 12 novos casos de regressão | 40 sucessos |
| Suite completa após a correcção | 1 237 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente do diff | Sem bloqueios identificados |
| Verificação de espaços e conflitos no diff | `git diff --check` sem erros |

Comandos de reprodução:

```powershell
python -m pytest tests/test_database_config.py tests/tb/test_tb_cultura_api_module.py -q
python -m pytest -q
git diff --check
```

Os testes usam configuração controlada, mocks e SQLite; não comprovam a
conectividade com SQL Server. Na homologação, configurar o serviço, reiniciá-lo
e executar `python scripts/check_mssql_connection.py --bind vl` num ambiente
autorizado, confirmando servidor, base e contagens esperados. Esse diagnóstico
faz consultas de leitura e não foi executado nesta etapa local.

### Próximas etapas

Os problemas de autenticação, respostas de erro e logs continuam pendentes até
às etapas correspondentes. Esta etapa não implementa CD4, CrAg ou TB-LAM.
