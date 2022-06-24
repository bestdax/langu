import os
import sys
import sqlite3
import time

from PyQt6.QtCore import QObject, QTimer, QThread
from PyQt6.QtWidgets import QApplication


class UI2PY(QObject):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(__file__)
        if not os.path.isdir('uis'):
            os.mkdir('uis')
        if not os.path.isdir('forms'):
            os.mkdir('forms')
        if os.path.isfile('mtime.db'):
            self.load_data_from_database()
        else:
            self.path_and_mtime = {}
            for file in os.listdir('uis'):
                ui_path = os.path.join(self.base_dir, 'uis', file)
                self.path_and_mtime[ui_path] = os.path.getmtime(ui_path)
            self.write_into_database()

        self.timer = QTimer()
        self.timer.timeout.connect(self.scan)
        self.timer.start(1000)

    def scan(self):
        for file in os.listdir('uis'):
            ui_path = os.path.join(self.base_dir, 'uis', file)
            if ui_path not in self.path_and_mtime:
                self.convert(files=[ui_path])
                self.path_and_mtime[ui_path] = os.path.getmtime(ui_path)
                self.write_into_database()
            elif self.path_and_mtime[ui_path] != os.path.getmtime(ui_path):
                self.convert(files=[ui_path])
                self.path_and_mtime[ui_path] = os.path.getmtime(ui_path)
                self.write_into_database()

        for p, m in self.path_and_mtime.items():
            connection = sqlite3.connect('mtime.db')
            cursor = connection.cursor()
            if not os.path.isfile(p):
                cursor.execute('delete from mtime where path=:path', {'path': p})
                print(f'{time.strftime("%H:%M:%S", time.localtime())} deleted {p} and {m} from database')
                self.load_data_from_database()
            connection.commit()
            connection.close()

    def convert(self, files=None, number=1):
        if not files:
            latest_n_mtime = sorted(self.path_and_mtime.values(), reverse=True)[:number]
            paths = [path for path, mtime in self.path_and_mtime.items() if mtime in latest_n_mtime]
            for ui_path in paths:
                filename, ext = os.path.splitext(os.path.basename(ui_path))
                form_path = os.path.join(self.base_dir, 'forms', filename + '.py')
                os.system(f'pyuic6 "{ui_path}" -o "{form_path}"')
        else:
            for file in files:
                if not os.path.isabs(file):
                    if not file.endswith('.ui'):
                        ui_path = os.path.join(self.base_dir, 'uis', file + '.ui')
                    else:
                        ui_path = os.path.join(self.base_dir, 'uis', file)
                else:
                    ui_path = file
                filename, ext = os.path.splitext(os.path.basename(ui_path))
                form_path = os.path.join(self.base_dir, 'forms', filename + '.py')
                os.system(f'venv/bin/pyuic6 "{ui_path}" -o "{form_path}"')

    def write_into_database(self):
        connection = sqlite3.connect('mtime.db')
        cursor = connection.cursor()
        cursor.execute('create table if not exists mtime (path text, mtime real)')
        cursor.execute('select * from mtime')
        recorded_data = cursor.fetchall()
        recorded_data_dict = {p: m for p, m in recorded_data}
        for path, mtime in self.path_and_mtime.items():
            if path not in recorded_data_dict:
                cursor.execute('insert into mtime values (?, ?)', (path, mtime))
                print(
                    f'{time.strftime("%H:%M:%S", time.localtime())} added {os.path.basename(path)} and {mtime} into database')
            elif mtime != recorded_data_dict[path]:
                cursor.execute('update mtime set mtime=:mtime where path=:path', {'path': path, 'mtime': mtime})
                print(
                    f'{time.strftime("%H:%M:%S", time.localtime())} updated {os.path.basename(path)} mtime to {mtime}')

        connection.commit()
        connection.close()

    def load_data_from_database(self):
        connection = sqlite3.connect('mtime.db')
        cursor = connection.cursor()
        cursor.execute('create table if not exists mtime (path text, mtime real)')
        cursor.execute('select * from mtime')
        recorded_data = cursor.fetchall()
        recorded_data_dict = {p: m for p, m in recorded_data}
        self.path_and_mtime = recorded_data_dict
        connection.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    convert = UI2PY()
    sys.exit(app.exec())
