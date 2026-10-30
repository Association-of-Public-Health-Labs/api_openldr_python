from suggestions.controller import SendSuggestion


MODULES = {
    "/tb": "TB",
    "/tb/gx": "TB GeneXpert",
    "/tb/cultura": "TB Cultura",
    "/hiv": "HIV",
    "/hiv/vl": "HIV Carga Viral",
    "/hiv/eid": "HIV Diagnóstico Infantil Precoce",
}


def suggestion_routes(api):
    for prefix, module in MODULES.items():
        api.add_resource(
            SendSuggestion,
            f"{prefix}/send-suggestion",
            endpoint=f"send_suggestion_{prefix.strip('/').replace('/', '_')}",
            resource_class_kwargs={"module": module},
            strict_slashes=False,
        )
