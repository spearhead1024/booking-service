import pytest

from app.database import create_db_engine


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_rejects_in_memory_sqlite(url: str) -> None:
    with pytest.raises(ValueError, match="In-memory SQLite is not supported"):
        create_db_engine(url)
