# Melhorias prioritárias da API

Plano de execução acordado em 12 de Novembro de 2026, antes da implementação
de doenças avançadas. Não são desenvolvidas etapas em paralelo. A etapa 1 foi
integrada em `dev` e validada pelo utilizador. A partir da etapa 2, cada branch
de correcção parte de `izi` e é integrada apenas em `izi`, após revisão e testes.
O utilizador faz pessoalmente a integração e a validação em `dev` antes da etapa
seguinte. A integração local não implica publicação no repositório remoto.
A revisão da etapa 3 foi feita directamente em `izi`, preservando as alterações
de login do utilizador e deixando-lhe o commit manual. A etapa 4 retoma o fluxo
de branch isolada e integração em `izi` depois dos testes.

| Etapa | Branch | Âmbito | Estado |
| --- | --- | --- | --- |
| 1 | `fix/01-database-config` | Configuração SQL e recuperação da suite de testes | Validada pelo utilizador |
| 2 | `fix/02-user-create-permissions` | Autorização para criar utilizadores e atribuir papéis | Concluída localmente; aguarda validação do utilizador |
| 2B | `feat/02-dashboard-roles` | Papéis de leitura por subdivisão e gestão das atribuições | Concluída localmente; aguarda validação do utilizador |
| 3 | `izi`, commit manual `9c5fa0b` | Login local e credenciais de contas Clerk | Guardada pelo utilizador; etapa seguinte autorizada |
| 4 | `fix/04-reporting-errors` | Respostas HTTP de erro dos relatórios e interacção com cache | Integrada em `izi` (`6559ec5`); etapa seguinte autorizada |
| 5 | `fix/05-patient-log-privacy` | Protecção de dados de pacientes nos logs de erro | Testes locais aprovados; destino de integração `izi` |

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

## Etapa 3 — Login por password e compatibilidade Clerk

Revisão de 12 de Novembro de 2026, directamente em `izi`, sobre o commit
`8f4b047`. O utilizador já tinha alterado o login e o esquema Swagger. Essas
alterações e a formatação da equipa foram preservadas e completadas; não foi
criada outra branch, commit, merge ou publicação nesta revisão. `dev` não foi
alterada pelo agente.

### Problemas encontrados e correcções

- O login ainda obrigava ao nome de utilizador e a pesquisa exigia também o
  email, impedindo os casos com apenas um identificador. Agora aceita `username`
  **ou** `email` com password; quando ambos são enviados, têm de identificar a
  mesma conta única. Duplicados devolvem 401, sem seleccionar uma linha arbitrária.
- A password é verificada pelo hash bcrypt, sem usar `user_id` na pesquisa.
  Credenciais incorrectas passam a devolver um objecto e HTTP 401 real, em vez
  de uma tupla serializada com HTTP 200. Entradas em falta, de tipo inválido ou
  acima dos 72 bytes UTF-8 suportados por bcrypt devolvem 400. Espaços exteriores
  dos identificadores são ignorados; os da password continuam significativos.
- Falhas de consulta, criação de token ou commit devolvem 500 genérico, sem SQL,
  credenciais ou detalhes internos na resposta. Foi retirado o debug com dados
  do utilizador. Timestamp e auditoria de sucesso são gravados juntos, depois
  da criação do token, e são revertidos em caso de falha.
- Novas contas Clerk recebem um segredo local aleatório, em vez do identificador
  público como password. O login local também rejeita a password igual a
  `user_id`, incluindo contas legadas, sem reescrever hashes existentes. Para
  activar login local nessas contas, um Admin deve atribuir uma password própria.
- JWT Clerk RS256 e webhooks Svix mantêm a verificação independente. Eventos
  assinados de sessão/perfil preservam passwords e papéis locais; metadados
  Clerk não atribuem novos privilégios. O login por password não consulta Clerk.
- README, esquema Swagger e [matriz de acesso](access-control.md) foram
  actualizados para reflectir o contrato e os limites da validação.

Os defeitos históricos de unicidade na criação/actualização não foram alterados
nesta revisão. A rejeição de identificadores ambíguos protege o login sem fundir,
eliminar ou modificar contas da equipa. Passwords legadas acima de 72 bytes
precisam de actualização administrativa para usar este contrato.

### Validação automatizada

