import logging
import markdown
from rdflib import Graph, URIRef
from flask import (
    Flask,
    Response,
    request,
    render_template,
    Markup,
    g,
    redirect,
    url_for,
    jsonify,
)
from config import *
from pyldapi import Renderer, ContainerRenderer
from model.zone import ZoneRenderer
from model.dataset import DatasetRenderer

from utils import make_cached_graph, calculate_neighbours, get_collections

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)


@app.before_request
def before_request():
    """
    Runs before every request and populates vocab index either from disk (VOCABS.p) or from a complete reload by
    calling collect() for each of the vocab sources defined in config/__init__.py -> VOCAB_SOURCES
    :return: nothing
    """
    # check to see if g.DATA exists, if so, do nothing
    if hasattr(g, "DATA"):
        return
    else:
        g.DATA = make_cached_graph()


@app.context_processor
def context_processor():
    """
    A set of variables available globally for all Jinja templates.
    :return: A dictionary of variables
    :rtype: dict
    """
    MEDIATYPE_NAMES = {
        "text/html": "HTML",
        "application/json": "JSON",
        "text/turtle": "Turtle",
        "application/rdf+xml": "RDX/XML",
        "application/ld+json": "JSON-LD",
        "text/n3": "Notation-3",
        "application/n-triples": "N-Triples",
    }

    return dict(
        LOCAL_URIS=LOCAL_URIS,
        MEDIATYPE_NAMES=MEDIATYPE_NAMES,
    )


@app.route("/")
def landing_page():
    return DatasetRenderer(request).render()


@app.route("/conformance")
def conformance():
    return render_template("conformance.html")


@app.route("/collections")
def collections():
    collections = get_collections()
    return ContainerRenderer(
        request,
        "https://w3id.org/dggs/tb16pix/resolution/",
        "Grids",
        "DGGs are made of hierarchical layers of cells. In TB16Pix, these layers are called Grids",
        "https://w3id.org/dggs/tb16pix",
        "TB16Pix Dataset",
        collections,
        len(collections)
    ).render()


@app.route("/collections/<string:collection_id>")
def collection(collection_id):
    if int(collection_id[-1]) not in range(10):
        return render_api_error(
            "Invalid Collection ID",
            400,
            "The Collection ID must be one of 'level{}'".format("', 'level".join([str(x) for x in range(10)]))
        )
    return render_template(
        "collection.html",
        collection_id=collection_id,
        collection_name="Grid " + str(collection_id)
    )


@app.route("/collections/<string:collection_id>/items")
def items(collection_id):
    features = []
    for cell in TB16Pix.grid(int(collection_id[-1])):
        if LOCAL_URIS:
            features.append((
                url_for("item", collection_id=collection_id, item_id=str(cell)),
                "Zone {}".format(str(cell))
            ))
        else:
            features.append((
                URI_BASE_ZONE[str(cell)],
                "Zone {}".format(str(cell))
            ))

    return render_template(
        "items.html",
        collection_name="Grid " + str(collection_id),
        items=features
    )


@app.route("/collections/<string:collection_id>/items/<string:item_id>")
def item(collection_id, item_id):
    return ZoneRenderer(request, item_id).render()


