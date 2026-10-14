from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.types import Receive, Scope, Send

from py_semantic_taxonomy.dependencies import get_graph_service
from py_semantic_taxonomy.domain import entities as de

router = APIRouter(include_in_schema=False)


@router.get("/")
async def redirect_main_page(
    request: Request,
) -> RedirectResponse:
    return RedirectResponse(request.url_for("web_concept_schemes"))


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


async def resolve_iri(scope: Scope, receive: Receive, send: Send) -> None:
    """Resolve an object's own IRI.

    Objects are identified by IRIs which are (when deployed correctly) served by this
    application. Following such an IRI in a browser should show the web UI; a request for
    JSON(-LD) should return the machine-readable data instead of a 404.

    Installed as the app router's `default`, so it only runs when no route matched and
    Starlette's trailing-slash redirect did not apply.
    """
    if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD"):
        return await scope["router"].not_found(scope, receive, send)
    request = Request(scope, receive)
    iri = str(request.url.replace(query=""))
    service = get_graph_service()
    # No web UI for correspondences, so always return JSON-LD.
    getters = {
        de.ConceptScheme: (service.concept_scheme_get, "web_concept_scheme_view"),
        de.Concept: (service.concept_get, "web_concept_view"),
        de.Correspondence: (service.correspondence_get, None),
    }
    try:
        get, view = getters[await service.get_object_type(iri=iri)]
    except (de.NotFoundError, KeyError):
        response = JSONResponse({"detail": f"No object found with IRI `{iri}`"}, status_code=404)
    else:
        headers = {"Vary": "Accept"}
        if view and _wants_html(request):
            response = RedirectResponse(request.url_for(view, iri=quote(iri)), headers=headers)
        else:
            response = JSONResponse((await get(iri=iri)).to_json_ld(), headers=headers)
    await response(scope, receive, send)