| Verificação | Resultado |
| --- | --- |
| Novos testes de login antes das correcções | 38 falhas e 12 sucessos, antes dos casos adicionais |
| Login, bcrypt, erros HTTP, transacção e coexistência Clerk | 58 sucessos |
| Papel VL nas rotas registadas, com JWT de password e Clerk | 308 sucessos |
| Testes dirigidos, incluindo webhook, autenticação e Swagger | 424 sucessos |
| Suite completa em `izi` | 2 128 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente do login e integração Clerk | Sem bloqueadores funcionais novos identificados |
| Verificação do diff | `git diff --check` sem erros |

Os testes percorrem as 147 rotas GET de relatórios e dicionários actualmente
registadas, para os dois emissores de token. Por emissor, o papel `vl` obtém:

| Grupo | Rotas | HTTP esperado |
| --- | ---: | --- |
| Relatórios agregados VL, com filtros permitidos | 43 | 200 |
| Dicionários partilhados | 6 | 200 |
| Pesquisas de pacientes VL, reservadas a Admin | 4 | 403 |
| DPI/EID | 41 | 403 |
| TB GeneXpert | 46 | 403 |
| TB cultura | 7 | 403 |

Também são testadas as seis rotas de sugestões para ambos os tokens e a
proibição de listar utilizadores com papel VL. A política continua a reservar
agregados por unidade sanitária e drill-downs individuais a Admin.

Estas verificações usam HTTP, validação de JWT, parsing, papel persistido e
pipeline de autorização reais, com SQLite e contas sintéticas. Consultas dos
relatórios, transporte JWKS, perfis Clerk e envio de email são substituídos nos
testes. Por isso, os resultados comprovam o controlo de acesso e os contratos,
sem comprovar indicadores SQL, dados clínicos ou disponibilidade do Clerk real.

```powershell
python -m pytest tests/test_login.py tests/test_vl_role_route_access.py tests/test_clerk_webhook.py tests/test_auth_enforcement.py tests/test_swagger_docstrings.py -q
python -m pytest -q
git diff --check
```

### Conta fornecida e validação pessoal pendente

Foi consultado apenas o cadastro autorizado no SQL Server, em leitura: a conta
existe, tem papel `vl`, nome de utilizador único e hash bcrypt. O identificador
público não corresponde à password guardada. O email está associado a duas
contas; login apenas por esse email é ambíguo e será rejeitado com 401. Deve ser
usado o nome de utilizador único, ou o par nome/email quando único, com a
password correcta. Nenhuma conta, hash, papel, auditoria ou `last_login` real
foi modificado por esta verificação.

A password em texto claro não foi fornecida, pelo que não foi efectuado login
real dessa conta nem emitido um token em seu nome. Não foram consultados os
relatórios clínicos reais. Antes de avançar para a etapa seguinte, o utilizador
deve confirmar o login com a sua password no ambiente configurado e o acesso
a um relatório VL e a uma subdivisão proibida. O código fica localmente em
`izi`, sem staging nem commit, para essa validação e commit manual. Em 13 de
Novembro, o cadastro Git confirmou o commit manual `9c5fa0b`, e o utilizador
solicitou o avanço para a etapa 4. O agente não realizou nova validação da
password real ou dos indicadores SQL.

## Etapa 4 — Erros HTTP e cache

Branch `fix/04-reporting-errors`, criada numa worktree isolada em 13 de Novembro
de 2026 a partir de `izi` no commit `9c5fa0b`. A cópia inicial estava limpa.
Destino de integração local: apenas `izi`. A validação e integração em `dev`
continuam a pertencer ao utilizador; não é feito push automático.

### Problemas reproduzidos

A pipeline já convertia muitos erros dos serviços em códigos HTTP reais. A
revisão encontrou falhas residuais concretas, sem necessitar de alterar as
consultas dos indicadores:

- Respostas 5xx eliminavam `error`, mas conservavam campos arbitrários como
  `details`, `trace` ou `data`, permitindo publicar detalhes internos.
- `HTTPException` 500/503 era relançada com descrições potencialmente internas.
- Um ficheiro de cache com um erro de serviço podia ser servido como HTTP 200.
  JSON não objecto, timestamp inválido ou envelope sem dados podiam interromper
  o relatório. Falhas de lookup/escrita também escapavam ao tratamento comum.
