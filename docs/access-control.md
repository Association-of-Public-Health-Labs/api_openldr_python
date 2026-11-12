# Papéis e acesso por subdivisão

Cada conta tem **um papel** no campo existente `User.role`. Não há alteração de
esquema nem atribuição automática de novos privilégios às contas existentes.
O controlo é aplicado pela API, independentemente do que a dashboard mostre.

| Papel persistido | Relatórios permitidos | Gestão de utilizadores |
| --- | --- | --- |
| `vl` | Carga viral: `/hiv/vl/*` | Não |
| `dpi` | Diagnóstico infantil precoce: `/hiv/eid/*` | Não |
| `tb_gx` | GeneXpert: `/tb/gx/*` | Não |
| `tb_cl` | Cultura: `/tb/cultura/*` | Não |
| `ad` | Doenças avançadas: `/hiv/ad/*`, reservado para implementação futura | Não |
| `global` | Todas as subdivisões de relatórios | Não |
| `Admin` | Todas as subdivisões, incluindo os acessos privilegiados existentes | Sim |
| `user` | Sem subdivisão atribuída | Não |

O nome do papel DPI é `dpi`; as rotas existentes continuam em `/hiv/eid/`.
Os nomes `tb_gx` e `tb_cl` também não alteram os URLs já usados pelas dashboards.
A reserva AD não cria endpoints nem modelos de CD4, CrAg ou TB-LAM.

## Limites dos papéis de leitura

Os papéis das subdivisões e `global` dão acesso aos relatórios. Mantêm-se os
controlos Admin existentes para pesquisas de pacientes, agregados VL por unidade
sanitária (`facility_type=health_facility`) e drill-downs que devolvem dados
individuais. O papel `global` não gere contas nem atribui papéis.

Os seis endpoints `/dict/*` são partilhados pelas subdivisões: exigem token
válido e um papel atribuído, incluindo `ad`, `global` ou `Admin`. Já não são
públicos. Os endpoints de sugestões seguem o módulo da rota; os aliases
`/hiv/send-suggestion` e `/tb/send-suggestion` aceitam os papéis da respectiva
família, além de `global` e `Admin`.

O login, a verificação Svix do webhook e a documentação Swagger conservam os
seus mecanismos próprios. O Swagger continua a apresentar a documentação
completa; ver uma rota na documentação não concede acesso aos seus dados.

## Identidade e autorização

1. A API verifica a assinatura e validade do token Clerk ou do token da API.
2. O `sub` verificado identifica a conta local; um claim adicional `user_id`
   não selecciona outra conta.
3. A API consulta o papel persistido em cada pedido. Claims `role` do JWT e
   campos do pedido não atribuem permissões.
4. A autorização é verificada **antes do cache e da consulta ao relatório**.
   Uma alteração de papel ou eliminação da conta tem efeito no pedido seguinte,
   mesmo com o mesmo token e um relatório já em cache.

Token ausente ou inválido nos relatórios/dicionários dá 401; conta sem subdivisão,
papel desconhecido ou acesso a outra subdivisão dá 403. Uma falha na consulta de
permissões dá 500 genérico, sem executar o relatório nem revelar SQL.

Os valores guardados são canónicos. A autorização não promove silenciosamente
valores legados como `admin`, `User` ou ` VL ` para um papel privilegiado.

## Atribuir ou alterar um papel

Apenas um operador cujo papel persistido seja exactamente `Admin` usa
`POST /auth/create` e `PUT /auth/update` para atribuir papéis. Estes endpoints
aceitam os valores da tabela, normalizando maiúsculas/minúsculas e espaços na
atribuição; valores desconhecidos são rejeitados com 400.

Para alterar o papel de uma conta existente sem substituir a password:

```http
PUT /auth/update
Authorization: Bearer <token de Admin>
Content-Type: application/json

{
  "user_id": "<identificador da conta>",
  "username": "<nome actual>",
  "first_name": "<primeiro nome>",
  "last_name": "<apelido>",
  "email": "<email actual>",
  "role": "dpi"
}
```

Omitir `password` e `confirm_password` em conjunto conserva o hash existente.
Para mudar a password, fornecer ambos com o mesmo valor não vazio. Os restantes
campos obrigatórios do endpoint de actualização continuam a ser exigidos.

Contas novas do Clerk continuam a receber `user`, sem acesso a relatórios até
Admin atribuir uma subdivisão ou `global`. Eventos assinados `user.updated`
actualizam o perfil, preservando o papel e a password administrados localmente.
Metadados Clerk não podem atribuir `Admin` ou mudar uma subdivisão.

## Introdução em ambiente de validação

Antes de disponibilizar esta versão às dashboards, um Admin deve atribuir o
papel adequado a cada conta que ainda tenha `user`/`User` ou um valor legado.
Não converter todas as contas para `global`: isso concederia leitura transversal.
Validar uma conta por subdivisão, uma `global` e uma `Admin`, incluindo pedidos
à subdivisão permitida e a uma proibida. Não foram alterados dados reais nesta
implementação; a validação automatizada usa SQLite e tokens de teste.

Novos controladores devem usar `run_reporting_endpoint`, ou a combinação
`authenticate_request`/decorator autenticado para auxiliares. A política pura
de caminhos não instala um bloqueio global: um novo módulo precisa ser
registado na política e usar a pipeline autenticada, com testes de acesso.

O fluxo de branches continua `branch isolada -> testes -> izi`; a integração
e a validação pessoal em `dev` pertencem ao utilizador. As correcções de login
e credenciais continuam na etapa 3 do [registo de melhorias](priority-improvements.md).
