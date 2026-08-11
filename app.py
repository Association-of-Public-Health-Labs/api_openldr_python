# This is an OpenLDR API running on python with flask_restx
# The production server is waitress running on port 9001
# The execution command is waitress-serve --host=127.0.0.1 --port=9001 app:app or waitress-serve --port=9001 app:app
# The service is served by nssm service manager
# Configure NSSM: In the NSSM GUI:
# Path: Set this to your Python interpreter path, e.g., C:\Users\Administrator\scripts\OpenLDR_API\.env\Scripts\python.exe
# Startup Directory: Set this to the directory where api.py is located in this case app.py, e.g., C:\Users\Administrator\scripts\OpenLDR_API\
# Arguments: Set this to run your Flask app using Waitress: -m waitress-serve --host=127.0.0.1 --port=9001 app:app
# or -m waitress-serve --port=9001 app:app
# The service name is OpenLDR_API to start, stop, or remove it refer to nssm --help command, e.g, nssm start OpenLDR_API
# Import necessary libraries
from flask import Flask, redirect
from flask_restful import Api
from flasgger import Swagger  # type: ignore
from flask_cors import CORS  # type: ignore
from hiv.vl.routes import vl_routes
from hiv.eid.routes import eid_routes
from dict.routes import dict_routes
from tb.gxpert.routes import tb_gxpert_routes
from tb.cultura.routes import tb_cultura_routes
from auth.routes import authentication_routes
from db.database import db
from configs.paths import *  # Import all constants from paths module
from utilities.utils import *  # Import all utility functions
from utilities.swagger import swagger_template
from flask_jwt_extended import JWTManager  # type: ignore

# Create a new Flask application instance
app = Flask(__name__)

# Configure the application to use multiple databases
app.config["SQLALCHEMY_BINDS"] = SQLALCHEMY_BINDS_CDR_OPENLDR_ORG_MZ

# Disable SQLALCHEMY_TRACK_MODIFICATIONS to improve performance
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Add Secret Key for session management and CSRF protection
app.config["SECRET_KEY"] = SECRET_KEY

# Configure expiration time for JWT tokens
# 30 minutes
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = relativedelta(minutes=60)
# 7 days
# app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)


# Configure Swagger UI settings
app.config["SWAGGER"] = {
    "title": "OpenLDR API",
    "uiversion": 3,
}


# Enable CORS (Cross-Origin Resource Sharing) for the application
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Create a new API instance and bind it to the Flask application
api = Api(app)

# Initialize JWT Manager for handling JSON Web Tokens
jwt = JWTManager(app)

# Initialize Swagger UI with a custom template
# Access swagger UI by endpoint http://localhost:5000/apidocs/#/
swagger = Swagger(app, template=swagger_template)

# Initialize the database instance and bind it to the Flask application
db.init_app(app)

# Register routes for different modules
dict_routes(api)
authentication_routes(api)  # Import and register authentication routes
vl_routes(api)
eid_routes(api)
tb_gxpert_routes(api)
tb_cultura_routes(api)


# Define a route to redirect the root URL to the Swagger UI
@app.route("/")
def root():
    """
    Redirect the root URL to the Swagger UI.

    Returns:
        redirect: A redirect object pointing to the Swagger UI endpoint.
    """
    return redirect("/apidocs/")

# Run the application if this script is executed directly
if __name__ == "__main__":
    # app.run(debug=True) # Run the application in debug mode
    app.run() # Run the application in production mode
