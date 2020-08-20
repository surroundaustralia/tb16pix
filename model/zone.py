from flask import Response, render_template
from rdflib import Graph, URIRef, Literal, RDF, RDFS, BNode
from .profiles import *
from config import *
from utils import calculate_neighbours, calculate_children, calculate_parent


class Zone:
    def __init__(
        self,
        zone_id
    ):
        self.uri = URI_BASE_ZONE[zone_id]
        self.label = "Zone {}".format(zone_id)
        self.parent = calculate_parent(zone_id)
        self.neighbours = [(URI_BASE_ZONE[x[1]], x[1], x[0]) for x in calculate_neighbours(zone_id)]
        self.children = calculate_children(zone_id)
        self.defaultGeometry = (URI_BASE_CELL[zone_id], "Cell " + zone_id)


class ZoneRenderer(Renderer):
    def __init__(self, request, zone_id):
        self.zone = Zone(zone_id)
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
        item_graph.bind("geox", GEOX)
        item_uri = URIRef(self.zone.uri)
        item_id = self.zone.uri.split("/")[-1]
        item_graph.add((item_uri, RDF.type, DGGS.Zone))
        item_graph.add((item_uri, RDFS.label, Literal("Zone {}".format(item_id))))

        item_graph.add((item_uri, GEO.sfWithin, URIRef(URI_BASE_ZONE[self.zone.parent[0]])))

        for neighbour in calculate_neighbours(item_id):
            direction_uri = URIRef(URI_BASE_DATASET[neighbour[0].title()])
            neighbour_uri = URIRef(URI_BASE_ZONE[neighbour[1]])
            bn = BNode()
            item_graph.add((bn, DGGS.neighbour, neighbour_uri))
            item_graph.add((bn, DGGS.direction, direction_uri))
            item_graph.add((item_uri, DGGS.directionalisedNeighbour, bn))

            item_graph.add((item_uri, GEO.sfTouches, URIRef(URI_BASE_ZONE[neighbour[1]])))

        for c in range(9):
            item_graph.add((item_uri, GEO.sfContains, URIRef(self.zone.uri + str(c))))

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
            "children": self.zone.children,
            "defaultGeometry": self.zone.defaultGeometry,
        }

        return Response(
            render_template("zone.html", **_template_context),
            headers=self.headers,
        )
