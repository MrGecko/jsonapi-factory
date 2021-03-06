import json
import urllib
import sys

from math import ceil
from collections import OrderedDict

from flask import request
from sqlalchemy import func, desc, asc
from sqlalchemy.exc import OperationalError

from app import JSONAPIResponseFactory, api_bp, db

if sys.version_info < (3, 6):
    json_loads = lambda s: json_loads(s.decode("utf-8")) if isinstance(s, bytes) else json.loads(s)
else:
    json_loads = json.loads


# TODO: voir si le param api_version est encore utile (on peut peut-être juste utiliser url_prefix
# TODO: voir si on peut virer les références à model dans ce fichier et passer par la facade
# TODO: gérer PATCH,POST,DELETE
# TODO: gérer les références transitives (qui passent par des relations)
# TODO: gérer les sparse fields


class JSONAPIRouteRegistrar(object):
    """

    """

    def __init__(self, api_version, url_prefix):
        self.api_version = api_version
        self.url_prefix = url_prefix

        # make a dict from models and their __tablename__
        self.models = dict([(cls.__tablename__, cls) for cls in db.Model._decl_class_registry.values()
                            if isinstance(cls, type) and issubclass(cls, db.Model)])

    @staticmethod
    def get_relationships_mode(args):
        if "without-relationships" in args:
            w_rel_links = False
            w_rel_data = False
        else:
            w_rel_links = True
            w_rel_data = True
            if "with-relationships" in args:
                w_rel_args = request.args["with-relationships"].split(',')
                if "links" not in w_rel_args:
                    w_rel_links = False
                if "data" not in w_rel_args:
                    w_rel_data = False
        return w_rel_links, w_rel_data

    @staticmethod
    def get_included_resources(asked_relationships, facade_obj):
        try:
            included_resources = OrderedDict({})
            relationships = facade_obj.relationships
            # iter over the relationships to be included
            for inclusion in asked_relationships:
                # try bring the related resources and add them to the list
                related_resources = relationships[inclusion]["resource_getter"]()
                # make unique keys to avoid duplicates
                if isinstance(related_resources, list):
                    for related_resource in related_resources:
                        unique_key = (related_resource["type"], related_resource["id"])
                        included_resources[unique_key] = related_resource
                else:
                    # the resource is a single object
                    if related_resources is not None:
                        unique_key = (related_resources["type"], related_resources["id"])
                        included_resources[unique_key] = related_resources
            return list(included_resources.values()), None
        except KeyError as e:
            return None, JSONAPIResponseFactory.make_errors_response(
                {"status": 404, "title": "Cannot include the relationship %s" % str(e)}, status=404
            )

    @staticmethod
    def count(model):
        return db.session.query(func.count('*')).select_from(model).scalar()

    @staticmethod
    def make_url(url, args):
        url = url.replace("[", "%5B").replace("]", "%5D")
        # recompose URL
        parameters = urllib.parse.urlencode(args)
        if len(parameters) > 0:
            return "%s?%s" % (url, parameters)
        else:
            return url

    def get_obj_from_resource_identifier(self, resource_identifer):
        related_model = self.models.get(resource_identifer["type"].replace("-", "_"), None)
        if related_model is None:
            return None, {"status": 403,
                          "title": "Resource '%s' has a wrong 'type' value" % (
                              resource_identifer)
                          }
        return related_model.query.filter(related_model.id == resource_identifer["id"]).first(), None

    def register_get_routes(self, model, facade_class):
        """

        :param model:
        :param facade_class:
        :param obj_getter:
        :param facade_class:
        :return:
        """

        # ================================
        # Collection resource GET route
        # ================================
        get_collection_rule = '/api/{api_version}/{type_plural}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL
        )

        def collection_endpoint():
            """
            Support the following parameters:
            - Search syntax:
              search[fieldname1,fieldname2]=expression
              or
              search=expression
            - Filtering syntax :
              filter[field_name]=searched_value
              field_name MUST be a mapped field of the underlying queried model
            - Sorting syntax :
              The sort respects the fields order :
              model.field,model.field2,model.field3...
              Sort by ASC by default, use the minus (-) operator to sort by DESC: -model.field
            - Pagination syntax requires page[number], page[size] or both parameters to be supplied in the URL:
              page[number]=1&page[size]=100
              The size cannot be greater than the limit defined in the corresponding Facade class
              If the page size is omitted, it is set to its default value (defined in the Facade class)
              If the page number is omitted, it is set to 1
              Provide self,first,last,prev,next links for the collection (top-level)
              Omit the prev link if the current page is the first one, omit the next link if it is the last one
            - Related resource inclusion :
              ?include=relationname1,relationname2
            - Relationships inclusion
              Adding a request parameter named without-relationships allows the retrieving of resources without their relationships
              It is much, much more efficient to do so.
              Adding a parameter with-relationships allows to retrieve only links to relationships :
                with-relationships (without values) retrieve both links and data
                with-relationships=links,data retrieve both links and data
                with-relationships=data retrieve both links and data
                with-relationships=link only retrieve links
              By default, if without-relationships or with-relationships are not specified, you retrieve everything from the relationships
            Return a 400 Bad Request if something goes wrong with the syntax or
             if the sort/filter criteriae are incorrect
            """
            url_prefix = request.host_url[:-1] + self.url_prefix

            links = {

            }

            objs_query = model.query
            count = None
            try:

                # if request has pagination parameters
                # add links to the top-level object
                if 'page[number]' in request.args or 'page[size]' in request.args:
                    num_page = int(request.args.get('page[number]', 1))
                    page_size = min(
                        facade_class.ITEMS_PER_PAGE,
                        int(request.args.get('page[size]', facade_class.ITEMS_PER_PAGE))
                    )
                else:
                    num_page = 1
                    page_size = facade_class.ITEMS_PER_PAGE

                # if request has search parameter
                # (search request arg, search fieldnames)
                search_parameters = [(f, [field.strip() for field in f[len('search['):-1].split(",")])
                                     for f in request.args.keys() if f.startswith('search[') and f.endswith(']')]
                if len(search_parameters) > 0 or "search" in request.args:
                    if "search" in request.args:
                        expression = request.args["search"]
                        search_fields = ["*"]
                    else:
                        search_request_param, search_fields = search_parameters[0]
                        expression = request.args[search_request_param]

                    print("search parameters: ", search_fields, expression)
                    objs_query, count = model.search(expression, fields=search_fields, page=num_page,
                                                     per_page=page_size)

                # if request has filter parameter
                filter_criteriae = []
                filters = [(f, f[len('filter['):-1])  # (filter_param, filter_fieldname)
                           for f in request.args.keys() if f.startswith('filter[') and f.endswith(']')]
                if len(filters) > 0:
                    for filter_param, filter_fieldname in filters:
                        filter_fieldname = filter_fieldname.replace("-", "_")
                        for criteria in request.args[filter_param].split(','):
                            new_criteria = "%s.%s=='%s'" % (model.__tablename__, filter_fieldname, criteria)
                            filter_criteriae.append(new_criteria)

                    objs_query = objs_query.filter(*filter_criteriae)

                # if request has sorting parameter
                if "sort" in request.args:
                    sort_criteriae = []
                    sort_order = asc
                    for criteria in request.args["sort"].split(','):
                        if criteria.startswith('-'):
                            sort_order = desc
                            criteria = criteria[1:]
                        sort_criteriae.append(getattr(model, criteria.replace("-", "_")))
                    print("sort criteriae: ", request.args["sort"], sort_criteriae)
                    # reset the order clause
                    objs_query = objs_query.order_by(False)
                    # then apply the user order criteriae
                    objs_query = objs_query.order_by(sort_order(*sort_criteriae))

                # apply the pagination after an eventual sort
                if "search" in request.args:
                    all_objs = objs_query.all()  # the search feature has already paginated the results for us
                    # TODO : this is bad because it is dependent on the search system (eg. good for us that elasticsearch provides pagination)
                else:
                    pagination_obj = objs_query.paginate(num_page, page_size, False)
                    all_objs = pagination_obj.items
                args = OrderedDict(request.args)

                if count is None:
                    count = JSONAPIRouteRegistrar.count(model)
                nb_pages = max(1, ceil(count / page_size))

                keep_pagination = "page[size]" in args or "page[number]" in args or count > page_size
                if keep_pagination:
                    args["page[size]"] = page_size
                links["self"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)

                if keep_pagination:
                    args["page[number]"] = 1
                    links["first"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                    args["page[number]"] = nb_pages
                    links["last"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                    if num_page > 1:
                        n = max(1, num_page - 1)
                        if n * page_size <= count:
                            args["page[number]"] = max(1, num_page - 1)
                            links["prev"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                    if num_page < nb_pages:
                        args["page[number]"] = min(nb_pages, num_page + 1)
                        links["next"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)

                # should we retrieve relationships too ?
                w_rel_links, w_rel_data = JSONAPIRouteRegistrar.get_relationships_mode(request.args)

                # finally retrieve the (eventually filtered, sorted, paginated) resources
                facade_objs = [facade_class(url_prefix, obj, w_rel_links, w_rel_data)
                               for obj in all_objs]

                # find out if related resources must be included too
                included_resources = None
                if "include" in request.args:
                    included_resources = []
                    for facade_obj in facade_objs:
                        included_res, errors = JSONAPIRouteRegistrar.get_included_resources(
                            request.args["include"].split(','),
                            facade_obj
                        )
                        if errors:
                            return errors
                        included_resources.extend(included_res)

                return JSONAPIResponseFactory.make_data_response(
                    [obj.resource for obj in facade_objs],
                    links=links,
                    included_resources=included_resources,
                    meta={"search-fields": getattr(model, "__searchable__", []), "total-count": count}
                )

            except (AttributeError, ValueError, OperationalError) as e:
                print(e)
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 400, "details": str(e)}, status=400
                )

        collection_endpoint.__name__ = "%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), collection_endpoint.__name__)
        # register the rule
        api_bp.add_url_rule(get_collection_rule, endpoint=collection_endpoint.__name__, view_func=collection_endpoint)

        # =======================
        # Single resource GET route
        # =======================
        single_obj_rule = '/api/{api_version}/{type_plural}/<id>'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL
        )

        def single_obj_endpoint(id):
            """
            Support the following parameters:
            - Related resource inclusion :
              ?include=relationname1,relationname2
            - Relationships inclusion
              Adding a request parameter named without-relationships allows the retrieving of resources without their relationships
              It is much, much more efficient to do so.
              Adding a parameter with-relationships allows to retrieve only links to relationships :
                with-relationships (without values) retrieve both links and data
                with-relationships=links,data retrieve both links and data
                with-relationships=data retrieve both links and data
                with-relationships=link only retrieve links
              By default, if without-relationships or with-relationships are not specified, you retrieve everything from the relationships
             Return a 400 Bad Request if something goes wrong with the syntax or
             if the sort/filter criteriae are incorrect
            """
            url_prefix = request.host_url[:-1] + self.url_prefix
            w_rel_links, w_rel_data = JSONAPIRouteRegistrar.get_relationships_mode(request.args)
            f_obj, kwargs, errors = facade_class.get_resource_facade(url_prefix, id,
                                                                     with_relationships_links=w_rel_links,
                                                                     with_relationships_data=w_rel_data)
            if f_obj is None:
                return JSONAPIResponseFactory.make_errors_response(errors, **kwargs)
            else:
                links = {
                    "self": request.url
                }

                # is there any other resources to include ?
                included_resources = None
                if "include" in request.args:
                    included_resources, errors = JSONAPIRouteRegistrar.get_included_resources(
                        request.args["include"].split(","),
                        f_obj
                    )
                    if errors:
                        return errors

                return JSONAPIResponseFactory.make_data_response(
                    f_obj.resource, links=links, included_resources=included_resources, meta=None
                )

        single_obj_endpoint.__name__ = "%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), single_obj_endpoint.__name__)
        # register the rule
        api_bp.add_url_rule(single_obj_rule, endpoint=single_obj_endpoint.__name__, view_func=single_obj_endpoint)

    def register_relationship_get_route(self, facade_class, rel_name):
        """
        Supported request parameters :
            - Related resource inclusion :
              ?include=relationname1,relationname2
            - Pagination syntax requires page[number], page[size] or both parameters to be supplied in the URL:
              page[number]=1&page[size]=100
              The size cannot be greater than the limit defined in the corresponding Facade class
              If the page size is omitted, it is set to its default value (defined in the Facade class)
              If the page number is omitted, it is set to 1
              Provides self,first,last,prev,next links for the collection (top-level)
              Omits the prev link if the current page is the first one, omits the next link if it is the last one

        """
        # ===============================
        # Relationships self link route
        # ===============================
        rule = '/api/{api_version}/{type_plural}/<id>/relationships/{rel_name}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL, rel_name=rel_name
        )

        def resource_relationship_endpoint(id):
            url_prefix = request.host_url[:-1] + self.url_prefix
            f_obj, kwargs, errors = facade_class.get_resource_facade(url_prefix, id)

            if f_obj is None:
                return JSONAPIResponseFactory.make_errors_response(errors, **kwargs)
            else:
                relationship = f_obj.relationships[rel_name]
                data = relationship["resource_identifier_getter"]()
                count = len(data)
                links = relationship["links"]
                paginated_links = {}

                try:
                    # if request has pagination parameters
                    # add links to the top-level object
                    if 'page[number]' in request.args or 'page[size]' in request.args:
                        num_page = int(request.args.get('page[number]', 1))
                        page_size = min(
                            facade_class.ITEMS_PER_PAGE,
                            int(request.args.get('page[size]', facade_class.ITEMS_PER_PAGE))
                        )

                        args = OrderedDict(request.args)
                        nb_pages = max(1, ceil(count / page_size))

                        args["page[size]"] = page_size
                        paginated_links["self"] = JSONAPIRouteRegistrar.make_url(links["self"], args)
                        paginated_links["related"] = JSONAPIRouteRegistrar.make_url(links["related"], args)
                        args["page[number]"] = 1
                        paginated_links["first"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        args["page[number]"] = nb_pages
                        paginated_links["last"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        if num_page > 1:
                            n = max(1, num_page - 1)
                            if n * page_size <= count:
                                args["page[number]"] = max(1, num_page - 1)
                                paginated_links["prev"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        if num_page < nb_pages:
                            args["page[number]"] = min(nb_pages, num_page + 1)
                            paginated_links["next"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)

                        # perform the pagination
                        data = data[(num_page - 1) * page_size:min(num_page * page_size, count)]
                        links.update(paginated_links)

                    # try to include related resources if requested
                    included_resources = None
                    if "include" in request.args:
                        included_resources, errors = JSONAPIRouteRegistrar.get_included_resources(
                            request.args["include"].split(","),
                            f_obj
                        )
                        if errors:
                            return errors

                    return JSONAPIResponseFactory.make_data_response(
                        data, links=links, included_resources=included_resources, meta={"total-count": count}, **kwargs
                    )

                except (AttributeError, ValueError, OperationalError) as e:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 400, "details": str(e)}, status=400
                    )

        resource_relationship_endpoint.__name__ = "%s_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), rel_name.replace("-", "_"),
            resource_relationship_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(rule, endpoint=resource_relationship_endpoint.__name__,
                            view_func=resource_relationship_endpoint)

        # ===================================
        # Relationships related link route
        # ===================================
        rule = '/api/{api_version}/{type_plural}/<id>/{rel_name}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL, rel_name=rel_name
        )
        print(rule)
        def resource_endpoint(id):
            """
                - Related resource inclusion :
                    ?include=relationname1,relationname2
                Support Pagination syntax :
                - Pagination syntax requires page[number], page[size] or both parameters to be supplied in the URL:
                  page[number]=1&page[size]=100
                  The size cannot be greater than the limit defined in the corresponding Facade class
                  If the page size is omitted, it is set to its default value (defined in the Facade class)
                  If the page number is omitted, it is set to 1
                  Provide self,first,last,prev,next links for the collection (top-level)
                  Omit the prev link if the current page is the first one, omit the next link if it is the last one
            """
            url_prefix = request.host_url[:-1] + self.url_prefix
            f_obj, kwargs, errors = facade_class.get_resource_facade(url_prefix, id)
            if f_obj is None:
                return JSONAPIResponseFactory.make_errors_response(errors, **kwargs)
            else:
                relationship = f_obj.relationships[rel_name]
                resource_data = relationship["resource_getter"]()
                if resource_data is None:
                    count = 0
                else:
                    if isinstance(resource_data, dict):
                        count = 1
                    else:
                        count = len(resource_data)
                paginated_links = {}
                links = {
                    "self": request.url
                }
                try:
                    # if request has pagination parameters
                    # add links to the top-level object
                    if 'page[number]' in request.args or 'page[size]' in request.args:
                        num_page = int(request.args.get('page[number]', 1))
                        page_size = min(
                            facade_class.ITEMS_PER_PAGE,
                            int(request.args.get('page[size]', facade_class.ITEMS_PER_PAGE))
                        )

                        args = OrderedDict(request.args)
                        nb_pages = max(1, ceil(count / page_size))

                        args["page[size]"] = page_size
                        paginated_links["self"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        args["page[number]"] = 1
                        paginated_links["first"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        args["page[number]"] = nb_pages
                        paginated_links["last"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        if num_page > 1:
                            n = max(1, num_page - 1)
                            if n * page_size <= count:
                                args["page[number]"] = max(1, num_page - 1)
                                paginated_links["prev"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)
                        if num_page < nb_pages:
                            args["page[number]"] = min(nb_pages, num_page + 1)
                            paginated_links["next"] = JSONAPIRouteRegistrar.make_url(request.base_url, args)

                        # perform the pagination
                        resource_data = resource_data[(num_page - 1) * page_size:min(num_page * page_size, count)]
                        links.update(paginated_links)

                    # try to include related resources if requested
                    included_resources = None
                    if "include" in request.args:
                        included_resources, errors = JSONAPIRouteRegistrar.get_included_resources(
                            request.args["include"].split(","),
                            f_obj
                        )
                        if errors:
                            return errors

                    return JSONAPIResponseFactory.make_data_response(
                        resource_data, links=links, included_resources=included_resources, meta={"total-count": count},
                    )

                except (AttributeError, ValueError, OperationalError) as e:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 400, "details": str(e)}, status=400
                    )

        resource_endpoint.__name__ = "%s_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), rel_name.replace("-", "_"), resource_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(rule, endpoint=resource_endpoint.__name__, view_func=resource_endpoint)

    def register_post_routes(self, model, facade_class):
        """

        :param model:
        :param facade_class:
        :return:
        """

        collection_obj_rule = '/api/{api_version}/{type_plural}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL
        )

        def collection_endpoint():
            try:
                request_data = json_loads(request.data)
            except json.decoder.JSONDecodeError as e:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "The request body is malformed", "details" : str(e)}, status=403
                )

            if "data" not in request_data:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "Missing 'data' section" % request.data}, status=403
                )
            else:
                # let's check the request body
                if "type" not in request_data["data"]:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 403, "title": "Missing 'type' attribute"}, status=403
                    )

                if request_data["data"]["type"] != facade_class.TYPE:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 403, "title": "Wrong resource type"}, status=403
                    )

                d = request_data["data"]
                obj_id = d["id"] if "id" in d else None
                if obj_id is None:
                    # autoinc at the db level
                    pass
                else:
                    # check the client generated ID is OK else MUST fail here
                    already_exists = model.query.filter(model.id == obj_id).first() is not None
                    if already_exists:
                        return JSONAPIResponseFactory.make_errors_response(
                            {"status": 409,
                             "title": "The provided ID is conflicting with an already existing resource"},
                            status=409
                        )

                attributes = d["attributes"] if "attributes" in d else {}
                relationships = d["relationships"] if "relationships" in d else {}

                # Test if the relationships are correctly formed and the if the related resources exist
                related_resources = {}
                for rel_name, rel in relationships.items():
                    related_resources[rel_name] = []

                    if not rel or "data" not in rel:
                        return JSONAPIResponseFactory.make_errors_response(
                            {"status": 403,
                             "title": "Section 'data' is missing from relationship '%s'" % rel_name},
                            status=403
                        )
                    elif not rel["data"]:
                        # if rel data is null then just skip this relationships
                        continue

                    if not isinstance(rel["data"], list):
                        rel_data = [rel["data"]]
                    else:
                        rel_data = rel["data"]

                    for rel_item in rel_data:

                        if "type" not in rel_item:
                            return JSONAPIResponseFactory.make_errors_response(
                                {"status": 403,
                                 "title": "Attribute 'type' is missing from an item of the relationship '%s'" % rel_name},
                                status=403
                            )

                        # In a relationship, you cant reference a resource which does not exist yet
                        if "id" not in rel_item:
                            return JSONAPIResponseFactory.make_errors_response(
                                {"status": 403,
                                 "title": "Attribute 'id' is missing from an item of the relationship '%s'" % rel_name},
                                status=403
                            )
                        else:
                            related_resource, errors = self.get_obj_from_resource_identifier(rel_item)
                            if related_resource is None:
                                e = {
                                        "status": 404,
                                        "title": "Relationship '%s' references a resource"
                                                   " '%s' which does not exist" % (rel_name, rel_item)
                                    }
                                if errors:
                                    e = [e, errors]
                                return JSONAPIResponseFactory.make_errors_response(e, status=404)
                            else:
                                related_resources[rel_name].append(related_resource)

                # =====================================
                #  Create the resource from its facade
                # =====================================
                resource, e = facade_class.create_resource(model, obj_id, attributes, related_resources)
                if e is None:
                    url_prefix = request.host_url[:-1] + self.url_prefix

                    f_obj = facade_class(url_prefix, resource, with_relationships_links=True,
                                         with_relationships_data=True)
                    # RESPOND 201 CREATED
                    if "links" in f_obj.resource and "self" in f_obj.resource["links"]:
                        headers = {"Location": f_obj.resource["links"]["self"]}
                    else:
                        headers = {}
                    meta = {"search-fields": getattr(model, "__searchable__", []), "total-count": 1}
                    return JSONAPIResponseFactory.make_data_response(f_obj.resource, None, None, meta=meta,
                                                                     status=201,
                                                                     headers=headers)
                else:
                    return JSONAPIResponseFactory.make_errors_response(e)

        collection_endpoint.__name__ = "post_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), collection_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(collection_obj_rule, endpoint=collection_endpoint.__name__, view_func=collection_endpoint,
                            methods=["POST"])

    def register_relationship_post_route(self, facade_class, rel_name):

        # ===============================
        # Relationships route
        # ===============================
        rule = '/api/{api_version}/{type_plural}/<id>/relationships/{rel_name}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL, rel_name=rel_name
        )

        def resource_relationship_endpoint(id):
            try:
                request_data = json_loads(request.data)

            except json.decoder.JSONDecodeError as e:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "The request body is malformed", "details": str(e)}, status=403
                )

            if "data" not in request_data:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "Missing 'data' section" % request.data}, status=403
                )
            else:
                if not isinstance(request_data["data"], list):
                    request_data = [request_data["data"]]
                else:
                    request_data = request_data["data"]

                related_resources = {rel_name: []}
                for rdi in request_data:
                    related_resource, errors = self.get_obj_from_resource_identifier(rdi)
                    if errors:
                        return JSONAPIResponseFactory.make_errors_response(errors, status=403)

                    if related_resource is None:
                        return JSONAPIResponseFactory.make_errors_response(
                            {"status": 404, "title": "Resource %s does not exist" % rdi}, status=404
                        )
                    related_resources[rel_name].append(related_resource)

                # ==============================
                # post the relationships links
                # ==============================
                model = self.models[facade_class.TYPE]
                obj = model.query.filter(model.id == id).first()
                resource, e = facade_class.update_resource(obj, facade_class.TYPE, {}, related_resources, append=True)
                if e is None:
                    url_prefix = request.host_url[:-1] + self.url_prefix

                    f_obj = facade_class(url_prefix, resource, with_relationships_links=True,
                                         with_relationships_data=True)
                    # RESPOND 200
                    if "links" in f_obj.resource and "self" in f_obj.resource["links"]:
                        headers = {"Location": f_obj.resource["links"]["self"]}
                    else:
                        headers = {}
                    meta = {"search-fields": getattr(model, "__searchable__", []), "total-count": 1}
                    return JSONAPIResponseFactory.make_data_response(f_obj.resource, None, None, meta=meta,
                                                                     status=200,
                                                                     headers=headers)
                else:
                    return JSONAPIResponseFactory.make_errors_response(e)

        resource_relationship_endpoint.__name__ = "post_%s_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), rel_name.replace("-", "_"),
            resource_relationship_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(
            rule,
            endpoint=resource_relationship_endpoint.__name__,
            view_func=resource_relationship_endpoint,
            methods=["POST"]
        )

    def register_patch_routes(self, model, facade_class):
        """

        :param model:
        :param facade_class:
        :return:
        """

        single_obj_rule = '/api/{api_version}/{type_plural}/<id>'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL
        )

        def single_obj_endpoint(id):
            try:
                request_data = json_loads(request.data)
            except json.decoder.JSONDecodeError as e:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "The request body is malformed", "details": str(e)}, status=403
                )

            if "data" not in request_data:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "Missing 'data' section" % request.data}, status=403
                )
            else:
                # let's check the request body
                if "type" not in request_data["data"]:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 403, "title": "Missing 'type' attribute"}, status=403
                    )

                # let's check the request body
                if "id" not in request_data["data"]:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 403, "title": "Missing 'id' attribute"}, status=403
                    )

                if request_data["data"]["type"] != facade_class.TYPE:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 403, "title": "Wrong resource type"}, status=403
                    )

                d = request_data["data"]

                obj = model.query.filter(model.id == id).first()
                if obj is None:
                    return JSONAPIResponseFactory.make_errors_response(
                        {"status": 404,
                         "title": "The resource '%s' with ID '%s' does not exist" % (facade_class.TYPE, id)},
                        status=404
                    )

                attributes = d["attributes"] if "attributes" in d else {}
                relationships = d["relationships"] if "relationships" in d else {}

                # Test if the relationships are correctly formed and the if the related resources exist
                related_resources = {}
                for rel_name, rel in relationships.items():
                    related_resources[rel_name] = []

                    if not rel or "data" not in rel:
                        return JSONAPIResponseFactory.make_errors_response(
                            {"status": 403,
                             "title": "Section 'data' is missing from relationship '%s'" % rel_name},
                            status=403
                        )
                    elif not rel["data"]:
                        related_resources[rel_name] = None
                        continue

                    if not isinstance(rel["data"], list):
                        rel_data = [rel["data"]]
                    else:
                        rel_data = rel["data"]

                    for rel_item in rel_data:

                        if "type" not in rel_item:
                            return JSONAPIResponseFactory.make_errors_response(
                                {"status": 403,
                                 "title": "Attribute 'type' is missing from an item of the relationship '%s'" % rel_name},
                                status=403
                            )

                        # In a relationship, you cant reference a resource which does not exist yet
                        if "id" not in rel_item:
                            return JSONAPIResponseFactory.make_errors_response(
                                {"status": 403,
                                 "title": "Attribute 'id' is missing from an item of the relationship '%s'" % rel_name},
                                status=403
                            )
                        else:
                            related_resource, errors = self.get_obj_from_resource_identifier(rel_item)
                            if related_resource is None:
                                e = {
                                        "status": 404,
                                        "title": "Relationship '%s' references a resource"
                                                   " '%s' which does not exist" % (rel_name, rel_item)
                                    }
                                if errors:
                                    e = [e, errors]
                                return JSONAPIResponseFactory.make_errors_response(e, status=404)
                            else:
                                related_resources[rel_name].append(related_resource)

                # =====================================
                #  Update the resource from its facade
                # =====================================
                resource, e = facade_class.update_resource(obj, facade_class.TYPE, attributes, related_resources)
                if e is None:
                    url_prefix = request.host_url[:-1] + self.url_prefix

                    f_obj = facade_class(url_prefix, resource, with_relationships_links=True,
                                         with_relationships_data=True)
                    # RESPOND 200
                    if "links" in f_obj.resource and "self" in f_obj.resource["links"]:
                        headers = {"Location": f_obj.resource["links"]["self"]}
                    else:
                        headers = {}
                    meta = {"search-fields": getattr(model, "__searchable__", []), "total-count": 1}
                    return JSONAPIResponseFactory.make_data_response(f_obj.resource, None, None, meta=meta,
                                                                     status=200,
                                                                     headers=headers)
                else:
                    return JSONAPIResponseFactory.make_errors_response(e)

        single_obj_endpoint.__name__ = "post_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), single_obj_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(single_obj_rule, endpoint=single_obj_endpoint.__name__, view_func=single_obj_endpoint,
                            methods=["PATCH"])

    def register_relationship_patch_route(self, facade_class, rel_name):

        # ===============================
        # Relationships route
        # ===============================
        rule = '/api/{api_version}/{type_plural}/<id>/relationships/{rel_name}'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL, rel_name=rel_name
        )

        def resource_relationship_endpoint(id):
            try:
                request_data = json_loads(request.data)

            except json.decoder.JSONDecodeError as e:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "The request body is malformed", "details" : str(e)}, status=403
                )

            if "data" not in request_data:
                return JSONAPIResponseFactory.make_errors_response(
                    {"status": 403, "title": "Missing 'data' section" % request.data}, status=403
                )
            else:
                if not isinstance(request_data["data"], list):
                    request_data = [request_data["data"]]
                else:
                    request_data = request_data["data"]

                related_resources = {rel_name: []}
                for rdi in request_data:
                    if rdi is None:
                        related_resources[rel_name].append(None)
                    else:
                        related_resource, errors = self.get_obj_from_resource_identifier(rdi)
                        if errors:
                            return JSONAPIResponseFactory.make_errors_response(errors, status=403)

                        if related_resource is None:
                            return JSONAPIResponseFactory.make_errors_response(
                                {"status": 404, "title": "Resource %s does not exist" % rdi}, status=404
                            )
                        related_resources[rel_name].append(related_resource)

                # ==============================
                # patch the relationships links
                # ==============================
                model = self.models[facade_class.TYPE]
                obj = model.query.filter(model.id == id).first()
                resource, e = facade_class.update_resource(obj, facade_class.TYPE, {}, related_resources, append=False)
                if e is None:
                    url_prefix = request.host_url[:-1] + self.url_prefix

                    f_obj = facade_class(url_prefix, resource, with_relationships_links=True,
                                         with_relationships_data=True)
                    # RESPOND 200
                    if "links" in f_obj.resource and "self" in f_obj.resource["links"]:
                        headers = {"Location": f_obj.resource["links"]["self"]}
                    else:
                        headers = {}
                    meta = {"search-fields": getattr(model, "__searchable__", []), "total-count": 1}
                    return JSONAPIResponseFactory.make_data_response(f_obj.resource, None, None, meta=meta,
                                                                     status=200,
                                                                     headers=headers)
                else:
                    return JSONAPIResponseFactory.make_errors_response(e)

        resource_relationship_endpoint.__name__ = "patch_%s_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), rel_name.replace("-", "_"),
            resource_relationship_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(
            rule,
            endpoint=resource_relationship_endpoint.__name__,
            view_func=resource_relationship_endpoint,
            methods=["PATCH"]
        )

    def register_delete_routes(self, model, facade_class):
        """

        :param model:
        :param facade_class:
        :return:
        """

        single_obj_rule = '/api/{api_version}/{type_plural}/<id>'.format(
            api_version=self.api_version,
            type_plural=facade_class.TYPE_PLURAL
        )

        def single_obj_endpoint(id):
            rdi = facade_class.make_resource_identifier(id, facade_class.TYPE)
            obj, errors = self.get_obj_from_resource_identifier(rdi)

            if errors is not None:
                return JSONAPIResponseFactory.make_errors_response({
                    "status": 404,
                    "title": "This resource does not exist"},
                    status=404
                )

            #======================
            # Delete the resource
            # =====================
            errors = facade_class.delete_resource(obj)
            if errors is not None:
                return JSONAPIResponseFactory.make_errors_response(errors, status=404)

            return JSONAPIResponseFactory.make_data_response(None, None, None, None, status=204)

        single_obj_endpoint.__name__ = "delete_%s_%s" % (
            facade_class.TYPE_PLURAL.replace("-", "_"), single_obj_endpoint.__name__
        )
        # register the rule
        api_bp.add_url_rule(single_obj_rule, endpoint=single_obj_endpoint.__name__, view_func=single_obj_endpoint,
                            methods=["DELETE"])