@app.route("/object")
def object():
    """Resolves Linked Data URIs for TB16Pix objects"""

    if request.values.get("uri") is None:
        return render_api_error(
            "No URI supplied",
            400,
            "You must supply a TB16Pix URI with the parameter ?uri= for this endpoint"
        )
    elif request.values.get("uri") == "https://w3id.org/dggs/tb16pix":
        return redirect(url_for("landing_page"))
    elif request.values.get("uri") == str(URI_BASE_ZONE.Earth):
        local = Graph()
        local.bind("dggs", DGGS)
        for s, p, o in g.DATA.triples((URIRef(request.values.get("uri")), None, None)):
            local.add((s, p, o))
        return Response(
            local.serialize(format="turtle").decode(),
            status=200,
            mimetype="text/plain"
        )
    elif request.values.get("uri") == URI_BASE_RESOLUTION:
        return redirect(url_for("collections"))
    elif request.values.get("uri").endswith("/cell/"):
        # https://w3id.org/dggs/tb16pix/resolution/2/cell/
        resolution = request.values.get("uri").split("/")[-3]
        return redirect(url_for("items", collection_id=resolution))
    elif request.values.get("uri").startswith(URI_BASE_RESOLUTION):
        resolution = request.values.get("uri").split("/")[-1]
        return redirect(url_for("collection", collection_id=resolution))
    elif request.values.get("uri").startswith(URI_BASE_ZONE):
        cell_id = request.values.get("uri").split("/")[-1]
        resolution = "resolution-" + str(len(cell_id) - 1)
        return redirect(url_for("item", collection_id=resolution, item_id=cell_id))
    else:
        return render_api_error(
            "URI not known",
            404,
            "The URI you supplied is not recognised within the TB16Pix dataset"
        )


@app.route("/about")
def about():
    import os
    # using basic Markdown method from http://flask.pocoo.org/snippets/19/
    README_FILE = os.path.join(APP_DIR, "README.md")
    with open(README_FILE) as f:
        content = f.read()

    # make images come from web dir
    content = content.replace(
        "catprez/view/style/", request.url_root + "style/"
    )
    contents = Markup(markdown.markdown(content))

    return render_template(
        "about.html",
        title="About",
        contents=contents
    )


# the SPARQL UI
@app.route("/sparql", methods=["GET", "POST"])
def sparql():
    return render_template(
        "sparql.html",
    )


