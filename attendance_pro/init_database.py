"""Initialize the current database and import legacy records on first run."""
from attendance.db import Database
from attendance.migration import bootstrap


def main() -> None:
    database = Database()
    bootstrap(database)
    print(f"Database ready: {database.path}")


if __name__ == "__main__":
    main()
