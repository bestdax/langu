import datetime
import re
import sqlite3
from sqlite3 import Cursor
from typing import Any


class Database:
    def __init__(self, db_path):
        self.path = db_path
        self._db = sqlite3.connect(self.path)

    def execute(self, sql: str, *args: Any, **kwargs: Any) -> Cursor:
        sql = sql.strip()
        if kwargs:
            result = self._db.execute(sql, kwargs)
        else:
            result = self._db.execute(sql, args)
        if re.match('insert|update|delete', sql.lower()):
            self.commit()
        return result

    def executemany(self, sql: str, iterable: Any) -> None:
        self._db.executemany(sql, [(item,) for item in iterable])
        self.commit()

    def create_table(self, table, **kwargs):
        table_string = ','.join([f'{key} {value}' for key, value in kwargs.items()])
        sql = f"create table if not exists {table} ({table_string})"
        self.execute(sql)

    def fetchone(self, sql: str, *args: Any, **kwargs: Any) -> Any:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchone()
        cursor.close()
        return result

    def get(self, sql, *args: Any, **kwargs: Any) -> Any:
        result = [x[0] for x in self.fetchall(sql, *args, **kwargs)]
        return result

    def fetchall(self, sql: str, *args: Any, **kwargs: Any) -> Any:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchall()
        cursor.close()
        return result

    def fetchmany(self, sql: str, size: int, *args: Any, **kwargs: Any) -> list:
        cursor = self.execute(sql, *args, **kwargs)
        result = cursor.fetchmany(size)
        cursor.close()
        return result

    def table(self, name):
        return Database.Table(self, name)

    @property
    def tables(self):
        result = self.get('select name from sqlite_master where type="table"')
        if 'sqlite_sequence' in result:
            result.remove('sqlite_sequence')
        return result

    def cursor(self) -> Cursor:
        return self._db.cursor()

    def commit(self) -> None:
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    class Table:
        def __init__(self, db, name):
            self.db = db
            self.name = name

        def column(self, column):
            return Database.Table.Column(self, column)

        def select(self, columns, *args, **kwargs):
            columns_string = ", ".join(columns) if isinstance(columns, list) else columns
            if not kwargs:
                if not args:
                    result = self.db.fetchall(f'select {columns_string} from {self.name} ')
                else:
                    result = self.db.fetchall(
                        f'select {columns_string} from {self.name} where {" and ".join(args)}')
            else:
                condition = ''
                for key, value in kwargs.items():
                    if not condition:
                        condition += f'{key}=?'
                    else:
                        condition += f'and {key}=?'
                result = self.db.fetchall(
                    f'select {columns_string} from {self.name} where {condition}', *kwargs.values())

            return result

        def get(self, columns: list or str, *args: Any, **kwargs: Any) -> list:
            """
            get a list of first items of search result,
            db.table('name').get('id', 'id>15')
            db.table('name').get('id', id=15)
            """
            result = self.select(columns, *args, **kwargs)
            items = [x[0] for x in result]
            return items

        def getone(self, columns: list or str, *args: Any, **kwargs: Any) -> Any:
            """get only one
            """
            result = self.get(columns, *args, **kwargs)
            if result:
                return result[0]
            else:
                return None

        def getmany(self, size, columns: list or str, *args: Any, **kwargs: Any) -> Any:
            """
            get specific number of items
            """
            result = self.get(columns, *args, **kwargs)
            return result[:size]

        def insert(self, **kwargs):
            """
            db.table('name').insert(col1='value1', col2='value2')
            :param kwargs:
            :return:
            """
            columns = kwargs.keys()
            values = kwargs.values()
            self.db.execute(
                f'insert into {self.name} ({", ".join(columns)}) values ({", ".join(list("?" * len(values)))})',
                *values)

        def insertmany(self, columns, values):
            """
            db.table('name').insert('column', ['value1', 'value2'])
            db.table('name').insert(['col1', 'col2'], [('value1', 'value2'), ('value3', 'value4')]
            """
            if isinstance(columns, list):
                self.db.executemany(
                    f'insert into {self.name} ({", ".join(columns)}) values ({", ".join(list("?" * len(columns)))})',
                    values)
            else:
                self.db.executemany(
                    f'insert into {self.name} ({columns}) values (?)',
                    values)

        def update(self, columns: Any, values: Any, new_values: Any) -> None:
            if isinstance(columns, list):
                assert len(columns) == len(values) == len(
                    new_values), "length of columns ,values and new values should be equal"
                for n in range(len(columns)):
                    self.db.execute(
                        f'update {self.name} set {columns[n]}=? where {columns[n]}=?', new_values[n], values[n])
            else:
                self.db.execute(
                    f'update {self.name} set {columns}=? where {columns}=?', new_values, values)

        def delete(self, *args, **kwargs) -> None:
            if not args:
                condition = ''
                for key, value in kwargs.items():
                    if not condition:
                        condition += f'{key}=?'
                    else:
                        condition += f' and {key}=?'
                self.db.execute(f'delete from {self.name} where {condition}', *kwargs.values())
            else:
                self.db.execute(f'delete from {self.name} where {" and ".join(args)}')

        class Column:
            def __init__(self, table_instance, column):
                self.table_instance = table_instance
                self.column = column

            def select(self, *args, **kwargs):
                return self.table_instance.select(*args, **kwargs)


if __name__ == '__main__':
    db = Database('user_files/data.db')
    # db.table('users').insert_many('name', [f'{chr(i + 97)}' * (i + 1) for i in range(26)])
    # db.table('users').delete('name!="dax"', 'name!="demo"')
    db.table('notes').update('', '', '')
    print(db.table('notes').getone('id'))
