import os
from rdflib import Namespace
from rhealpixdggs.dggs import *
from rhealpixdggs.ellipsoids import *

APP_DIR = os.environ.get("APP_DIR", os.path.dirname(os.path.realpath(__file__)))
TEMPLATES_DIR = os.environ.get("TEMPLATES_DIR", os.path.join(APP_DIR, "view", "templates"))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(APP_DIR, "view", "style"))
LOGFILE = os.environ.get("LOGFILE", os.path.join(APP_DIR, "catprez.log"))
DEBUG = os.environ.get("DEBUG", True)
PORT = os.environ.get("PORT", 5000)
CACHE_HOURS = os.environ.get("CACHE_HOURS", 1)
CACHE_FILE = os.environ.get("CACHE_DIR", os.path.join(APP_DIR, "cache", "DATA.pickle"))
LOCAL_URIS = os.environ.get("LOCAL_URIS", True)
PICKLED_G_FILE = os.path.join(APP_DIR, "data", "DATA.pickle")

# rdflib
DGGSP = Namespace("https://w3id.org/dggs/abstract")
DGGS = Namespace("https://w3id.org/dggs/abstract/ont/")
URI_BASE_DATASET = Namespace("https://w3id.org/dggs/tb16pix/")
URI_BASE_CELL = Namespace("https://w3id.org/dggs/tb16pix/cell/")
URI_BASE_RESOLUTION = Namespace("https://w3id.org/dggs/tb16pix/resolution/")

# rHealPix
WGS84_TB16 = Ellipsoid(a=6378137.0, b=6356752.314140356, e=0.0578063088401, f=0.003352810681182, lon_0=-131.25)
TB16Pix = RHEALPixDGGS(ellipsoid=WGS84_TB16, north_square=0, south_square=0, N_side=3)
