import re
import sqlite3
from sqlite3 import Cursor
from typing import Any


class Database:
    def __init__(self, db_path):
        self.path = db_path
        self.db = sqlite3.connect(self.path)

    def execute(self, sql: str, *args: Any, **kwargs: Any) -> Cursor:
        sql = sql.lower().strip()
        if kwargs:
            result = self.db.execute(sql, kwargs)
        else:
            result = self.db.execute(sql, args)
        if re.match('insert|update|delete', sql):
            self.commit()
        return result

    def executemany(self, sql: str, iterable: Any) -> None:
        self.db.executemany(sql, [(item,) for item in iterable])
        self.commit()

    def fetchone(self, sql: str, *args: Any, **kwargs: Any) -> Any:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchone()
        cursor.close()
        return result

    def get(self, sql, *args: Any, **kwargs: Any) -> list:
        result = [x[0] for x in self.fetchall(sql, *args, **kwargs)]
        return result if len(result) > 1 or len(result) == 0 else result[0]

    def fetchall(self, sql: str, *args: Any, **kwargs: Any) -> list:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchall()
        cursor.close()
        return result

    def fetchmany(self, sql: str, size: int, *args: Any, **kwargs: Any) -> list:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchmany(size)
        cursor.close()
        return result

    def cursor(self) -> Cursor:
        return self.db.cursor()

    def commit(self) -> None:
        self.db.commit()

    def close(self) -> None:
        self.db.close()