- As seis rotas de dicionários devolviam HTTP 200 e o texto da excepção quando
  a consulta falhava. Falhas na escrita atómica do cache podiam deixar `.tmp`,
  incluindo um descritor aberto que impedia a remoção no Windows.

### Alterações e compatibilidade

- A resposta 5xx contém apenas `status`, `code` e a mensagem fixa
  `An error occurred`. O código declarado é preservado, incluindo 503; excepções
  inesperadas e códigos de erro inválidos dão 500. Contratos 4xx, parsing,
  listas de sucesso, paginação e resultados vazios são preservados.
- Os seis GET de dicionários usam a pipeline comum, com uma única consulta ao
  papel, preservando filtros e permissões. Excepções passam a HTTP 500 genérico;
  os dicionários continuam sem cache. Swagger documenta este comportamento.
- Entradas do cache exigem chave correspondente e válida, dados de sucesso,
  timestamp com timezone, não futuro e dentro do prazo. Erros, corrupção e
  falhas de acesso são tratados como ausência de cache e o relatório é calculado.
  Se esse relatório falhar, o cliente recebe o erro actual, sem fallback expirado.
- Apenas sucessos são gravados. Falhas de serialização, abertura ou substituição
  preservam a entrada anterior e removem o temporário. O warm-up ignora entradas
  inválidas e mantém chaves antigas válidas para recomputação.
- Não mudam as janelas, TTL padrão, chaves das entradas válidas, consultas SQL,
  papéis, login ou autenticação Clerk. A autorização continua anterior ao cache.
  Não são necessárias migrações ou uma limpeza geral do cache.

O [contrato de erros e cache](reporting-errors-and-cache.md), o README, a
[matriz de acesso](access-control.md) e o Swagger foram actualizados. Nesta etapa,
a protecção dos dados de pacientes nos logs ficou reservada à etapa 5.

### Validação

| Verificação | Resultado |
| --- | --- |
| Contrato HTTP antes da correcção | 54 falhas, 42 sucessos |
| Cache antes da correcção inicial | 40 falhas, 6 sucessos |
| Excepções nas seis rotas de dicionários antes da correcção | 6 falhas |
| Novas regressões de contrato HTTP | 96 sucessos |
| Cache existente e novas regressões, incluindo falha de abertura no Windows | 93 sucessos |
| Novas regressões de dicionários | 54 sucessos |
| Conjunto dirigido, incluindo permissões e Swagger | 387 sucessos |
| Suite completa na branch da etapa | 2 325 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente do código e novos testes | Sem bloqueadores identificados |
| Verificação do diff | `git diff --check` sem erros |

Foram acrescentados 197 casos de regressão. Os testes usam SQLite, tokens e
dados sintéticos, serviços simulados e ficheiros temporários. Não fazem consultas
SQL Server, chamadas reais ao Clerk, envio de emails ou alterações a contas reais.
Os resultados comprovam os contratos HTTP, permissões, cache e integração local;
não comprovam indicadores de produção ou disponibilidade dos serviços externos.

```powershell
python -m pytest tests/test_reporting_error_contract.py tests/test_reporting_errors.py tests/test_report_cache.py tests/test_report_cache_failures.py tests/test_dictionary_errors.py tests/test_dashboard_roles.py tests/test_swagger_docstrings.py -q
python -m pytest -q
git diff --check
```

Depois da integração em `izi`, validar no ambiente configurado um relatório
autorizado, um acesso proibido e um pedido elegível para cache, confirmando os
headers HIT/MISS. A próxima etapa só deve começar após validação do utilizador.

## Etapa 5 — Privacidade dos logs de pacientes

Branch `fix/05-patient-log-privacy`, criada numa worktree isolada a partir de
`izi` no commit `6559ec5`, após o utilizador pedir o avanço. A cópia inicial
estava limpa. O destino da integração local continua a ser apenas `izi`; a
validação e integração em `dev` pertencem ao utilizador.

### Problemas reproduzidos

- A pipeline registava o campo interno `error` e usava `logger.exception`.
  Uma excepção SQLAlchemy/ODBC podia copiar SQL, parâmetros, nomes, contactos e
  identificadores para o texto ou argumentos do log e para o traceback.
- O serviço de pacientes VL devolvia o texto da excepção em `error`, que a
  pipeline registava. Os quatro serviços TB GX incluíam o detalhe em `message`.
  EID já devolvia erro genérico e registava apenas a classe, pelo que foi mantido.
