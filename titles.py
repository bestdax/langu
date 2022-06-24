import requests
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThreadPool
from PyQt6.QtWidgets import QWidget, QApplication, QListWidgetItem
import sys

from bs4 import BeautifulSoup

try:
    from .forms.titles import Ui_Form
    from .db import Database
except ImportError:
    from db import Database
    from forms.titles import Ui_Form


class Worker(QObject):
    title_signal = pyqtSignal(str, str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'}

    def run(self):
        self.get_news_title(self.url)

    def get_news_title(self, url):
        """Get new title"""
        res = requests.get(url, headers=self.headers)
        if res.status_code == 200:
            html = res.text
            soup = BeautifulSoup(html, features='html.parser')
            title = soup.h1.text.strip()
            self.title_signal.emit(url, title)


class ChooseTitles(QWidget, Ui_Form):
    title_signal = pyqtSignal(str, str)
    urls_signal = pyqtSignal([str])

    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.url_title_dict = {}
        self.db = Database('user_files/data.db')
        self.urls = self.db.get('select url from urls')[:30]
        self.setupUi(self)
        self.custom_ui()
        self.show()

    def custom_ui(self):
        while self.urls:
            self.run_worker()

        self.select_all_button.clicked.connect(self.select_all)
        self.deselect_all_button.clicked.connect(self.deselect_all)
        self.download_button.clicked.connect(self.get_selected_urls)

    def select_all(self):
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            item.setCheckState(Qt.CheckState.Checked)

    def deselect_all(self):
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            item.setCheckState(Qt.CheckState.Unchecked)

    def get_selected_urls(self):
        urls = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                title = item.text()
                url = self.url_title_dict[title]
                urls.append(url)
        self.urls_signal.emit(urls)

    def run_worker(self):
        worker = Worker(self.urls.pop())
        worker.title_signal.connect(self.update_list)
        self.thread_pool.start(worker.run)

    def update_list(self, url, title):
        self.url_title_dict[title] = url
        item = QListWidgetItem(title, self.listWidget)
        item.setCheckState(Qt.CheckState.Checked)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = ChooseTitles()
    sys.exit(app.exec())
