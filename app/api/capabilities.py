from flask import request, current_app

from app import api_bp, JSONAPIResponseFactory


COLLECTIONS_PARAMETERS = {
    "search": "search[fieldname1,fieldname2]=expression ou search=expression pour chercher parmis tous les champs indexés",
    "filter": "filter[field_name]=searched_value. Le nom du champs DOIT être un des champs du model",
    "sort": "sort=field1,field2,field3. Le tri respecte l'ordre des champs. Utiliser - pour effectuer un tri descendant",
    "page": "page[number]=3&page[size]=10. La pagination nécessite page[number], page[size] ou les deux paramètres en même temps. La taille ne peut pas excéder la limite inscrite dans la facade correspondante. La pagination produit des liens de navigation prev,next,self,first,last dans tous les cas où cela a du sens.",
    "include": "include=relation1,relation2. Le document retourné incluera les ressources liées à la présente ressource. Il n'est pas possible d'inclure une relation indirecte (ex: model.relation1.relation2)",
    "lightweight": "Ce paramètre n'a pas de valeur. Sa seule présence dans l'URL permet d'obtenir une version allégée du document (les relations ne sont pas incluses dans la réponse)."
}


@api_bp.route("/api/<api_version>")
def api_get_capabilities(api_version):
    if "capabilities" in request.args:
        url_prefix = request.host_url[:-1] + current_app.config["API_URL_PREFIX"]
        capabilities = [
        ]

        meta = {
            "description": ""
        }
        return JSONAPIResponseFactory.make_data_response(capabilities, links=None,  included_resources=None, meta=meta)