# the SPARQL endpoint under-the-hood
@app.route("/endpoint", methods=["GET", "POST"])
def endpoint():
    """
    TESTS

    Form POST:
    curl -X POST -d query="PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0ASELECT%20*%20WHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%20.%7D" http://localhost:5000/endpoint

    Raw POST:
    curl -X POST -H 'Content-Type: application/sparql-query' --data-binary @query.sparql http://localhost:5000/endpoint
    using query.sparql:
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT * WHERE {?s a skos:ConceptScheme .}

    GET:
    curl http://localhost:5000/endpoint?query=PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0ASELECT%20*%20WHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%20.%7D

    GET CONSTRUCT:
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        CONSTRUCT {?s a rdf:Resource}
        WHERE {?s a skos:ConceptScheme}
    curl -H 'Accept: application/ld+json' http://localhost:5000/endpoint?query=PREFIX%20rdf%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%3E%0APREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fco23%3E%0ACONSTRUCT%20%7B%3Fs%20a%20rdf%3AResource%7D%0AWHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%7D

    """
    logging.debug("request: {}".format(request.__dict__))

    # TODO: Find a slightly less hacky way of getting the format_mimetime value
    format_mimetype = request.__dict__["environ"]["HTTP_ACCEPT"]

    # Query submitted
    if request.method == "POST":
        """Pass on the SPARQL query to the underlying endpoint defined in config
        """
        if "application/x-www-form-urlencoded" in request.content_type:
            """
            https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-post-urlencoded

            2.1.2 query via POST with URL-encoded parameters

            Protocol clients may send protocol requests via the HTTP POST method by URL encoding the parameters. When
            using this method, clients must URL percent encode all parameters and include them as parameters within the
            request body via the application/x-www-form-urlencoded media type with the name given above. Parameters must
            be separated with the ampersand (&) character. Clients may include the parameters in any order. The content
            type header of the HTTP request must be set to application/x-www-form-urlencoded.
            """
            if (
                    request.values.get("query") is None
                    or len(request.values.get("query")) < 5
            ):
                return Response(
                    "Your POST request to the SPARQL endpoint must contain a 'query' parameter if form posting "
                    "is used.",
                    status=400,
                    mimetype="text/plain",
                )
            else:
                query = request.values.get("query")
        elif "application/sparql-query" in request.content_type:
            """
            https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-post-direct

            2.1.3 query via POST directly

            Protocol clients may send protocol requests via the HTTP POST method by including the query directly and
            unencoded as the HTTP request message body. When using this approach, clients must include the SPARQL query
            string, unencoded, and nothing else as the message body of the request. Clients must set the content type
            header of the HTTP request to application/sparql-query. Clients may include the optional default-graph-uri
            and named-graph-uri parameters as HTTP query string parameters in the request URI. Note that UTF-8 is the
            only valid charset here.
            """
            query = request.data.decode("utf-8")  # get the raw request
            if query is None:
                return Response(
                    "Your POST request to this SPARQL endpoint must contain the query in plain text in the "
                    "POST body if the Content-Type 'application/sparql-query' is used.",
                    status=400,
                )
        else:
            return Response(
                "Your POST request to this SPARQL endpoint must either the 'application/x-www-form-urlencoded' or"
                "'application/sparql-query' ContentType.",
                status=400,
            )

        try:
            if "CONSTRUCT" in query:
                format_mimetype = "text/turtle"
                return Response(
                    sparql_query2(
                        query, format_mimetype=format_mimetype
                    ),
                    status=200,
                    mimetype=format_mimetype,
                )
            else:
                return Response(
                    sparql_query2(query, format_mimetype),
                    status=200,
                )
        except ValueError as e:
            return Response(
                "Input error for query {}.\n\nError message: {}".format(query, str(e)),
                status=400,
                mimetype="text/plain",
            )
        except ConnectionError as e:
            return Response(str(e), status=500)
    else:  # GET
        if request.args.get("query") is not None:
            # SPARQL GET request
            """
            https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-get

            2.1.1 query via GET

            Protocol clients may send protocol requests via the HTTP GET method. When using the GET method, clients must
            URL percent encode all parameters and include them as query parameter strings with the names given above.

            HTTP query string parameters must be separated with the ampersand (&) character. Clients may include the
            query string parameters in any order.

            The HTTP request MUST NOT include a message body.
            """
            query = request.args.get("query")
            if "CONSTRUCT" in query:
                acceptable_mimes = [x for x in Renderer.RDF_MEDIA_TYPES]
                best = request.accept_mimetypes.best_match(acceptable_mimes)
                query_result = sparql_query2(
                    query, format_mimetype=best
                )
                file_ext = {
                    "text/turtle": "ttl",
                    "application/rdf+xml": "rdf",
                    "application/ld+json": "json",
                    "text/n3": "n3",
                    "application/n-triples": "nt",
                }
                return Response(
                    query_result,
                    status=200,
                    mimetype=best,
                    headers={
                        "Content-Disposition": "attachment; filename=query_result.{}".format(
                            file_ext[best]
                        )
                    },
                )
            else:
                query_result = sparql_query2(query)
                return Response(
                    query_result, status=200, mimetype="application/sparql-results+json"
                )
        else:
            # SPARQL Service Description
            """
            https://www.w3.org/TR/sparql11-service-description/#accessing

            SPARQL services made available via the SPARQL Protocol should return a service description document at the
            service endpoint when dereferenced using the HTTP GET operation without any query parameter strings
            provided. This service description must be made available in an RDF serialization, may be embedded in
            (X)HTML by way of RDFa, and should use content negotiation if available in other RDF representations.
            """

            acceptable_mimes = [x for x in Renderer.RDF_MEDIA_TYPES] + ["text/html"]
            best = request.accept_mimetypes.best_match(acceptable_mimes)
            if best == "text/html":
                # show the SPARQL query form
                return redirect(url_for("sparql"))
            elif best is not None:
                for item in Renderer.RDF_MEDIA_TYPES:
                    if item == best:
                        rdf_format = best
                        return Response(
                            get_sparql_service_description(
                                rdf_format=rdf_format
                            ),
                            status=200,
                            mimetype=best,
                        )

                return Response(
                    "Accept header must be one of " + ", ".join(acceptable_mimes) + ".",
                    status=400,
                )
            else:
                return Response(
                    "Accept header must be one of " + ", ".join(acceptable_mimes) + ".",
                    status=400,
                )


