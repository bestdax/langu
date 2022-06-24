import os
import re
import time

import requests
import urllib3
import random

from PyQt6.QtCore import QThread, pyqtSlot
from bs4 import BeautifulSoup
import sqlite3

from aqt import mw
from aqt.qt import *
from aqt import ProfileManager
from aqt.gui_hooks import reviewer_did_show_question
from anki.cards import Card

try:
    from .deck import DeckDialog
    from .scrap import Scrap
    from .log import Logger
    from .db import Database
except ImportError:
    from deck import DeckDialog
    from scrap import Scrap
    from log import Logger
    from db import Database


class ChuXinNHK(QObject):
    setting_ready_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.scrap = None
        self.logger_thread = None
        self.scrap_thread = None
        self.logger = None
        self.nhknews_deck_name = None
        self.addon_folder = os.path.dirname(__file__)
        self.user_files = os.path.join(self.addon_folder, "user_files")
        if not os.path.exists(self.user_files):
            os.mkdir(self.user_files)
        self.db_path = os.path.join(self.user_files, 'data.db')
        self.db = None
        self.mw = mw
        self.scrap_thread = None

        self.setting_ready_signal.connect(self.on_setting_ready)

    def log(self, msg):
        self.logger.update_message(msg)
        self.logger.update()

    def init_db(self):
        table_names = ['urls', 'notes', 'users', 'log']
        for name in table_names:
            self.create_table(name)

        pm = ProfileManager()
        pm.setupMeta()
        user_names = pm.profiles()
        for username in user_names:
            self.db.table('users').insert(name=username)

    def create_table(self, name):
        if name == 'urls':
            self.db.create_table(name,
                                 ID='INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL',
                                 URL='TEXT',
                                 TITLE='TEXT')
        elif name == 'notes':
            self.db.create_table(name,
                                 ID='INTEGER PRIMARY KEY NOT NULL',
                                 PAGE_ID='INTEGER',
                                 AUDIO_URL='TEXT'
                                 )

        elif name == 'users':
            self.db.create_table(name,
                                 ID='INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL',
                                 NAME='TEXT')
        elif name == 'log':
            self.db.create_table(name,
                                 NOTE_ID='INTEGER',
                                 USER_ID='INTEGER')

    def table_exists(self, name: str) -> bool:
        """check if a table exists in database"""
        return name in self.db.tables

    def check_db(self):
        """check if table exists"""
        for table_name in ['urls', 'notes', 'users', 'log']:
            if not self.table_exists(table_name):
                self.create_table(table_name)

    def check_setting(self):
        self.db = Database(self.db_path)
        # init database if db not exists
        if not os.path.isfile(self.db_path):
            self.init_db()
        else:
            self.check_db()

        # prepare nhknews model
        nhknews_model = mw.col.models.by_name('nhknews')
        if not nhknews_model:
            # if no nhknews model exists add it
            try:
                from .nhknews_model import add_nhknews_model
            except ImportError:
                from nhknews_model import add_nhknews_model
            add_nhknews_model(mw.col)
        else:
            # if fields are not same then update
            try:
                from .nhknews_model import nhknews_model_data
            except ImportError:
                from nhknews_model import nhknews_model_data

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

        if 'nhk_deck' in mw.addonManager.getConfig(__name__).keys():
            # if getting deck config then run scrap from web
            # if not, pop a dialog to create a deck or choose a deck to contain nhknews cards
            self.mw.nhknews_deck_name = mw.addonManager.getConfig(__name__)['nhk_deck']
            self.setting_ready_signal.emit()
        else:
            self.mw.deck_dialog = DeckDialog()
            self.mw.deck_dialog.deck_ready_signal.connect(self.on_deck_ready)

        self.db.close()

    @pyqtSlot()
    def on_setting_ready(self):
        self.run()

    @pyqtSlot()
    def on_deck_ready(self):
        self.setting_ready_signal.emit()

    def run(self):
        if not self.scrap:
            self.logger = Logger()
            self.logger_thread = QThread()
            self.logger.moveToThread(self.logger_thread)
            self.logger_thread.start()
            self.scrap = Scrap()
            self.logger.hide()
            self.scrap.message_signal.connect(self.logger.update_message)
            self.scrap.download.download_signal.connect(self.logger.show)
            self.scrap.moveToThread(self.scrap_thread)
            self.scrap_thread.started.connect(self.scrap.run)
            self.scrap_thread.start()
        else:
            self.scrap.run()


if __name__ == '__main__':
    nhk = ChuXinNHK()
    # nhk.run()
