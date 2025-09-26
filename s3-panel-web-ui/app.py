from flask import Flask
from routes.auth_routes import auth_bp
from routes.bucket_routes import bucket_bp
from routes.user_routes import user_bp
from routes.groups_routes import iam_groups_bp
from routes.objects import object_bp
from routes.s3select import s3_select_bp
from routes.manage_sts_permission import manage_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = "super-secret-key"

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(bucket_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(iam_groups_bp)
    app.register_blueprint(object_bp)
    app.register_blueprint(s3_select_bp)
    app.register_blueprint(manage_bp)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
