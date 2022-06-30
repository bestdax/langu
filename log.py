from PyQt6.QtWidgets import QWidget, QApplication
import sys
from aqt import mw

from .forms.log import Ui_Form


class Logger(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.mw = mw
        self.setupUi(self)
        self.custom_ui()
        self.line_number = 0

    def custom_ui(self):
        pass

    def scroll_to_bottom(self):
        vbar = self.scrollArea.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def update_message(self, text):
        self.line_number += 1
        text = self.label.text() + '\n' + f'<p><span style="color:lightgray">{self.line_number:04d}</span> {text}</p>'
        self.label.setText(text)
        self.label.update()
        self.scroll_to_bottom()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def hideEvent(self, event) -> None:
        event.accept()
        self.mw.repaint()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = Logger()
    mw.label.setText('<h1>hello world</h1>')
    sys.exit(app.exec())
