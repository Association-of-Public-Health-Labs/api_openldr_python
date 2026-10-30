import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_restful import Api
from flask_jwt_extended import JWTManager, create_access_token
from db.database import db


# tests/test_hiv_endpoints.py is a standalone integration script (it talks to
# real DBs and uses ``token`` as a regular function argument, not a pytest
# fixture).  Telling pytest to skip its collection keeps the unit-test run
# clean without having to delete the file.
collect_ignore = ["test_hiv_endpoints.py"]


@pytest.fixture(scope="session")
def app():
    """Create Flask app with test configuration."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_BINDS"] = {
        "vlSMS": "sqlite:///:memory:",
        "vl": "sqlite:///:memory:",
        "dpi": "sqlite:///:memory:",
        "tb": "sqlite:///:memory:",
        "dict": "sqlite:///:memory:",
        "users": "sqlite:///:memory:",
        "reportData": "sqlite:///:memory:",
        "ad": "sqlite:///:memory:",
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret-at-least-32-bytes-long"

    jwt = JWTManager(app)
    db.init_app(app)

    api = Api(app)

    # Import and register routes for every domain the test suite exercises.
    from hiv.vl.routes import vl_routes
    from hiv.eid.routes import eid_routes
    from tb.gxpert.routes import tb_gxpert_routes
    from auth.routes import authentication_routes
    from suggestions.routes import suggestion_routes

    vl_routes(api)
    eid_routes(api)
    tb_gxpert_routes(api)
    authentication_routes(api)
    suggestion_routes(api)

    with app.app_context():
        db.create_all()

    yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Valid JWT authorization headers."""
    with app.app_context():
        token = create_access_token(
            identity="test-user",
            additional_claims={
                "user_id": "test-123",
                "user_name": "testuser",
                "first_name": "Test",
                "last_name": "User",
                "email": "test@openldr.org",
                "role": "Admin",
            },
        )
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_vl_query_params():
    """Standard VL query parameters."""
    return {
        "interval_dates": ["2024-01-01", "2024-12-31"],
        "province": ["Maputo"],
        "facility_type": "province",
    }


@pytest.fixture
def sample_eid_query_params():
    """Standard EID query parameters."""
    return {
        "interval_dates": ["2024-01-01", "2024-12-31"],
        "province": ["Maputo"],
        "facility_type": "province",
        "lab_type": "all",
    }


@pytest.fixture
def mock_vl_service_response():
    """Sample VL service response for mocking."""
    return [
        {
            "year": 2024,
            "month": 1,
            "month_name": "January",
            "total": 150,
            "total_not_null": 140,
            "total_null": 10,
            "suppressed": 120,
            "not_suppressed": 20,
            "male_suppressed": 60,
            "male_not_suppressed": 10,
            "female_suppressed": 60,
            "female_not_suppressed": 10,
        }
    ]


@pytest.fixture
def mock_eid_service_response():
    """Sample EID service response for mocking."""
    return [
        {
            "year": 2024,
            "month": 1,
            "month_name": "January",
            "total": 200,
            "tested": 180,
            "positive": 15,
            "negative": 165,
            "rejected": 10,
            "pending": 10,
            "female": 95,
            "male": 85,
        }
    ]
