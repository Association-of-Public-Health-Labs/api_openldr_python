# Dúvidas e sugestões das dashboards

Os módulos partilham o mesmo serviço autenticado de envio por email:

| Módulo | Endpoint POST |
| --- | --- |
| TB | `/tb/send-suggestion` |
| TB GeneXpert | `/tb/gx/send-suggestion` |
| TB Cultura | `/tb/cultura/send-suggestion` |
| HIV | `/hiv/send-suggestion` |
| HIV Carga Viral | `/hiv/vl/send-suggestion` |
| HIV EID | `/hiv/eid/send-suggestion` |

As variantes com `/` final também são aceites, sem redirecionamento.
O parâmetro `duvida` é obrigatório: `true` para dúvida e `false` para sugestão.
Este parâmetro prevalece sobre `category`; o módulo vem da rota.

Exemplo de pedido da dashboard, com um token de sessão Clerk ou da API:

```http
POST /tb/gx/send-suggestion?duvida=true
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "<p>teste</p>",
  "category": "doubt",
  "reportTitle": "Relatório de Resultados - Ultra",
  "userEmail": "irzelindo.salvador@gmail.com",
  "userName": "irzelindo salvador"
}
```

`content` e `reportTitle` são obrigatórios, com limites de 100 000 e 250 caracteres.
O conteúdo deve conter texto. `category`, quando presente, aceita `doubt` ou `suggestion`.
`userEmail` e `userName` são metadados opcionais (254 e 250 caracteres).
O email inclui o conteúdo em texto, o HTML original como texto, todos os campos
enviados e a identificação do utilizador autenticado. Não renderiza HTML do editor.

Destinatários fixos:

- irzelindo.salvador@moz.aphl.org
- diosdelio.malamule@moz.aphl.org
- vagner.ermelindo@moz.aphl.org

O utilizador vai em **CC** e **Reply-To**. A API valida o token pelo mesmo
`authenticate_request()` dos relatórios, extrai o `user_id` e consulta o cadastro
com `get_user_by_id_service()`. Se o cadastro não tiver email, usa `email_address`
ou `email` do token validado. Se não existir email válido nestas fontes, devolve
400. `userEmail` do JSON não define destinatários nem substitui a identidade.

## Configuração SMTP

Todas as opções SMTP são lidas em `configs/paths.py`, tal como as restantes
configurações do projeto. No Windows, preencher a secção `[Email]` já incluída
em `configs/configs.ini` (modelo em `configs/configs.ini.example`). No Linux,
definir as variáveis de ambiente de `.env.example` no processo da API:

```dotenv
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_USERNAME=<utilizador SMTP>
SMTP_PASSWORD=<palavra-passe SMTP>
SMTP_FROM_ADDRESS=openldr@example.org
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=15
```

No Windows, a configuração é lida desta secção de `configs/configs.ini`:

```ini
[Email]
host = smtp.example.org
port = 587
username = <utilizador SMTP>
password = <palavra-passe SMTP>
from_address = openldr@example.org
use_tls = true
use_ssl = false
timeout = 15
```

Para SSL direto, usar porta 465, `use_ssl=true` e `use_tls=false`.
Para relay sem autenticação, deixar `username` e `password` vazios.
O timeout deve ser maior que 0 e no máximo 60 segundos. Reiniciar o serviço após
alterar a configuração. A aplicação não carrega `.env` automaticamente; no Docker,
passar estas variáveis ao container, por exemplo com `env_file: .env` no Compose.

## Respostas e integração da dashboard

- **200**: SMTP aceitou a mensagem para todos os destinatários, incluindo CC.
- **400**: JSON, payload, `duvida` ou email do utilizador inválido/ausente.
- **401**: token ausente ou inválido.
- **502**: falha de SMTP ou recusa de algum destinatário.
- **503**: SMTP não configurado ou configuração inválida.
- **500**: falha interna, por exemplo na consulta do cadastro.

O envio é síncrono e não existe fila nem repetição automática. Uma recusa parcial
do SMTP pode significar que outros destinatários já aceitaram a mensagem.

O frontend deve encaminhar o pedido atualmente enviado para `/api/send-suggestion`
para a rota correspondente da API, anexar `?duvida=true` ou `?duvida=false` e
encaminhar `Authorization: Bearer <token>`. Esse proxy do frontend está fora
deste repositório. Não foi criado um alias `/api/send-suggestion` na API.

Os testes `tests/test_suggestions.py` simulam SMTP e não enviam emails reais.
