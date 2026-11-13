# Desactivação lógica de utilizadores

Implementação na branch `feat/user-soft-deactivation`, a partir de `izi` no
commit `fa03f28`. Destino de integração: `izi`. Não foi encontrado `AGENTS.md`
no checkout nem nos directórios superiores verificados; foram respeitados os
fluxos existentes de contas, JWT, auditoria e trabalho por branch isolada.

## Gestão de contas, identidade e auditoria

A gestão de contas está em `auth`, com Flask-RESTful e Flask-JWT-Extended. O
login local verifica bcrypt e emite um JWT de acesso válido por uma hora. Os
relatórios, dicionários e sugestões também aceitam sessões Clerk RS256, validadas
com JWKS, issuer e authorized party. Eventos Clerk exigem assinatura Svix.
As permissões vêm da conta persistida, sem confiar no claim `role` do token.
Não existe um endpoint local de renovação ou emissão de refresh tokens.

`UserLogs` já guarda eventos de login, consulta de contas e eventos Clerk. A
desactivação acrescenta um registo transaccional `user_deactivated` apenas se o
estado mudar. O campo `user_id` desse registo aponta para a conta alvo, que é
preservada, e `log_details` contém `actor_id`, `target_user_id`, `deactivated_at`
e `source` (`api` ou `clerk`). Para o webhook verificado, o autor é `clerk`.
O timestamp usa `datetime.now()`, sem timezone, como as escritas existentes do
projecto; a mesma data alimenta `updated_at`, `log_date` e os detalhes do evento.
Falha de auditoria ou commit reverte a alteração do estado na mesma transacção.

## Contrato de remoção

```http
DELETE /auth/delete
Authorization: Bearer <JWT de um Admin activo>
Content-Type: application/json

{"user_id": "<identificador da conta>"}
```

As permissões e o corpo de sucesso anterior são conservados: HTTP 200, mensagem
`User deleted successfully` e `data` com `user_id`, `username`, `first_name`,
`last_name`, `email` e `role`. A mensagem legada não significa eliminação física.

- Um `UPDATE` usa a chave `user_id` e a condição `is_active = 1`, gravando
  `is_active = 0` e `updated_at`.
- Alvo inexistente mantém HTTP 404; um utilizador activo sem Admin mantém 403.
  JWT inválido ou associado a uma conta ausente/inactiva é recusado com 401.
- A repetição por um Admin activo mantém HTTP 200 e o corpo, sem mudar a data
  da primeira desactivação nem acrescentar auditoria. A condição no `UPDATE`
  impede duas transições caso os pedidos concorram.
- Um Admin pode desactivar a própria conta; o seu JWT deixa de autorizar o pedido
  seguinte. Repetições administrativas requerem outra conta Admin activa.
- A linha, password, papel e referências de auditoria permanecem. Não existe
  endpoint de reactivação nesta alteração; campos extra no pedido não a activam.

O modelo passa a usar a chave indicada, `user_id NVARCHAR(50)`, conservando a
coluna numérica `id` legada. `is_active` é `Boolean`, obrigatório, com defaults
Python e SQL iguais a 1. Foram pesquisados os INSERTs SQL de contas no repositório:
não existem escritores SQL directos de produção a adaptar; as criações ORM
gravam contas activas e o default cobre INSERTs externos que omitam a coluna.

## Login, JWT e histórico

Login por username/email pesquisa apenas contas activas. Inactivas recebem a
mesma resposta 401 `Invalid credentials`, sem token ou novo marcador de login.
Outra conta activa continua a autenticar-se normalmente.

A pipeline de relatórios/dicionários/sugestões e os quatro métodos protegidos
de gestão de contas consultam novamente a conta na base. A consulta não reutiliza
estado ORM antigo. API JWT e Clerk JWT são recusados no primeiro pedido protegido
posterior ao commit, antes de qualquer HIT de cache. Um refresh token é recusado
como access token; não foi acrescentada uma rota de renovação inexistente.

