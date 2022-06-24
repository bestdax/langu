from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QApplication
import sys

try:
    from .forms.download import Ui_Form
    from .titles import ChooseTitles
except ImportError:
    from forms.download import Ui_Form
    from titles import ChooseTitles


class Download(QWidget, Ui_Form):
    download_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.choose_titles_window = None
        self.setupUi(self)
        self.custom_ui()

        self.show()

    def custom_ui(self):
        self.download_button.clicked.connect(self.download)
        self.spinBox.setEnabled(False)
        self.comboBox.currentTextChanged.connect(self.setup_spinbox)

    def download(self):
        self.download_signal.emit()
        self.hide()

    def setup_spinbox(self):
        if self.comboBox.currentText() == 'All':
            self.spinBox.setEnabled(False)
        else:
            self.spinBox.setEnabled(True)
            self.spinBox.setValue(10)

    def choose_titles(self):
        self.choose_titles_window = ChooseTitles()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = Download()
    sys.exit(app.exec())
