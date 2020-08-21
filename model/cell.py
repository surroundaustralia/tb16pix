from flask import Response, render_template
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import DCTERMS, RDF, RDFS
from .profiles import *
from config import *


class Cell:
    def __init__(
        self,
        cell_id
    ):
        self.uri = URI_BASE_CELL[cell_id]
        self.label = "Cell {}".format(cell_id)
        self.isPartOf = URI_BASE_GRID[str(len(cell_id) - 1)], "Grid {}".format(str(len(cell_id) - 1))
        self.asDGGS = "<https://w3id.org/dggs/tb16pix> {}".format(cell_id)
        self.isGeometryOf = URI_BASE_ZONE[cell_id], "Zone {}".format(cell_id)


class CellRenderer(Renderer):
    def __init__(self, request, cell_id):
        self.zone = Cell(cell_id)
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
        item_graph.add((item_uri, RDF.type, DGGS.Cell))
        item_graph.add((item_uri, RDFS.label, Literal("Cell {}".format(item_id))))
        item_graph.add((
            item_uri,
            GEOX.asDGGS,
            Literal("<https://w3id.org/dggs/tb16pix> {}".format(item_id), datatype=GEOX.dggsLiteral)
        ))

        item_graph.add((item_uri, DCTERMS.isPartOf, URIRef(self.zone.isPartOf[0])))

        item_graph.add((item_uri, GEOX.isGeometryOf, URIRef(self.zone.isGeometryOf[0])))

        # serialise in the appropriate RDF format
        if self.mediatype in ["application/rdf+json", "application/json"]:
            return Response(item_graph.serialize(format="json-ld"), mimetype=self.mediatype)
        else:
            return Response(item_graph.serialize(format=self.mediatype), mimetype=self.mediatype)

    def _render_dggs_html(self):
        _template_context = {
            "uri": self.zone.uri,
            "label": self.zone.label,
            "isPartOf": self.zone.isPartOf,
            "asDGGS": self.zone.asDGGS,
            "isGeometryOf": self.zone.isGeometryOf
        }

        return Response(
            render_template("cell.html", **_template_context),
            headers=self.headers,
        )
