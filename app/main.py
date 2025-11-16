from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
from app.config.database_configuration import get_database
from app.config.embedding_model import load_model
from app.api.schedule_api import schedule_bp
from app.api.search_api import search_bp
from app.api.list_all_api import list_all_bp
app = Flask(__name__)
CORS(app)

# Cấu hình Swagger UI
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api-docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Schedule API",
        "description": "API documentation for Schedule Project",
        "version": "1.0.0"
    },
    "basePath": "/api",
    "schemes": ["http", "https"]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Khởi tạo DB và model
app.db = get_database()
app.model = load_model()

# Đăng ký blueprint cho từng nhóm endpoint
app.register_blueprint(schedule_bp, url_prefix='/api')
app.register_blueprint(search_bp, url_prefix='/api')
app.register_blueprint(list_all_bp, url_prefix="/api")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
