"""The Swagger spec must build.

One invalid endpoint docstring makes /apispec_1.json return 500, which breaks
the whole Swagger UI (/apidocs/). An unquoted ": " inside a description is the
usual cause.
"""
from flask import Flask
from flask_restful import Api
from flasgger import Swagger

from auth.routes import authentication_routes
from hiv.eid.routes import eid_routes
from hiv.vl.routes import vl_routes
from tb.gxpert.routes import tb_gxpert_routes
from utilities.swagger import swagger_template


def test_swagger_spec_builds():
    app = Flask(__name__)
    api = Api(app)
    for register in (vl_routes, eid_routes, tb_gxpert_routes, authentication_routes):
        register(api)
    Swagger(app, template=swagger_template)

    response = app.test_client().get("/apispec_1.json")

    assert response.status_code == 200
    paths = response.get_json()["paths"]
    assert "/hiv/vl/laboratories/rejected_samples/" in paths
    assert "/hiv/vl/summary/samples_history/" in paths
