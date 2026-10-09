"""Create every table. Run with `python -m db.init`.

create_all only creates tables that do not exist yet, so running it twice is safe. It does
not change tables that already exist; that is the job a migration tool like Alembic does.
"""

import logging
import sys

from db.models import Base
from db.session import get_engine


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Tables ready: {', '.join(sorted(Base.metadata.tables))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
