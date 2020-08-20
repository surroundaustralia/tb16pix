from flask import Response, render_template
from rdflib import Graph, URIRef, Literal, RDF, RDFS, BNode
from .profiles import *
from config import *
from utils import calculate_neighbours, calculate_children, calculate_parent


class Earth:
    def __init__(
        self,
        zone_id
    ):
        self.uri = URI_BASE_ZONE[zone_id]
        self.label = "Zone {}".format(zone_id)
        self.parent = None
        self.neighbours = []
        self.children = calculate_children(zone_id)


class EarthRenderer(Renderer):
    def __init__(self, request, zone_id):
        self.zone = Earth(zone_id)
        self.profiles = {"dggs": profile_dggs}
        super().__init__(request, self.zone.uri, self.profiles, "dggs")

    def render(self):
        # try returning alt profile
        response = super().render()
        if response is not None:
            return response
        elif self.profile == "dggs":
            if self.mediatype in Renderer.RDF_SERIALIZER_TYPES_MAP:
                return self._render_dggs_rdf()
            else:
                return self._render_dggs_html()

    def _render_dggs_rdf(self):
        item_graph = Graph()
        item_graph.bind("dggs", DGGS)
        GEO = Namespace("http://www.opengis.net/ont/geosparql#")
        item_graph.bind("geo", GEO)
        GEOX = Namespace("https://linked.data.gov.au/def/geox#")
        item_uri = URIRef(self.zone.uri)
        item_id = self.zone.uri.split("/")[-1]
        item_graph.add((item_uri, RDF.type, DGGS.Zone))
        item_graph.add((item_uri, RDFS.label, Literal("Zone {}".format(item_id))))

        for c in ["N", "O", "P", "Q", "R", "S"]:
            item_graph.add((item_uri, GEO.sfContains, URIRef(URI_BASE_ZONE + c)))

        item_graph.add((item_uri, GEO.hasDefaultGeometry, URIRef(URI_BASE_CELL[item_id])))

        # serialise in the appropriate RDF format
        if self.mediatype in ["application/rdf+json", "application/json"]:
            return Response(item_graph.serialize(format="json-ld"), mimetype=self.mediatype)
        else:
            return Response(item_graph.serialize(format=self.mediatype), mimetype=self.mediatype)

    def _render_dggs_html(self):
        _template_context = {
            "uri": self.zone.uri,
            "label": self.zone.label,
            "parent": self.zone.parent,
            "neighbours": self.zone.neighbours,
            "children": self.zone.children
        }

        return Response(
            render_template("earth.html", **_template_context),
            headers=self.headers,
        )
