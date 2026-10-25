"""Flask 应用工厂。"""
from pathlib import Path

import click
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import cors, db
from app.utils.errors import ApiError

PUBLIC_ENDPOINTS = {"auth.login", "health.check"}


def create_app(config=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config:
        if isinstance(config, dict):
            app.config.update(config)
        else:
            app.config.from_object(config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_path = (Path(app.instance_path) / "guiwei.db").as_posix()
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    if str(app.config["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite"):
        app.config.setdefault(
            "SQLALCHEMY_ENGINE_OPTIONS", {"connect_args": {"check_same_thread": False}}
        )
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    app.json.ensure_ascii = False
    app.json.sort_keys = False

    db.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    _register_blueprints(app)
    _register_auth_guard(app)
    _register_error_handlers(app)
    _register_cli(app)
    _register_frontend(app)

    with app.app_context():
        from app import models  # noqa: F401  确保模型注册

        if app.config.get("AUTO_CREATE_DB"):
            db.create_all()
        _ensure_schema()
        if app.config.get("AUTO_BOOTSTRAP_ADMIN"):
            from app.models import Admin
            from app.services import admin_service

            if Admin.query.count() == 0:
                admin = admin_service.bootstrap_admin()
                if not admin:
                    app.logger.warning(
                        "尚未创建管理员。请设置 ADMIN_USERNAME / ADMIN_PASSWORD，"
                        "或执行 flask --app run.py create-admin --username ... --password ..."
                    )

    return app


def _register_blueprints(app: Flask) -> None:
    from app.api import register_blueprints

    register_blueprints(app)


def _ensure_schema() -> None:
    """轻量迁移：为旧数据库补齐新增列，避免升级后启动报错。"""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "items" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("items")}
    if "color_family" not in columns:
        db.session.execute(
            text("ALTER TABLE items ADD COLUMN color_family VARCHAR(20) NOT NULL DEFAULT ''")
        )
        db.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_items_color_family "
                "ON items (color_family)"
            )
        )
        db.session.commit()

    if "containers" in inspector.get_table_names():
        container_columns = {
            column["name"] for column in inspector.get_columns("containers")
        }
        if "nickname" not in container_columns:
            db.session.execute(
                text("ALTER TABLE containers ADD COLUMN nickname VARCHAR(80) NOT NULL DEFAULT ''")
            )
            db.session.commit()

    if "photos" in inspector.get_table_names():
        # 多物品检测的裁切图标记：未入库前不在图片库展示，并会被 TTL 清理
        photo_columns = {column["name"] for column in inspector.get_columns("photos")}
        if "is_temp" not in photo_columns:
            db.session.execute(
                text("ALTER TABLE photos ADD COLUMN is_temp BOOLEAN NOT NULL DEFAULT 0")
            )
            db.session.execute(
                text("CREATE INDEX IF NOT EXISTS ix_photos_is_temp ON photos (is_temp)")
            )
            db.session.commit()

    if "ai_messages" in inspector.get_table_names():
        message_columns = {
            column["name"] for column in inspector.get_columns("ai_messages")
        }
        if "usage" not in message_columns:
            db.session.execute(
                text("ALTER TABLE ai_messages ADD COLUMN usage TEXT NOT NULL DEFAULT ''")
            )
            db.session.commit()


def _register_auth_guard(app: Flask) -> None:
    from app.utils.auth import authenticate_request

    @app.before_request
    def _authenticate():
        if request.method == "OPTIONS":
            return None
        if not request.path.startswith("/api/"):
            return None
        if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        admin, error = authenticate_request()
        if error:
            return error
        g.admin = admin
        return None


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        db.session.rollback()
        return (
            jsonify({"code": exc.status, "message": exc.message, "data": exc.data}),
            exc.status,
        )

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        message = exc.description
        if exc.code == 413:
            message = "上传内容超过大小限制"
        if exc.code == 404:
            message = "接口不存在"
        return jsonify({"code": exc.code, "message": message, "data": None}), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        db.session.rollback()
        app.logger.exception("未处理异常: %s", exc)
        return jsonify({"code": 500, "message": "服务器内部错误", "data": None}), 500


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        """创建数据库表并按配置初始化管理员。"""
        db.create_all()
        from app.services import admin_service

        admin = admin_service.bootstrap_admin()
        if admin:
            click.echo(f"数据库已初始化，管理员已创建：{admin.username}")
        else:
            click.echo("数据库已初始化。管理员已存在或未配置 ADMIN_USERNAME/ADMIN_PASSWORD。")

    @app.cli.command("create-admin")
    @click.option("--username", default=None, help="管理员用户名")
    @click.option("--password", default=None, help="管理员密码（至少 6 位）")
    def create_admin_command(username, password):
        """创建唯一的管理员账号。"""
        from app.services import admin_service

        username = username or app.config.get("ADMIN_USERNAME")
        password = password or app.config.get("ADMIN_PASSWORD")
        if not password:
            raise click.ClickException("请通过 --password 或环境变量 ADMIN_PASSWORD 提供密码")
        try:
            admin = admin_service.create_admin(username, password)
        except ApiError as exc:
            raise click.ClickException(exc.message) from exc
        click.echo(f"管理员已创建：{admin.username}")

    @app.cli.command("reset-password")
    @click.option("--username", required=True)
    @click.option("--password", required=True)
    def reset_password_command(username, password):
        """重置管理员密码。"""
        from app.services import admin_service

        try:
            admin_service.reset_password(username, password)
        except ApiError as exc:
            raise click.ClickException(exc.message) from exc
        click.echo(f"已重置 {username} 的密码")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """写入一套演示数据（仅空库可用）。"""
        from app.seed import seed_demo

        try:
            result = seed_demo()
        except ApiError as exc:
            raise click.ClickException(exc.message) from exc
        click.echo(result["note"])

    @app.cli.command("routes")
    def routes_command():
        """打印所有路由。"""
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: str(r)):
            click.echo(f"{','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})):16} {rule}")


def _register_frontend(app: Flask) -> None:
    """可选：由 Flask 托管构建后的 Vue 前端（单机部署）。"""
    if not app.config.get("SERVE_FRONTEND"):
        return
    dist = Path(app.root_path).parent.parent / "frontend" / "dist"
    if not dist.is_dir():
        app.logger.warning("SERVE_FRONTEND 已开启，但未找到 %s", dist)
        return

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path: str):
        if path.startswith(("api/", "uploads/")):
            return jsonify({"code": 404, "message": "接口不存在", "data": None}), 404
        target = dist / path
        if path and target.is_file():
            return send_from_directory(str(dist), path)
        response = send_from_directory(str(dist), "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response
