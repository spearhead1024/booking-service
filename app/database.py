"""Engine/session construction and transaction helpers.

Write operations must be serialized per property so that the "check for overlap, then insert"
sequence cannot interleave between two requests. Two mechanisms cover the supported backends:

* SQLite has no row-level locks, so write transactions are opened with ``BEGIN IMMEDIATE``,
  which takes the database write lock up front. A concurrent writer waits (``busy timeout``)
  and then re-reads committed data, instead of failing later on a lock upgrade.
* Servers such as PostgreSQL honour ``SELECT ... FOR UPDATE``; the services lock the parent
  property row, which serializes writers per property (see ``app.services.availability``).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, event, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_WRITE_LOCK_OPTION = "booking_write_lock"
_SQLITE_BUSY_TIMEOUT_SECONDS = 30


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(url, echo=echo, pool_pre_ping=True)

    if url.database in (None, "", ":memory:"):
        # A private in-memory database lives on a single connection, which every request
        # thread would have to share - and therefore share one transaction. That defeats the
        # isolation the overlap check relies on, so a file-backed database is required.
        raise ValueError("In-memory SQLite is not supported; use a file path instead.")

    engine = create_engine(
        url,
        echo=echo,
        connect_args={"check_same_thread": False, "timeout": _SQLITE_BUSY_TIMEOUT_SECONDS},
    )
    event.listen(engine, "connect", _configure_sqlite_connection)
    event.listen(engine, "begin", _begin_sqlite_transaction)
    return engine


def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    # Disable the driver's implicit transaction handling so SQLAlchemy emits BEGIN itself.
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
    finally:
        cursor.close()


def _begin_sqlite_transaction(connection: Connection) -> None:
    is_write = connection.get_execution_options().get(_WRITE_LOCK_OPTION, False)
    connection.exec_driver_sql("BEGIN IMMEDIATE" if is_write else "BEGIN")


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # Objects stay usable after commit so responses can be serialized without a reload.
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def write_transaction(session: Session) -> Iterator[None]:
    """Run a block in a transaction that holds the write lock from its first statement.

    Commits on success and rolls back on any exception.
    """
    with session.begin():
        session.connection(execution_options={_WRITE_LOCK_OPTION: True})
        yield
