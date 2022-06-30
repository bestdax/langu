from PyQt6.QtCore import QThread

from aqt import mw
from aqt.qt import *
from aqt import ProfileManager

from .workers import UrlWorker, TaskManager
from .deck import DeckDialog
from .log import Logger
from .db import Database
from .download import DownloadWindow


class NHK(QObject):
    setting_ready_signal = pyqtSignal()
    message_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.task_thread = None
        self.task_manager = None
        self.urls_to_handle = None
        self.task_number = 10
        self.url_thread = None
        self.url_worker = None
        self.download_window = None
        self.scrap = None
        self.scrap_thread = None
        self.logger = Logger()
        self.nhknews_deck_name = None
        self.addon_folder = os.path.dirname(__file__)
        self.user_files = os.path.join(self.addon_folder, "user_files")
        if not os.path.exists(self.user_files):
            os.mkdir(self.user_files)
        self.db_path = os.path.join(self.user_files, 'data.db')
        self.db = None
        self.mw = mw
        self.run_count = 0

        self.setting_ready_signal.connect(self.on_setting_ready)

        self.init_url_worker()
        self.init_download_window()
        self.init_task_manager()

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
        # init database if db not exists
        if not self.db:
            self.db = Database(self.db_path)
            self.init_db()
        else:
            self.db = Database(self.db_path)
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

    @pyqtSlot()
    def on_setting_ready(self):
        self.run()

    @pyqtSlot()
    def on_deck_ready(self):
        self.setting_ready_signal.emit()

    def init_url_worker(self):
        # init url worker to handle urls
        self.url_thread = QThread()
        self.url_worker = UrlWorker()
        self.url_worker.moveToThread(self.url_thread)
        self.url_thread.started.connect(self.url_worker.run)
        self.url_worker.message_signal.connect(self.logger.update_message)

    def init_download_window(self):
        # init download window
        self.download_window = DownloadWindow()

    def init_task_manager(self):
        self.task_manager = TaskManager([])
        self.task_thread = QThread()
        self.task_manager.moveToThread(self.task_thread)
        self.task_manager.message_signal.connect(self.logger.update_message)
        self.task_manager.all_tasks_finished_signal.connect(self.logger.scroll_to_bottom)
        self.task_thread.start()

    def set_urls(self):
        task_number = self.download_window.spinBox.value()
        urls = self.url_worker.urls_to_handle[:task_number]
        self.task_manager.set_urls(urls)

    def run(self):
        self.logger.show()
        if self.run_count == 0:
            # connect signals with slots
            self.url_worker.complete_signal.connect(
                lambda urls_to_handle: self.download_window.spinBox.setMaximum(len(urls_to_handle)))
            self.url_worker.complete_signal.connect(
                lambda urls_to_handle: self.download_window.spinBox.setValue(len(urls_to_handle)))
            self.url_worker.complete_signal.connect(
                lambda urls_to_handle: self.download_window.spinBox.setSuffix(f'/{len(urls_to_handle)}')
            )
            self.download_window.download_button.clicked.connect(self.task_manager.run)
            self.download_window.spinBox.valueChanged.connect(
                lambda value: self.task_manager.set_urls(self.url_worker.urls_to_handle[:value]))

            self.url_worker.complete_signal.connect(self.download_window.show)
            self.url_worker.complete_signal.connect(self.logger.hide)
            self.url_worker.complete_signal.connect(self.download_window.setup_spinbox)

            self.download_window.download_button.clicked.connect(self.logger.show)
            self.download_window.download_button.clicked.connect(self.set_urls)

            self.logger.download_more_button.clicked.connect(self.url_worker.run)

            self.url_thread.start()
        else:
            if self.logger.isHidden():
                self.logger.show()
            self.url_worker.run()
            self.download_window.show()

        self.run_count += 1


if __name__ == '__main__':
    nhk = NHK()
    # nhk.run()