def get_sparql_service_description(rdf_format="turtle"):
    """Return an RDF description of PROMS' read only SPARQL endpoint in a requested format

    :param rdf_format: 'turtle', 'n3', 'xml', 'json-ld'
    :return: string of RDF in the requested format
    """
    sd_ttl = """
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sd:     <http://www.w3.org/ns/sparql-service-description#> .
        @prefix sdf:    <http://www.w3.org/ns/formats/> .
        @prefix void: <http://rdfs.org/ns/void#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        <http://gnafld.net/sparql>
            a                       sd:Service ;
            sd:endpoint             <%(BASE_URI)s/function/sparql> ;
            sd:supportedLanguage    sd:SPARQL11Query ; # yes, read only, sorry!
            sd:resultFormat         sdf:SPARQL_Results_JSON ;  # yes, we only deliver JSON results, sorry!
            sd:feature sd:DereferencesURIs ;
            sd:defaultDataset [
                a sd:Dataset ;
                sd:defaultGraph [
                    a sd:Graph ;
                    void:triples "100"^^xsd:integer
                ]
            ]
        .
    """
    g = Graph().parse(io.StringIO(sd_ttl), format="turtle")
    rdf_formats = list(set([x for x in Renderer.RDF_SERIALIZER_TYPES_MAP]))
    if rdf_format[0][1] in rdf_formats:
        return g.serialize(format=rdf_format[0][1])
    else:
        raise ValueError(
            "Input parameter rdf_format must be one of: " + ", ".join(rdf_formats)
        )


def sparql_query2(query, format_mimetype="application/json"):
    """ Make a SPARQL query"""
    logging.debug("sparql_query2: {}".format(query))
    data = query

    headers = {
        "Content-Type": "application/sparql-query",
        "Accept": format_mimetype,
        "Accept-Encoding": "UTF-8",
    }
    if app.config.get("SPARQL_USERNAME") and app.config.get("SPARQL_PASSWORD"):
        auth = (app.config.get("SPARQL_USERNAME"), app.config.get("SPARQL_PASSWORD"))
    else:
        auth = None

    try:
        logging.debug(
            "endpoint={}\ndata={}\nheaders={}".format(
                app.config.get("SPARQL_ENDPOINT"), data, headers
            )
        )
        r = requests.post(
            app.config.get("SPARQL_ENDPOINT"), auth=auth, data=data, headers=headers, timeout=60
        )
        logging.debug("response: {}".format(r.__dict__))
        return r.content.decode("utf-8")
    except Exception as e:
        raise e


# TODO: use for all errors
# TODO: allow conneg - at least text v. HTML
def render_api_error(title, status, message, mediatype="text/html"):
    if mediatype == "application/json":
        return jsonify({
            "title": title,
            "status": status,
            "message": message
        }), status
    elif mediatype in Renderer.RDF_MEDIA_TYPES:
        pass
    else:  # mediatype == "text/html":
        return render_template(
            "error.html",
            title=title,
            status=status,
            message=message
        ), status


def render_invalid_object_class_response(uri):
    msg = """No valid *Object Class URI* found for object of URI <{}>.""".format(uri)
    msg = Markup(markdown.markdown(msg))
    return render_template(
        "error.html",
        title="Error - Object Class URI",
        heading="Concept Class Type Error",
        msg=msg,
    )


# run the Flask app
if __name__ == "__main__":
    logging.basicConfig(
        filename=LOGFILE,
        level=logging.DEBUG,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s",
    )

    app.run(debug=DEBUG, threaded=True, port=PORT)