- Permaneciam prints de consultas com `literal_binds`, filtros e SQL nos serviços
  TB GX e dicionários, incluindo os drill-downs Admin que devolvem pacientes.
  Estes prints também ocorriam em pedidos bem-sucedidos.

### Alterações e compatibilidade

- A pipeline regista eventos fixos, padrão da rota, código HTTP validado e/ou
  classe da excepção. Não entrega ao logger o texto/objecto da excepção, dados
  do pedido, SQL, valores de filtros ou traceback, incluindo os argumentos
  retidos em `LogRecord`. Rejeições de token seguem a mesma regra.
- É usado o padrão registado da rota, evitando valores dinâmicos do URL.
  Mensagens de validação 400 e os contratos HTTP existentes são preservados.
- VL e as quatro pesquisas TB GX devolvem um 500 genérico e registam apenas o
  tipo da falha. O padrão seguro já existente em EID permanece sem alterações.
- Foram removidos 17 prints activos de SQL/filtros: dois das pesquisas TB GX e
  15 dos serviços de unidades sanitárias, laboratórios e dicionários. Consultas,
  selecções, filtros, paginação e serializadores não foram reescritos.
- As respostas Admin mantêm os dados clínicos previstos, sem os copiar para
  stdout ou logs. A autorização precede consultas/cache; pacientes continuam
  reservados a Admin e sem cache. Login, Clerk e auditoria de contas são mantidos.

O [contrato de privacidade dos logs](patient-log-privacy.md), README, Swagger,
[matriz de acesso](access-control.md) e [contrato de erros/cache](reporting-errors-and-cache.md)
foram actualizados, incluindo o diagnóstico seguro e os limites operacionais.

### Validação

| Verificação | Resultado |
| --- | --- |
| Primeiros testes de privacidade antes da correcção | 69 falhas, 85 sucessos |
| Drill-downs/dicionários antes da remoção de prints | 6 falhas, 2 sucessos |
| Privacidade HTTP/serviços, incluindo logging de token e rota dinâmica | 167 sucessos |
| Drill-downs TB Admin e dicionários com consultas/serialização reais | 8 sucessos |
| Conjunto dirigido, incluindo pacientes, SQL, HTTP, cache e tokens | 416 sucessos |
| Suite completa na branch da etapa | 2 500 sucessos, 1 ignorado, nenhuma falha |
| Revisão independente da pipeline, serviços e novos testes | Sem bloqueadores identificados |
| Verificação do diff | `git diff --check` sem erros |

Os 175 novos casos cobrem as 11 rotas de pacientes (quatro VL, três EID e quatro
TB GX), erros devolvidos, excepções inesperadas, `StatementError` com SQL e
parâmetros e objectos cuja conversão para texto falha. São inspeccionados stdout,
stderr e os campos retidos pelo logger, além do corpo HTTP. Também são exercitados
os serializadores de sucesso, paginação, restrições 401/403 e ausência de cache.

São usados SQLite, dados/tokens sintéticos e execução SQL substituída. Não foram
consultadas bases clínicas, alteradas contas reais ou enviados emails. Não são
reconfigurados logs de proxies, servidor HTTP, ODBC ou SQL Server, nem eliminados
logs históricos. A nova documentação distingue estes limites da protecção dos
diagnósticos da aplicação; os testes não comprovam indicadores SQL reais.

```powershell
python -m pytest tests/test_patient_log_privacy.py tests/test_patient_drilldown_log_privacy.py tests/hiv/test_vl_patients.py tests/hiv/test_vl_patients_sql.py tests/hiv/test_eid_patients.py tests/hiv/test_eid_patients_sql.py tests/tb/test_tb_patients.py tests/test_reporting_error_contract.py tests/test_report_cache.py tests/test_token_verification.py -q
python -m pytest -q
git diff --check
```

Após a integração em `izi`, validar no ambiente configurado um sucesso e uma
falha controlada, usando dados sintéticos, e confirmar que os novos logs contêm
apenas os diagnósticos previstos. As cinco etapas do plano inicial ficam
implementadas localmente; o avanço para doenças avançadas aguarda a validação
do utilizador e a definição dos respectivos modelos, indicadores e endpoints.
