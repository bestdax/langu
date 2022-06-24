from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QWidget, QApplication
import sys

try:
    from .forms.log import Ui_Form
except ImportError:
    from forms.log import Ui_Form


class Logger(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.setupUi(self)
        self.custom_ui()

        self.show()

    def custom_ui(self):
        pass

    def update_message(self, text):
        text = self.label.text() + '\n' + f'<p>{text}</p>'
        self.label.setText(text)
        self.label.update()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        print('still running')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = Logger()
    mw.label.setText('<h1>hello world</h1>')
    sys.exit(app.exec())
