import time

import anki.storage
from PyQt6.QtWidgets import QWidget, QApplication, QInputDialog
from PyQt6.QtCore import Qt, pyqtSignal
import sys

try:
    from nhk.forms.deck import Ui_Form
except ImportError:
    from forms.deck import Ui_Form
from aqt import mw
from aqt import ProfileManager
from aqt.operations.deck import add_deck_dialog

from aqt.utils import getOnlyText, tooltip, tr


class DeckDialog(QWidget, Ui_Form):
    deck_ready_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.mw = mw
        self.setupUi(self)
        self.custom_ui()

        self.show()

    def custom_ui(self):
        self.verticalLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.listWidget.addItems(mw.col.decks.all_names())
        self.confirm_button.clicked.connect(self.confirm)
        self.new_deck_button.clicked.connect(self.new_deck)

    def confirm(self):
        row = self.listWidget.currentRow()
        deck_name = self.listWidget.item(row).text()
        self.mw.addonManager.writeConfig(__name__, {'deck': deck_name})
        self.mw.nhknews_deck_name = deck_name
        self.deck_ready_signal.emit()
        self.close()

    def new_deck(self):
        self.close()
        if op := add_deck_dialog(parent=self.mw):
            op.run_in_background()
        time.sleep(0.2)
        latest_mod = 0
        latest_created_deck = None
        for deck in mw.col.decks.all():
            if deck['mod'] > latest_mod:
                latest_mod = deck['mod']
                latest_created_deck = deck
        self.mw.nhknews_deck_name = latest_created_deck['name']
        self.mw.addonManager.writeConfig('nhk', {'deck': self.mw.nhknews_deck_name})
        self.deck_ready_signal.emit()

    def new_dialog(self):
        self.mw.deck_dialog = DeckDialog()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    pm = ProfileManager()
    pm.setupMeta()
    pm.load('Dax')
    col = anki.storage.Collection(pm.collectionPath())
    mw1 = DeckDialog()
    mw1.listWidget.addItems([value['name'] for value in anki.decks.DecksDictProxy(col).values()])

    sys.exit(app.exec())
