# Melhorias prioritárias da API

Plano de execução acordado em 12 de Novembro de 2026, antes da implementação
de doenças avançadas. Não são desenvolvidas etapas em paralelo. A etapa 1 foi
integrada em `dev` e validada pelo utilizador. A partir da etapa 2, cada branch
de correcção parte de `izi` e é integrada apenas em `izi`, após revisão e testes.
O utilizador faz pessoalmente a integração e a validação em `dev` antes da etapa
seguinte. A integração local não implica publicação no repositório remoto.

| Etapa | Branch | Âmbito | Estado |
| --- | --- | --- | --- |
| 1 | `fix/01-database-config` | Configuração SQL e recuperação da suite de testes | Validada pelo utilizador |
| 2 | `fix/02-user-create-permissions` | Autorização para criar utilizadores e atribuir papéis | Concluída localmente; aguarda validação do utilizador |
| 2B | `feat/02-dashboard-roles` | Papéis de leitura por subdivisão e gestão das atribuições | Concluída localmente; aguarda validação do utilizador |
| 3 | `fix/03-login-credentials` | Login local e credenciais de contas Clerk | Por iniciar |
| 4 | `fix/04-reporting-errors` | Respostas HTTP de erro dos relatórios e interacção com cache | Por iniciar |
| 5 | `fix/05-patient-log-privacy` | Protecção de dados de pacientes nos logs de erro | Por iniciar |

## Critérios por etapa

1. Identificar e preservar alterações locais da equipa em `izi`; criar a branch
   de correcção numa worktree isolada, a partir do último commit de `izi`.
2. Implementar apenas a correcção da etapa, com testes de regressão e documentação.
3. Executar os testes afectados e depois a suite completa, sem ligações externas.
4. Rever o diff, verificar que não contém segredos e criar um commit identificável.
5. Integrar apenas em `izi`, com os testes verdes, preservando a branch da
   melhoria e as alterações locais identificadas. Verificar a integração.
6. Aguardar a integração pessoal e validação do utilizador em `dev` antes de
   iniciar a etapa seguinte. Publicação remota e validação com SQL Server têm
   de ser identificadas separadamente nos resultados.

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

Os problemas de autenticação, respostas de erro e logs são tratados nas etapas
correspondentes. Esta etapa não implementa CD4, CrAg ou TB-LAM.

## Etapa 2 — Autorização para criar utilizadores

Branch: `fix/02-user-create-permissions`, criada a partir de `izi` no commit
`2887e1d`. Destino de integração: `izi`. A branch `dev` é gerida pelo utilizador.

### Situação inicial

O endpoint público exigia um JWT, mas o serviço de criação ignorava a identidade
do operador e gravava o papel recebido. Um utilizador comum conseguia criar uma
conta Admin. O mesmo serviço era usado pelo webhook, pelo que acrescentar uma
verificação Admin indiscriminadamente impediria o provisionamento Clerk.

### Alteração e compatibilidade

- A criação pública exige um operador persistido com papel exactamente `Admin`.
  Claims do JWT não substituem a consulta ao cadastro. Identidades ausentes,
  desconhecidas ou com outro papel são rejeitadas sem criar contas.
- Novas contas aceitam os papéis Admin e user, normalizados sem distinguir
  maiúsculas/minúsculas; papéis desconhecidos devolvem 400. Contas existentes
  não são alteradas nem migradas.
- O endpoint devolve os códigos HTTP reais 400/403/500 nas falhas de criação e
  conserva HTTP 200 e o payload de sucesso. O texto de excepções não é exposto.
- O provisionamento Clerk tem um serviço interno separado, chamado depois da
  verificação Svix, e força sempre o papel `user`. Não existe um parâmetro do
  endpoint público que dispense a autorização. Erros de provisionamento não
  são anunciados nem registados como criações bem-sucedidas.
- O fluxo de login, as credenciais Clerk e os restantes endpoints CRUD ficam
  fora desta etapa. A verificação histórica de duplicados também é preservada;
  esta correcção trata de autorização e atribuição de papéis na criação.

### Validação

Validação concluída na branch isolada:

| Verificação | Resultado |
| --- | --- |
| Primeira execução dos testes novos, antes da correcção | 32 falhas, 21 sucessos |
| Criação, webhook, autenticação e geração de Swagger | 101 sucessos |
| Suite completa | 1 280 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente do código e documentação | Sem bloqueios identificados |
| Verificação do diff | `git diff --check` sem erros |

Os 43 novos casos de regressão demonstram a autorização com cadastro real em
SQLite, o bloqueio de tentativas de bypass e a preservação do provisionamento.
Comandos de reprodução:

```powershell
python -m pytest tests/test_user_creation.py tests/test_clerk_webhook.py tests/test_auth_enforcement.py tests/test_swagger_docstrings.py -q
python -m pytest -q
git diff --check
```

A worktree inicial de `izi` contém alterações de configuração SQL, diagnóstico,
testes e uma linha do README. Estas alterações pertencem à equipa e ficam fora
do commit da etapa 2. A integração deve preservá-las e os testes finais devem
avaliar a cópia integrada. Os testes de autorização usam SQLite em memória e
pedidos assinados de teste, sem SQL Server nem chamadas reais ao Clerk.

## Extensão 2B — Papéis por dashboard

Solicitada pelo utilizador após a etapa 2, antes de avançar para a correcção de
login. Branch `feat/02-dashboard-roles`, a partir de `izi` no commit `481128c`.
O destino continua `izi`; a integração em `dev` pertence ao utilizador.

Foi introduzida a [matriz de acesso](access-control.md) para `vl`, `dpi`,
`tb_gx`, `tb_cl`, `ad`, `global` e `Admin`, conservando `user` como papel ainda
não atribuído. O campo único já existente é mantido, sem migração ou alteração
de contas reais. A autorização usa o papel local e a identidade `sub` verificada
antes de servir relatórios, incluindo cache. Os dicionários passam a exigir um
papel atribuído. As restrições Admin de pacientes e drill-downs são preservadas.

A criação e actualização administrativas usam a mesma lista de papéis. A
atribuição de um papel pode conservar a password. O webhook sincroniza perfis
sem substituir permissões e passwords locais; novos utilizadores continuam sem
subdivisão até uma atribuição Admin. Os restantes problemas de login permanecem
na etapa 3.

Validação concluída na branch isolada:

| Verificação | Resultado |
| --- | --- |
| Matriz HTTP antes do controlo por papel | 35 falhas, 33 sucessos |
| Matriz HTTP final, seis dicionários, sugestões e métodos de leitura | 133 sucessos |
| Suite completa, incluindo política pura, administração e Clerk | 1 754 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente | Sem bloqueadores identificados |
| Verificação do diff | `git diff --check` sem erros |

Comandos de reprodução:

```powershell
python -m pytest tests/test_roles.py tests/test_dashboard_roles.py tests/test_dashboard_role_admin.py -q
python -m pytest -q
git diff --check
```

Antes da correcção HTTP, os novos testes reproduziram **35 falhas e 33 sucessos**,
incluindo leitura transversal indevida e dicionários públicos. A suite final
também cobre criação/atribuição, revogação com token e cache existentes, falhas
de consulta, sugestões por família e sincronização Clerk. A worktree inicial
de `izi` tem as mesmas quatro alterações locais da equipa descritas na etapa 2;
continuam fora do commit desta extensão e devem ser preservadas na integração.
