from flask import Response, render_template
from rdflib import Graph, URIRef, Literal, RDF, RDFS, BNode
from .profiles import *
from config import *
from utils import calculate_neighbours


class Cell:
    def __init__(
        self,
        cell_id
    ):
        self.uri = URI_BASE_CELL[cell_id]
        self.label = "Cell {}".format(cell_id)
        self.neighbours = [(URI_BASE_CELL[x[1]], x[1], x[0]) for x in calculate_neighbours(cell_id)]
        self.isPartOf = URI_BASE_RESOLUTION[str(len(cell_id) - 1)]


class CellRenderer(Renderer):
    def __init__(self, request, cell_id):
        self.cell = Cell(cell_id)
        self.profiles = {"dggs": profile_dggs}

        super().__init__(request, self.cell.uri, self.profiles, "dggs")

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
        item_uri = URIRef(self.cell.uri)
        item_id = self.cell.uri.split("/")[-1]
        item_graph.add((item_uri, RDF.type, DGGS.Cell))
        item_graph.add((item_uri, RDFS.label, Literal("Cell {}".format(item_id))))

        for neighbour in calculate_neighbours(item_id):
            direction_uri = URIRef(URI_BASE_DATASET[neighbour[0].title()])
            neighbour_uri = URIRef(URI_BASE_CELL[neighbour[1]])
            bn = BNode()
            item_graph.add((bn, DGGS.neighbour, neighbour_uri))
            item_graph.add((bn, DGGS.direction, direction_uri))
            item_graph.add((item_uri, DGGS.directionalisedNeighbour, bn))

        # serialise in the appropriate RDF format
        if self.mediatype in ["application/rdf+json", "application/json"]:
            return Response(item_graph.serialize(format="json-ld"), mimetype=self.mediatype)
        else:
            return Response(item_graph.serialize(format=self.mediatype), mimetype=self.mediatype)

    def _render_dggs_html(self):
        _template_context = {
            "uri": self.cell.uri,
            "label": self.cell.label,
            "neighbours": self.cell.neighbours,
            "isPartOf": self.cell.isPartOf,
        }

        return Response(
            render_template("cell.html", **_template_context),
            headers=self.headers,
        )
