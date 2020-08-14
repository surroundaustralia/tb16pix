from flask import Response, render_template
from rdflib import Graph, URIRef, Literal, RDF, RDFS, BNode
from .profiles import *
from config import *
from utils import calculate_neighbours, get_collections
import markdown


class Dataset:
    def __init__(
        self,
    ):
        self.uri = "https://w3id.org/dggs/tb16pix"
        self.label = "Testbed 16 Pix Discrete Global Grid"
        self.description = """This is an instance of the [Open Geospatial Consortium (OGC)](https://www.ogc.org/) 's "[OGC API - Features](http://www.opengis.net/doc/IS/ogcapi-features-1/1.0)" API that delivers the authoritative content for the *Testbed 16 Pix* (TB16Pix) which is a [Discreet Global Grid](http://docs.opengeospatial.org/as/15-104r5/15-104r5.html#4), that is, a multi-layered, tessellated, set of spatial grid cells used for position identification on the Earth's surface. 

This API and the data within it have been created for the OGC's Testbed 16 which is a multi-organisation interoperability experiment."""
        self.parts = get_collections()
        self.distributions = [
            (URI_BASE_DATASET.sparql, "SPARQL"),
            (URI_BASE_DATASET, "Linked Data API"),
        ]


class DatasetRenderer(Renderer):
    def __init__(self, request):
        self.dataset = Dataset()
        self.profiles = {
            "dcat": profile_dcat,
            "dggs": profile_dggs,
        }

        super().__init__(request, self.dataset.uri, self.profiles, "dcat")

    def render(self):
        # try returning alt profile
        response = super().render()
        if response is not None:
            return response
        elif self.profile == "dcat":
            if self.mediatype in Renderer.RDF_SERIALIZER_TYPES_MAP:
                return self._render_dcat_rdf()
            else:
                return self._render_dcat_html()

    def _render_dcat_rdf(self):
        item_graph = Graph()
        item_graph.bind("dggs", DGGS)
        item_uri = URIRef(self.dataset.uri)
        item_id = self.dataset.uri.split("/")[-1]
        item_graph.add((item_uri, RDF.type, DGGS.Zone))
        item_graph.add((item_uri, RDFS.label, Literal("Zone {}".format(item_id))))

        for neighbour in calculate_neighbours(item_id):
            direction_uri = URIRef(URI_BASE_DATASET[neighbour[0].title()])
            neighbour_uri = URIRef(URI_BASE_ZONE[neighbour[1]])
            bn = BNode()
            item_graph.add((bn, DGGS.neighbour, neighbour_uri))
            item_graph.add((bn, DGGS.direction, direction_uri))
            item_graph.add((item_uri, DGGS.directionalisedNeighbour, bn))

        # serialise in the appropriate RDF format
        if self.mediatype in ["application/rdf+json", "application/json"]:
            return Response(item_graph.serialize(format="json-ld"), mimetype=self.mediatype)
        else:
            return Response(item_graph.serialize(format=self.mediatype), mimetype=self.mediatype)

    def _render_dcat_html(self):
        _template_context = {
            "uri": self.dataset.uri,
            "label": self.dataset.label,
            "description": markdown.markdown(self.dataset.description),
            "parts": self.dataset.parts,
            "distributions": self.dataset.distributions,
        }

        return Response(
            render_template("dataset.html", **_template_context),
            headers=self.headers,
        )
