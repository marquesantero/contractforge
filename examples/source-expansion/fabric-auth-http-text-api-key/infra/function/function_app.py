import os

import azure.functions as func


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="contractforge-http-text-api-key", methods=["GET"])
def contractforge_http_text_api_key(req: func.HttpRequest) -> func.HttpResponse:
    expected = os.environ.get("CONTRACTFORGE_EXPECTED_API_KEY", "")
    supplied = req.headers.get("x-api-key") or req.headers.get("X-Api-Key") or ""
    if not supplied:
        return func.HttpResponse("missing api key", status_code=401, mimetype="text/plain")
    if not expected or supplied != expected:
        return func.HttpResponse("invalid api key", status_code=403, mimetype="text/plain")
    return func.HttpResponse("contractforge_api_key_authenticated=true", status_code=200, mimetype="text/plain")
