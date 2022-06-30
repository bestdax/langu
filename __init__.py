from .nhk import NHK
from aqt.qt import *
from aqt import mw

if not (LangU_menu := mw.menuBar().findChild(QMenu, "LangU")):
    LangU_menu = mw.menuBar().addMenu("LangU")

# Chuxin NHKNews
nhk = NHK()
nhknews_action = QAction("NHK News", mw)
LangU_menu.addAction(nhknews_action)
qconnect(nhknews_action.triggered, nhk.check_setting)




