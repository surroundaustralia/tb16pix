import logging
import markdown
from flask import (
    Flask,
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
from model import DatasetRenderer, EarthRenderer, ZoneRenderer, CellRenderer

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
        "https://w3id.org/dggs/tb16pix/grid/",
        "Collections",
        "DGGs are made of hierarchical layers of Cell geometries. In TB16Pix, these layers are called Grids. "
        "Additionally, this API delivers TB16Pix Zones in Collections too.",
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
                "Cell {}".format(str(cell))
            ))
        else:
            features.append((
                URI_BASE_CELL[str(cell)],
                "Cell {}".format(str(cell))
            ))

    return render_template(
        "items.html",
        collection_name="Grid " + str(collection_id),
        items=features
    )


@app.route("/collections/<string:collection_id>/items/<string:item_id>")
def item(collection_id, item_id):
    item_id = item_id.split("?")[0]
    if item_id == "Earth":
        return EarthRenderer(request, item_id).render()
    else:
        return CellRenderer(request, item_id).render()


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
        return EarthRenderer(request, "Earth").render()
    elif request.values.get("uri") == URI_BASE_GRID:
        return redirect(url_for("collections"))
    elif request.values.get("uri").endswith("/cell/"):
        # https://w3id.org/dggs/tb16pix/resolution/2/cell/
        resolution = request.values.get("uri").split("/")[-3]
        return redirect(url_for("items", collection_id=resolution))
    elif request.values.get("uri").startswith(URI_BASE_GRID):
        resolution = request.values.get("uri").split("/")[-1]
        return redirect(url_for("collection", collection_id=resolution))
    elif request.values.get("uri").startswith(URI_BASE_ZONE):
        cell_id = request.values.get("uri").split("/")[-1].split("?")[0]
        return ZoneRenderer(request, cell_id).render()
    elif request.values.get("uri").startswith(URI_BASE_CELL):
        zone_id = request.values.get("uri").split("/")[-1]
        resolution = "resolution-" + str(len(zone_id) - 1)
        return redirect(url_for("item", collection_id=resolution, item_id=zone_id))
        # cell_id = request.values.get("uri").split("/")[-1].split("?")[0]
        # return CellRenderer(request, cell_id).render()
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
    contents = Markup(markdown.markdown(content, extensions=['tables']))

    return render_template(
        "about.html",
        title="About",
        contents=contents
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
