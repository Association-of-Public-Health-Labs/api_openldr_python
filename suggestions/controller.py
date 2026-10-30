from flask import current_app, request, session
from flask_restful import Resource
from werkzeug.exceptions import BadRequest

from suggestions.service import send_suggestion
from utilities.controller_helpers import authenticate_request
from utilities.service_helpers import InvalidParameter
from utilities.email_service import EmailDeliveryError


class SendSuggestion(Resource):
    def __init__(self, module):
        self.module = module

    def post(self):
        """Send a dashboard doubt or suggestion by email.
        ---
        tags:
          - Dúvidas e Sugestões
        security:
          - Bearer: []
        parameters:
          - name: duvida
            in: query
            type: boolean
            required: true
            description: True for a doubt; false for a suggestion. Overrides category.
          - name: body
            in: body
            required: true
            schema:
              type: object
              required: [content, reportTitle]
              properties:
                content:
                  type: string
                  example: <p>teste</p>
                category:
                  type: string
                  enum: [doubt, suggestion]
                reportTitle:
                  type: string
                  example: Relatório de Resultados - Ultra
                userEmail:
                  type: string
                  description: Dashboard metadata; CC uses the authenticated user's email.
                userName:
                  type: string
        responses:
          200:
            description: Email accepted by SMTP for all recipients, including the caller in CC.
          400:
            description: Invalid JSON, payload, duvida or unavailable caller email.
          401:
            description: Invalid or missing token.
          502:
            description: Email delivery failed.
          503:
            description: Email service is not configured.
        """
        user_id, error = authenticate_request()
        if error is not None:
            return error

        try:
            flags = request.args.getlist("duvida")
            if len(flags) != 1 or flags[0].lower() not in {"true", "false"}:
                raise InvalidParameter("duvida must be true or false")
            if not request.is_json:
                raise InvalidParameter("A JSON payload is required")
            payload = request.get_json()
            send_suggestion(
                payload,
                is_doubt=flags[0].lower() == "true",
                module=self.module,
                user_id=user_id,
                user_info=session["user_info"],
            )
            return {
                "status": "success",
                "code": 200,
                "message": "Mensagem enviada com sucesso.",
            }, 200
        except (InvalidParameter, BadRequest) as exc:
            message = (
                str(exc)
                if isinstance(exc, InvalidParameter)
                else "Invalid JSON payload"
            )
            return {"status": "error", "code": 400, "message": message}, 400
        except EmailDeliveryError as exc:
            current_app.logger.error(
                "Suggestion email failed on %s (%s)", request.path, type(exc).__name__
            )
            return {
                "status": "error",
                "code": exc.code,
                "message": exc.public_message,
            }, exc.code
        except Exception:
            current_app.logger.exception(
                "Suggestion request failed on %s", request.path
            )
            return {"status": "error", "code": 500, "message": "An error occurred"}, 500
