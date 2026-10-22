"""Flask 扩展实例，集中初始化，避免循环导入。"""
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cors = CORS()