`GET /auth/users` e as pesquisas operacionais devolvem só activos. A função
interna `get_user_by_id_service(..., include_inactive=True)` permite resolver
uma conta histórica/tombstone; não é um parâmetro HTTP nem dispensa autorização.
As consultas autorizadas existentes sobre `UserLogs` continuam a ver o histórico.
Não foi criado um novo endpoint de auditoria nem aplicado um filtro global às
consultas de histórico.

`user.deleted` do Clerk usa a mesma desactivação atómica e não duplica o evento
quando é reaplicado. `session.created` de uma conta inactiva dá 401 e não a recria
nem grava um login. `user.updated` não altera a conta inactiva; provisionar um
`user_id` já existente dá 409. Metadados Clerk não reactivam a conta.

## Migração manual para SQL Server 2014

1. [001_add_user_is_active.sql](../sql/auth/001_add_user_is_active.sql) opera em
   `Utils.dbo.openldr_api_user_users`. Verifica a base, a chave primária simples
   `user_id NVARCHAR(50)` e adiciona `is_active BIT NOT NULL`, com a constraint
   `DF_openldr_api_user_users_is_active DEFAULT (1)` e `WITH VALUES`.
2. [002_verify_user_is_active.sql](../sql/auth/002_verify_user_is_active.sql)
   verifica o schema/default e mostra apenas contagens de contas, em leitura.

A inicialização dos existentes como activos só ocorre quando a coluna é criada.
Na reaplicação não há `UPDATE` dos dados nem alteração de `updated_at`, pelo que
os zeros já gravados são mantidos. Se só faltar o default, este é acrescentado
para futuros INSERTs sem alterar os estados. Tipo, nullability, chave ou default
incompatíveis provocam erro e rollback; o script não tenta reparar diferenças
destrutivamente. Não altera a chave física, não renomeia constraints existentes
e não remove linhas nem referências de auditoria.

Os scripts usam sintaxe disponível em SQL Server 2014 e validam a base depois
de `USE`, antes de tocar na tabela. Não são executados pelo arranque da aplicação.
Os predicados ORM são compilados/testados como `is_active = 1`, evitando `IS 1`,
que o SQL Server não aceita para BIT.

## Testes e execução no ambiente de teste

Os testes da API usam SQLite, bcrypt e JWT API/Clerk sintéticos, sem alterar
contas reais ou contactar Clerk/SMTP. Cobrem permissões, preservação da linha e
histórico, auditoria/rollback, idempotência, a conta activa de controlo, listas,
estado ORM pré-carregado e a recusa de tokens anteriores mesmo com cache.

| Verificação local | Resultado |
| --- | --- |
| Novos testes da funcionalidade | 46 aprovados |
| Contratos/compatibilidade estática dos scripts SQL | 10 aprovados |
| Execução da migração/reaplicação em SQL Server | 14 ignorados por falta de configuração de teste |
| Funcionalidade, scripts e Swagger em conjunto | 57 aprovados, 14 ignorados |
| Suite completa na branch da funcionalidade | 2 556 aprovados, 15 ignorados, nenhuma falha |
| Revisão independente dos fluxos JWT/Clerk e migração | Sem bloqueadores de código identificados |
| `git diff --check` | Sem erros |

Dos 15 testes ignorados na suite, 14 são os testes SQL Server novos e um já
existia. As expectativas antigas de eliminação física e de 403 para uma
identidade inexistente foram adaptadas à preservação da linha e ao novo 401 de
autenticação; uma conta activa sem privilégios continua a receber 403.

Os testes de migração separam verificações estáticas de execução T-SQL real.
**A execução em SQL Server de teste está pendente neste ambiente.** Sem as duas
variáveis abaixo, os 14 casos SQL são explicitamente ignorados; SQLite e a
compilação MSSQL não comprovam DDL, reaplicação ou comportamento do driver real.

