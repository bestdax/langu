import os
import re
import time

import requests
import urllib3
import random
from bs4 import BeautifulSoup
import sqlite3

from aqt import mw
from aqt.qt import *
from aqt import ProfileManager
from aqt.gui_hooks import reviewer_did_show_question
from anki.cards import Card

try:
    from nhk.deck import DeckDialog
    from nhk.scrapnhk import NHKNews
    from nhk.log import Logger
except ImportError:
    from deck import DeckDialog
    from scrapnhk import NHKNews
    from log import Logger


class ChuXinNHK(QObject):
    presetting_ready_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.logger_thread = None
        self.scrap_thread = None
        self.logger = None
        self.nhknews_deck_name = None
        self.addon_folder = os.path.dirname(__file__)
        self.user_files = os.path.join(self.addon_folder, "user_files")
        if not os.path.exists(self.user_files):
            os.mkdir(self.user_files)
        self.db_path = os.path.join(self.user_files, 'data.db')
        self.mw = mw
        self.scrap_thread = None

        self.presetting_ready_signal.connect(self.on_presetting_ready)

    def log(self, msg):
        self.logger.update_message(msg)
        self.logger.update()

    def init_db(self):
        table_names = ['urls', 'notes', 'users', 'log']
        for name in table_names:
            self.create_table(name)

    def create_table(self, name):
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.cursor()
            if name == 'urls':
                cursor.execute("""CREATE TABLE IF NOT EXISTS urls (
                                              ID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                                              URL TEXT)
                                              """)
            elif name == 'notes':
                cursor.execute("""CREATE TABLE IF NOT EXISTS notes (
                           ID INTEGER PRIMARY KEY NOT NULL,
                           PAGE_ID INTEGER,
                           AUDIO_URL TEXT
                           )""")

            elif name == 'users':
                cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                              ID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                              NAME TEXT)
                              """)
            elif name == 'log':
                cursor.execute("""CREATE TABLE IF NOT EXISTS log (
                            NOTE_ID INTEGER,
                            USER_ID INTEGER)""")
                pm = ProfileManager()
                pm.setupMeta()
                user_names = pm.profiles()
                for username in user_names:
                    cursor.execute("""INSERT INTO users (NAME) VALUES (?);""", [username])
                connection.commit()
            else:
                pass

    def table_exists(self, name: str) -> bool:
        """check if a table exists in database"""
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.cursor()
            cursor.execute(f'select name from sqlite_master where type="table" and name="{name}"')
            return bool(cursor.fetchone())

    def check_db(self):
        """check if table exists"""
        for table_name in ['urls', 'notes', 'users', 'log']:
            if not self.table_exists(table_name):
                self.create_table(table_name)

    def presetting(self):
        # init database if db not exists
        if not os.path.isfile(self.db_path):
            self.init_db()
        else:
            self.check_db()

        # prepare nhknews model
        nhknews_model = mw.col.models.by_name('nhknews')
        if not nhknews_model:
            # if no nhknews model exists add it
            from nhk.nhknews_model import add_nhknews_model
            add_nhknews_model(mw.col)
        else:
            # if fields are not same then update
            from nhk.nhknews_model import nhknews_model_data
            if nhknews_model['flds'] != nhknews_model_data['flds']:
                nhknews_model['flds'] = nhknews_model_data['flds']
                mw.col.models.save(nhknews_model)

        self.scrap_thread = QThread()
        # config setting
        config_file = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.isfile(config_file):
            # if no config file add one
            with open(config_file, 'w') as f:
                f.write('{}')
        if 'deck' in mw.addonManager.getConfig('nhk').keys():
            # if getting deck config then run scrap from web
            # if not, pop a dialog to create a deck or choose a deck to contain nhknews cards
            self.mw.nhknews_deck_name = mw.addonManager.getConfig('nhk')['deck']
            self.presetting_ready_signal.emit()
        else:
            self.mw.deck_dialog = DeckDialog()
            self.mw.deck_dialog.deck_ready_signal.connect(self.on_deck_ready)

    @pyqtSlot()
    def on_presetting_ready(self):
        self.scrap()

    @pyqtSlot()
    def on_deck_ready(self):
        self.presetting_ready_signal.emit()

    def run(self):
        if self.scrap_thread and self.scrap_thread.isRunning:
            self.scrap_thread.quit()
        self.presetting()

    def scrap(self):
        self.logger = Logger()
        self.logger_thread = QThread()
        self.logger.moveToThread(self.logger_thread)
        self.logger_thread.start()
        self.mw.nhknews = NHKNews()
        self.mw.nhknews.message_signal.connect(self.logger.update_message)
        self.mw.nhknews.moveToThread(self.scrap_thread)
        self.scrap_thread.started.connect(self.mw.nhknews.scrap)
        self.scrap_thread.start()


if __name__ == '__main__':
    nhk = ChuXinNHK()
    # nhk.run()
