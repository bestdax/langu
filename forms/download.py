# Form implementation generated from reading ui file '/Users/dax/Library/Application Support/Anki2/addons21/langu/uis/download.ui'
#
# Created by: PyQt6 UI code generator 6.3.1
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(400, 300)
        self.verticalLayout = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.comboBox = QtWidgets.QComboBox(Form)
        self.comboBox.setObjectName("comboBox")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.horizontalLayout.addWidget(self.comboBox)
        self.spinBox = QtWidgets.QSpinBox(Form)
        self.spinBox.setSuffix("")
        self.spinBox.setPrefix("")
        self.spinBox.setSingleStep(10)
        self.spinBox.setObjectName("spinBox")
        self.horizontalLayout.addWidget(self.spinBox)
        self.download_button = QtWidgets.QPushButton(Form)
        self.download_button.setObjectName("download_button")
        self.horizontalLayout.addWidget(self.download_button)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Download Settings"))
        self.comboBox.setItemText(0, _translate("Form", "All"))
        self.comboBox.setItemText(1, _translate("Form", "Custom Number"))
        self.download_button.setText(_translate("Form", "Download"))