Para executar os testes SQL, preparar uma base **vazia e descartável**, de
preferência numa instância SQL Server 2014, cujo nome comece por
`OpenLDR_API_test_deactivation_`. Configurar no processo de teste:

```powershell
$env:OPENLDR_DEACTIVATION_SQLSERVER_TEST_DATABASE = 'OpenLDR_API_test_deactivation_validation'
# OPENLDR_DEACTIVATION_SQLSERVER_TEST_CONNECTION_STRING deve vir da configuração
# segura do ambiente, seleccionando exactamente essa base; não usar Utils.
python -m pytest tests/test_user_deactivation_migration.py -q -rs
python -m pytest tests/test_user_deactivation.py -q
python -m pytest -q
```

O harness recusa outras bases, ligação a uma base diferente e tabelas de contas
ou auditoria preexistentes. Só substitui o nome de destino nos scripts; o DDL e
os dados sintéticos ficam numa transacção exterior revertida no final. Testa
backfill, INSERT sem a coluna, reaplicação com conta inactiva/data preservadas,
histórico com foreign key, default em falta e rejeição de schema/base incorrectos.

## Ordem de publicação

1. Executar a suite e os testes T-SQL na base descartável; depois aplicar/testar
   a migração no ambiente de homologação e validar a API nesse ambiente.
2. Na publicação, aplicar manualmente **001 na base Utils antes da nova API**.
   Se houver erro de schema/default/chave, interromper a publicação e investigar.
3. Executar **002** e confirmar BIT NOT NULL, constraint/default e contagens.
   Reaplicar 001 para confirmar que os estados existentes se mantêm.
4. Publicar a nova API e reiniciar todos os workers/instâncias. Só permitir
   desactivações quando todas as instâncias usarem a nova versão; uma instância
   antiga ainda ignora `is_active`.
5. Validar com contas de teste: login activo, desactivação por Admin, repetição
   sem nova data/evento, JWT anterior recusado e outra conta activa operacional.

A integração do código em `izi` não aplica a migração nem publica o serviço.
O código novo requer a coluna; executá-lo antes da migração dá erro de schema.
Num rollback, conservar a coluna e o histórico. Voltar a uma API antiga que ignore
`is_active` volta a permitir contas desactivadas, pelo que o rollback deve manter
a validação de estado; não remover a coluna como recuperação automática.

## Ficheiros alterados

- [auth/user_model.py](../auth/user_model.py): chave e booleano.
- [auth/auth_service.py](../auth/auth_service.py): desactivação, auditoria, login e pesquisas.
- [auth/auth_controller.py](../auth/auth_controller.py): contas activas nos métodos JWT, Clerk e Swagger.
- [utilities/controller_helpers.py](../utilities/controller_helpers.py): verificação de conta antes de permissões/cache.
- [utilities/token_verification.py](../utilities/token_verification.py): token de acesso obrigatório na API.
- [utilities/swagger.py](../utilities/swagger.py): contrato de desactivação.
- [sql/auth/001_add_user_is_active.sql](../sql/auth/001_add_user_is_active.sql): migração manual.
- [sql/auth/002_verify_user_is_active.sql](../sql/auth/002_verify_user_is_active.sql): verificação em leitura.
- [tests/test_user_deactivation.py](../tests/test_user_deactivation.py): regressões da funcionalidade.
- [tests/test_user_deactivation_migration.py](../tests/test_user_deactivation_migration.py): validação estática e T-SQL opt-in.
- [tests/test_clerk_webhook.py](../tests/test_clerk_webhook.py), [tests/test_dashboard_role_admin.py](../tests/test_dashboard_role_admin.py), [tests/test_dashboard_roles.py](../tests/test_dashboard_roles.py), [tests/test_suggestions.py](../tests/test_suggestions.py) e [tests/test_user_creation.py](../tests/test_user_creation.py): expectativas e fixtures adaptadas aos novos estados de autenticação/preservação da linha.
- [README.md](../README.md), [docs/access-control.md](access-control.md) e este documento: contrato e publicação.
