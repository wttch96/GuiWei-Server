"""开发入口：python run.py"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    if debug and host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            f"[提示] 调试模式已开启并监听 {host}。"
            "Werkzeug 调试器只应在可信局域网使用；公网部署请设置 FLASK_DEBUG=false。"
        )
    app.run(
        host=host,
        port=int(os.getenv("PORT", "5000")),
        debug=debug,
    )
