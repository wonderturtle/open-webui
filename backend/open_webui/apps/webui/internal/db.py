import json
import logging
from contextlib import contextmanager
from typing import Any, Optional
from urllib.parse import urlparse

from open_webui.apps.webui.internal.wrappers import register_connection
from open_webui.env import OPEN_WEBUI_DIR, DATABASE_URL, SRC_LOG_LEVELS
from peewee_migrate import Router
import peewee
from sqlalchemy import create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])

class JSONField(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect) -> Any:
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value: Optional[_T], dialect) -> Any:
        return json.loads(value) if value is not None else None

    def copy(self, **kw: Any) -> Self:
        return JSONField(self.impl.length)

    def db_value(self, value):
        return json.dumps(value) if value is not None else None

    def python_value(self, value):
        return json.loads(value) if value is not None else None

def handle_peewee_migration(DATABASE_URL):
    """
    Handle the peewee migration. Now possible to use postgresql, mysql/mariadb and sqlite."""
    db = None
    try:
        parsed_url = urlparse(DATABASE_URL)
        scheme = parsed_url.scheme.split('+')[0]

        if scheme == 'mysql':
            DatabaseClass = peewee.MySQLDatabase
        elif scheme in ['postgresql', 'postgres']:
            DatabaseClass = peewee.PostgresqlDatabase
        elif scheme == 'sqlite':
            DatabaseClass = peewee.SqliteDatabase
        else:
            raise ValueError(f"Unsupported database scheme: {scheme}")

        database = parsed_url.path.lstrip('/')
        
        if scheme == 'sqlite':
            db = DatabaseClass(database)
        else:
            db = DatabaseClass(
                database,
                host=parsed_url.hostname,
                port=parsed_url.port,
                user=parsed_url.username,
                password=parsed_url.password
            )

        migrate_dir = OPEN_WEBUI_DIR / "apps" / "webui" / "internal" / "migrations"
        router = Router(db, logger=log, migrate_dir=migrate_dir)
        router.run()

    except Exception as e:
        log.error(f"Failed to initialize the database connection: {str(e)}")
        log.error(f"Database URL: {DATABASE_URL}")
        log.exception("Detailed error information:")
        raise
    finally:
        if db and not db.is_closed():
            db.close()

handle_peewee_migration(DATABASE_URL)

SQLALCHEMY_DATABASE_URL = DATABASE_URL
parsed_url = urlparse(SQLALCHEMY_DATABASE_URL)
scheme = parsed_url.scheme.split('+')[0]

if scheme == 'sqlite':
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        pool_pre_ping=True, 
        pool_recycle=3600
    )

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    expire_on_commit=False
)
Base = declarative_base()
Session = scoped_session(SessionLocal)

def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

get_db = contextmanager(get_session)






