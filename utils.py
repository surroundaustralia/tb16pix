import pickle
from rdflib import Graph
from rdflib.namespace import RDF, RDFS
import glob
from os.path import join
from config import *
from rhealpixdggs.dggs import Cell


def calculate_level(zone_id):
    if zone_id == "Earth":
        return "Earth"
    else:
        return len(zone_id) - 1


def calculate_parent(zone_id):
    if zone_id == "Earth":
        return None
    elif len(zone_id) == 1:
        return URI_BASE_ZONE + "Earth", "Earth"
    else:  # <LETTER>...<LETTER><0-8>*9
        return URI_BASE_ZONE + zone_id[:-1], zone_id[:-1]


def calculate_children(zone_id):
    if zone_id == "Earth":
        return [(URI_BASE_ZONE + zone_id + str(n), zone_id + str(n)) for n in ["N", "O", "P", "Q", "R", "S"]]
    else:
        if len(zone_id) < 10:
            return [(URI_BASE_ZONE + zone_id + str(n), zone_id + str(n)) for n in range(8)]
        else:
            return None


def _suid_from_string(zone_id):
    if zone_id == "Earth":
        return "Earth"
    else:
        if len(zone_id) == 1:
            return [zone_id[0]]
        else:
            return [zone_id[0]] + [int(x) for x in zone_id[1:]]


def calculate_neighbours(zone_id):
    if zone_id == "Earth":
        return None
    else:
        c = Cell(TB16Pix, _suid_from_string(zone_id))
        neighbours = []
        for k, v in sorted(c.neighbors().items()):
            neighbours.append((k, str(v)))
        return neighbours


def _load_graph_from_pickle(pickle_file_path):
    try:
        with open(pickle_file_path, "rb") as fg:
            gr = pickle.load(fg)
            return gr
    except Exception:
        return None


def pickle_graph_to_file(gr, pickle_file_path):
    with open(pickle_file_path, "wb") as pf:
        pickle.dump(gr, pf)


def make_cached_graph():
    G = Graph()
    G.bind("dggs", DGGS)

    if not os.path.isfile(PICKLED_G_FILE):
        for f in glob.glob(join(APP_DIR, "data", "*")):
            G.parse(f, format="turtle")
        pickle_graph_to_file(G, PICKLED_G_FILE)
    else:
        G = _load_graph_from_pickle(PICKLED_G_FILE)

    return G


def get_collections():
    collections = []
    g = make_cached_graph()
    for s in g.subjects(predicate=RDF.type, object=DGGS.Grid):
        for o in g.objects(subject=s, predicate=RDFS.label):
            collections.append((str(s), str(o)))

    collections = sorted(collections)
    collections.insert(0, collections.pop(-1))  # move Earth to first place
    return collections


if __name__ == "__main__":
    print([x for x in get_collections()])
