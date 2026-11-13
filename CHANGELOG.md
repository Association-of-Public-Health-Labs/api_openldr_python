# Histórico de versões da OpenLDR API

## 2.0.0 — preparada para validação

A versão anterior indicada pelo Swagger era `1.0.0`. Esta actualização reúne as
melhorias integradas em `izi`; a publicação em produção depende da validação da
migração em SQL Server de teste. O número identifica o código da API, sem afirmar
que esta versão já foi publicada em todos os ambientes.

### Alterações para os consumidores

- **Acesso por subdivisão:** os papéis persistidos `vl`, `dpi`, `tb_gx`, `tb_cl`
  e `ad` limitam o acesso aos relatórios correspondentes. `global` lê todas as
  subdivisões e `Admin` mantém os privilégios administrativos. Os dicionários
  partilhados exigem um papel de dashboard atribuído. A criação pública de contas
  não permite conceder privilégios administrativos. Consultar a
  [matriz de acesso](docs/access-control.md).
- **Login local:** usa username ou email e password verificada com bcrypt.
  A autenticação por sessões Clerk continua disponível. As permissões são
  determinadas pela conta persistida, não pelo papel declarado no JWT.
- **Desactivação de contas:** `DELETE /auth/delete` preserva a linha e o histórico,
  mantendo as permissões e o corpo HTTP 200 de sucesso anteriores. A repetição
  conserva a primeira data e não duplica a auditoria. Contas inactivas deixam de
  aparecer nas listas operacionais e não podem efectuar login. JWT API e Clerk
  anteriores são recusados no pedido protegido seguinte após o commit da
  desactivação. Uma identidade ausente ou inactiva recebe HTTP 401; uma conta
  activa sem privilégios recebe 403. Consultar o
  [contrato de desactivação](docs/user-deactivation.md).
- **Erros e cache:** relatórios e dicionários devolvem os códigos HTTP de erro
  efectivos. Respostas 5xx usam mensagem genérica e relatórios falhados não são
  guardados nem devolvidos como sucessos HTTP 200 pelo cache. Consultar o
  [contrato de erros e cache](docs/reporting-errors-and-cache.md).
- **Privacidade dos logs:** o diagnóstico dos relatórios conserva padrões de
  rota, códigos HTTP e classes de erro sem dados de pacientes, valores da query
  ou tracebacks. Consultar a [política de logs](docs/patient-log-privacy.md).

### Compatibilidade e publicação

O incremento para `2.0.0` reflecte alterações no contrato observável: permissões
por subdivisão, códigos HTTP de erro e remoção lógica. Os consumidores devem
rever o tratamento de 401/403/5xx e não assumir que uma remoção elimina a conta
fisicamente. Os caminhos dos endpoints existentes mantêm-se.

Ordem de publicação:

1. Validar a migração, a reaplicação e os testes em SQL Server de teste, seguindo
   o [guia de desactivação](docs/user-deactivation.md#testes-e-execução-no-ambiente-de-teste).
   Os 14 testes SQL Server continuam pendentes por falta de configuração desse
   ambiente; os testes locais não substituem esta validação.
2. Aplicar manualmente [001_add_user_is_active.sql](sql/auth/001_add_user_is_active.sql)
   e executar [002_verify_user_is_active.sql](sql/auth/002_verify_user_is_active.sql)
   **antes de publicar a nova versão da API**.
3. Publicar a API e reiniciar todos os workers, conforme o
   [guia de publicação](docs/user-deactivation.md). Confirmar o número `2.0.0`
   em `/apidocs/` e em `info.version` de `/apispec_1.json`, e validar os fluxos
   de autenticação e desactivação antes de disponibilizar a operação.

### Validação desta actualização

- Suite completa: **2 556 testes aprovados e 15 ignorados**, sem falhas. Dos
  ignorados, 14 dependem do SQL Server de teste e um já existia.
- Teste dedicado de geração do Swagger: **1 aprovado**.
- Verificação HTTP com o cliente Flask de teste: `/apispec_1.json` e `/apidocs/`
  respondem com 200; a especificação anuncia `2.0.0` e inclui as notas da versão.
  Confirmada a consistência com README e constante, mantendo o formato Swagger
  `2.0` e a interface Swagger UI `3`.

### Actualizações futuras

A fonte única da versão em execução é
[`API_VERSION`](utilities/api_version.py), utilizada pelo
[template Swagger](utilities/swagger.py). O valor `swagger: 2.0` identifica o
formato da especificação e `uiversion: 3` identifica a interface Swagger UI;
nenhum destes valores é a versão da OpenLDR API.

Em cada entrega, actualizar a constante, abrir uma entrada neste histórico e
actualizar a versão apresentada no [README](README.md). Usar `MAJOR.MINOR.PATCH`:
incrementar MAJOR para alterações incompatíveis do contrato, MINOR para
funcionalidades compatíveis e PATCH para correcções compatíveis. Actualizar
também o resumo visível no Swagger e os documentos afectados pela alteração.

Antes de integrar em `izi`, executar os testes adequados à alteração e
`python -m pytest tests/test_swagger_docstrings.py -q`, e confirmar a versão e
as notas em `/apispec_1.json` e `/apidocs/`. A validação e integração em `dev`
continuam sob responsabilidade do utilizador.
