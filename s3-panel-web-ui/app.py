from flask import Flask, render_template, session
from helpers.aws import get_user_type
from routes.auth_routes import auth_bp
from routes.bucket_routes import bucket_bp
from routes.user_routes import user_bp
from routes.groups_routes import iam_groups_bp
from routes.objects import object_bp
from routes.s3select import s3_select_bp
from routes.manage_sts_permission import manage_bp
from routes.manage_roles import manage_iam_bp
from routes.assume_roles import assume_bp


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
    app.register_blueprint(manage_iam_bp)
    app.register_blueprint(assume_bp)
    @app.errorhandler(403)
    def forbidden_error(error):
        user_info = get_user_type(
            session["access_key"], 
            session["secret_key"], 
            session["endpoint_url"]
        )
        return render_template("403.html", user_info=user_info), 403
    return app



if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=5000,debug=True)
