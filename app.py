from PySide6 import QtWidgets, QtCore
import os
import sys
import time


class FilePicker(QtWidgets.QWidget):
    textChanged = QtCore.Signal(str)

    def __init__(self,
                 label=None,
                 placeholder_text=None,
                 filepath_root=None,
                 is_directory=False,
                 parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.is_directory = is_directory
        self.button = QtWidgets.QPushButton("Select File" if label is None else label)
        self.button.clicked.connect(self.open_file_dialog)
        self.line_edit = QtWidgets.QLineEdit()
        if placeholder_text is None:
            self.line_edit.setPlaceholderText("Select File")
        else:
            self.line_edit.setPlaceholderText(placeholder_text)
        self.line_edit.textChanged.connect(self.updateLabel)
        self.status_label = QtWidgets.QLabel()
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.status_label)
        hbox.addWidget(self.line_edit)
        hbox.addWidget(self.button)
        self.filepath_root = filepath_root
        self.setLayout(hbox)
        self.updateLabel("")

    def open_file_dialog(self):
        file_dialog = QtWidgets.QFileDialog(self)
        if self.filepath_root is not None and os.path.exists(self.filepath_root):
            file_dialog.setDirectory(self.filepath_root)

        # Only allow selecting existing files
        file_dialog.setFileMode(
            QtWidgets.QFileDialog.Directory if self.is_directory else QtWidgets.QFileDialog.ExistingFile)
        # file_dialog.setNameFilter(f"(*{self.file_type_filter})")  # Optional filter for file types
        if file_dialog.exec():
            self.selected_file = file_dialog.selectedFiles()[0]
            if self.selected_file is not None:
                self.line_edit.setText(self.selected_file)
            else:
                self.line_edit.clear()
        # This is called because we are listening for text changed
        # self.updateLabel()

    def updateLabel(self, current_text):
        if current_text.strip() == "":
            icon_name = "SP_FileIcon"
        elif os.path.exists(current_text):
            icon_name = "SP_DialogApplyButton"
        else:
            icon_name = "SP_MessageBoxWarning"
        icon = self.style().standardIcon(getattr(QtWidgets.QStyle, icon_name))
        # Set the icon to the label
        self.status_label.setPixmap(icon.pixmap(32, 32))  # Adjust the size as needed=
        self.textChanged.emit(current_text)

    def text(self):
        return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(text)

    def fileExists(self):
        return os.path.exists(self.line_edit.text())


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Photo Importer")

        self.menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.showMessage("Ready")
        self.setStatusBar(self.statusbar)

        self.tab_widget = QtWidgets.QTabWidget()

        self.widget_import = self._createImportWidget()
        self.widget_organize = self._createOrganizeWidget()

        self.tab_widget.addTab(self.widget_import, "Import")
        self.tab_widget.addTab(self.widget_organize, "Organize")

        self.setCentralWidget(self.tab_widget)

        self._loadWidgetSettings()

        self.show()

    def _createImportWidget(self):
        widget_container = QtWidgets.QWidget()
        self.file_picker_src = FilePicker(
            label="Import Location",
            is_directory=True,
            placeholder_text="/Volumes",
            filepath_root="/Volumes")

        path = "${HOME}/Pictures/PhotoImportLibrary"
        self.file_picker_dst = FilePicker(
            label="Library Folder",
            is_directory=True,
            placeholder_text=os.path.expandvars(path),
            filepath_root=os.path.expandvars(path))

        self.file_picker_src.textChanged.connect(self._enableImport)
        self.file_picker_dst.textChanged.connect(self._enableImport)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)

        self.button_import = QtWidgets.QPushButton("Import")
        self.button_import.clicked.connect(self._runImport)
        self.button_import.setEnabled(False)

        vbox_layout = QtWidgets.QVBoxLayout()
        vbox_layout.addWidget(self.file_picker_src)
        vbox_layout.addWidget(self.file_picker_dst)
        vbox_layout.addWidget(self.button_import)
        vbox_layout.addWidget(self.progress_bar)
        vbox_layout.addStretch()

        widget_container.setLayout(vbox_layout)
        self._enableImport()

        return widget_container

    def _enableImport(self):
        if self.file_picker_src.fileExists() and self.file_picker_dst.fileExists():
            self.button_import.setEnabled(True)
            self.statusbar.showMessage("Ready")
        else:
            self.statusbar.showMessage("Import locations and library paths must exist.")
            self.button_import.setEnabled(False)

    def _runImport(self):
        self.statusbar.showMessage("Importing Images")
        self.file_picker_src.setEnabled(False)
        self.file_picker_dst.setEnabled(False)
        self.button_import.setEnabled(False)
        time.sleep(3)
        self.file_picker_src.setEnabled(True)
        self.file_picker_dst.setEnabled(True)
        self.button_import.setEnabled(True)
        self.statusbar.showMessage("Import Complete")

    def _createOrganizeWidget(self):
        widget_container = QtWidgets.QWidget()
        path = "${HOME}/Pictures/"
        self.file_picker_organize_src = FilePicker(
            label="Source Folder",
            is_directory=True,
            placeholder_text=os.path.expandvars(path),
            filepath_root=os.path.expandvars(path))

        widget_copy = QtWidgets.QWidget()
        hbox_copy = QtWidgets.QHBoxLayout()

        self.checkbox_copy_location = QtWidgets.QCheckBox("Copy")
        self.checkbox_copy_location.stateChanged.connect(self._enableCopyLocation)
        self.file_picker_organize_dst = FilePicker(
            label="Output Folder",
            is_directory=True,
            placeholder_text=os.path.expandvars(path),
            filepath_root=os.path.expandvars(path))

        hbox_copy.addWidget(self.checkbox_copy_location)
        hbox_copy.addWidget(self.file_picker_organize_dst)
        widget_copy.setLayout(hbox_copy)

        self.file_picker_organize_dst.setEnabled(False)
        self.file_picker_organize_src.textChanged.connect(self._enableOrganize)
        self.file_picker_organize_dst.textChanged.connect(self._enableOrganize)

        self.progress_bar_organize = QtWidgets.QProgressBar()
        self.progress_bar_organize.setTextVisible(True)

        self.button_organize = QtWidgets.QPushButton("Organize")
        self.button_organize.clicked.connect(self._runOrganize)
        self.button_organize.setEnabled(False)

        vbox_layout = QtWidgets.QVBoxLayout()
        vbox_layout.addWidget(self.file_picker_organize_src)
        vbox_layout.addWidget(widget_copy)
        vbox_layout.addWidget(self.button_organize)
        vbox_layout.addWidget(self.progress_bar_organize)
        vbox_layout.addStretch()

        widget_container.setLayout(vbox_layout)
        self._enableOrganize()

        return widget_container

    def _enableOrganize(self):
        if self.file_picker_organize_src.fileExists():
            self.button_organize.setEnabled(True)
        else:
            self.button_organize.setEnabled(False)

    def _enableCopyLocation(self, state):
        self.file_picker_organize_dst.setEnabled(state == 2)

    def _runOrganize(self):
        self.statusbar.showMessage("Organizing Images")
        self.file_picker_organize_src.setEnabled(False)
        self.file_picker_organize_dst.setEnabled(False)
        self.checkbox_copy_location.setEnabled(False)
        self.button_organize.setEnabled(False)
        time.sleep(3)
        self.file_picker_organize_src.setEnabled(True)
        self.file_picker_organize_dst.setEnabled(True)
        self.checkbox_copy_location.setEnabled(True)
        self.button_organize.setEnabled(True)
        self.statusbar.showMessage("Organize Complete")

    def _createPreferences(self):
        widget_container = QtWidgets.QWidget()
        return widget_container

    def _loadWidgetSettings(self):
        settings = QtCore.QSettings("rischio", "PhotoImporter")

        if not os.path.exists(settings.fileName()):
            return

        settings.sync()
        all_widgets = list((name, widget) for (name, widget) in vars(self).items()
                           if isinstance(widget, QtWidgets.QWidget)
                           and name in settings.allKeys())

        for name, widget in all_widgets:
            if isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(str(settings.value(name)))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentIndex(int(settings.value(name)))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.setChecked(True if int(settings.value(name)) > 0 else False)
            elif isinstance(widget, QtWidgets.QSpinBox):
                widget.setValue(int(settings.value(name)))
            elif isinstance(widget, FilePicker):
                widget.setText(settings.value(name))

        if "geometry" in settings.allKeys():
            self.restoreGeometry(settings.value('geometry', ''))

    def _saveWidgetSettings(self):
        settings = QtCore.QSettings("rischio", "PhotoImporter")
        all_widgets = list((name, widget) for (name, widget) in vars(self).items() if isinstance(
            widget, QtWidgets.QWidget))

        for name, widget in all_widgets:
            if isinstance(widget, QtWidgets.QLineEdit):
                settings.setValue(name, widget.text())
            elif isinstance(widget, QtWidgets.QComboBox):
                settings.setValue(name, widget.currentIndex())
            elif isinstance(widget, QtWidgets.QCheckBox):
                settings.setValue(name, 1 if widget.isChecked() else 0)
            elif isinstance(widget, QtWidgets.QSpinBox):
                settings.setValue(name, widget.value())
            elif isinstance(widget, FilePicker):
                settings.setValue(name, widget.text())

        geometry = self.saveGeometry()
        settings.setValue('geometry', geometry)
        settings.sync()

    def closeEvent(self, event):
        self._saveWidgetSettings()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    app.exec()
