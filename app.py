#!/usr/bin/env python3
import os
import shutil
import sys
import time
from PySide6 import QtWidgets, QtCore, QtGui
import core


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
        self.line_edit.setFixedWidth(250)
        if placeholder_text is None:
            self.line_edit.setPlaceholderText("Select File")
        else:
            self.line_edit.setPlaceholderText(placeholder_text)
        self.line_edit.textChanged.connect(self.updateLabel)
        self.status_label = QtWidgets.QLabel()
        hbox = QtWidgets.QHBoxLayout()
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


def list_volumes():
    """ Lists mounted volumes found in /Volumes directory on macOS """
    volumes_path = "/Volumes"
    try:
        # List directories in /Volumes, which are the mounted volumes
        return [volume for volume in os.listdir(volumes_path) if os.path.isdir(os.path.join(volumes_path, volume))]
    except FileNotFoundError:
        # In case the /Volumes directory does not exist
        return []


class SettingsDialog(QtWidgets.QDialog):

    updated = QtCore.Signal()

    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Settings")
        layout = QtWidgets.QVBoxLayout(self)

        # Integer SpinBox for number of threads
        self.thread_spinbox = QtWidgets.QSpinBox(self)
        self.thread_spinbox.setRange(1, 64)  # Assuming 1 to 64 threads
        self.thread_spinbox.setValue(8)  # Default value
        self.thread_spinbox.setToolTip("Number of worker threads to run Graphics Magick compression.")
        layout.addWidget(QtWidgets.QLabel("Number of Threads:"))
        layout.addWidget(self.thread_spinbox)

        # Double SpinBox for compression amount (float)
        self.compression_enabled = QtWidgets.QCheckBox("Enable Compression")
        self.compression_enabled.setToolTip("Enable or disable Graphics Magick compression.")
        self.compression_spinbox = QtWidgets.QDoubleSpinBox(self)
        self.compression_spinbox.setRange(0.0, 100.0)  # Compression range
        self.compression_spinbox.setSingleStep(1.0)
        self.compression_spinbox.setValue(90.0)  # Default value
        layout.addWidget(QtWidgets.QLabel("Compression Amount (%):"))
        layout.addWidget(self.compression_enabled)
        layout.addWidget(self.compression_spinbox)

        # CheckBox for playing a sound
        self.movies_checkbox = QtWidgets.QCheckBox("Import Movies", self)
        self.movies_checkbox.setToolTip("Enable copying of movie files from Volume.")
        self.movies_checkbox.setChecked(True)  # Default checked
        layout.addWidget(self.movies_checkbox)

        # CheckBox for playing a sound
        self.sound_checkbox = QtWidgets.QCheckBox("Play Sound on Completion", self)
        self.sound_checkbox.setToolTip("Enable or disable import complete sound.")
        self.sound_checkbox.setChecked(True)  # Default checked
        layout.addWidget(self.sound_checkbox)

        # Buttons for OK and Cancel
        buttons_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK", self)
        cancel_button = QtWidgets.QPushButton("Cancel", self)
        buttons_layout.addWidget(ok_button)
        buttons_layout.addWidget(cancel_button)

        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        layout.addLayout(buttons_layout)
        layout.addStretch()

        self.setMinimumSize(self.sizeHint())
        self.setMaximumSize(self.sizeHint())

        self.load_settings()

    def accept(self):
        self.saveSettings()
        super().accept()
        self.updated.emit()

    def saveSettings(self):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        settings.setValue('num_threads', self.thread_spinbox.value())
        settings.setValue('compression_amount', self.compression_spinbox.value())
        settings.setValue("compression_enabled", self.compression_enabled.isChecked())
        settings.setValue('play_sound', self.sound_checkbox.isChecked())
        settings.setValue('import_movies', self.movies_checkbox.isChecked())

    def load_settings(self):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        self.thread_spinbox.setValue(settings.value('num_threads', 8, int))
        self.compression_spinbox.setValue(settings.value('compression_amount', 90.0, float))
        self.compression_enabled.setChecked(settings.value('compression_enabled', True, bool))
        self.sound_checkbox.setChecked(settings.value('play_sound', True, bool))
        self.movies_checkbox.setChecked(settings.value('import_movies', True, bool))


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowIcon(QtGui.QIcon("icon.png"))  # Set the window icon
        self.setWindowTitle("Photo Importer")

        self.menubar = QtWidgets.QMenuBar(self)
        self.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.showMessage("Ready")
        self.setStatusBar(self.statusbar)

        self.tab_widget = QtWidgets.QTabWidget()

        widget_main = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout()
        self.widget_import = self._createImportWidget()
        main_layout.addWidget(self.widget_import)
        widget_main.setLayout(main_layout)

        menu_bar = QtWidgets.QMenuBar(self)
        self.setMenuBar(menu_bar)
        settings_menu = menu_bar.addMenu("Settings")
        settings_action = QtGui.QAction("Preferences...", self)
        settings_action.setShortcut("Meta+,")
        settings_action.triggered.connect(self._openSettings)
        settings_menu.addAction(settings_action)

        self.thread_import = QtCore.QThread()

        self.setCentralWidget(widget_main)

        self._loadWidgetSettings()
        self.setMinimumSize(self.sizeHint())
        self.setMaximumSize(self.sizeHint())
        self.show()

    def _openSettings(self):
        dialog = SettingsDialog(self)
        dialog.updated.connect(self._updateSettingsHud)
        dialog.exec()

    def _createSettingsHudWidget(self):
        # widget = QtWidgets.QGroupBox("Settings")
        widget = QtWidgets.QWidget()
        self.label_hud = QtWidgets.QLabel()
        self.button_settings = QtWidgets.QPushButton("Settings")
        self.button_settings.clicked.connect(self._openSettings)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.label_hud)
        hbox.addWidget(self.button_settings)
        widget.setLayout(hbox)
        self._updateSettingsHud()
        return widget

    def _updateSettingsHud(self):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        compression = settings.value('compression_amount', 90.0, float)
        compression_enabled = settings.value('compression_enabled', True, bool)
        import_movies = settings.value('import_movies', True, bool)
        text = "<b>Compression:</b> " + (f"{compression}% " if compression_enabled else "Disabled ")
        text += f"<b>Import Movies:</b> {import_movies}"
        self.label_hud.setText(text)


    def _createImportWidget(self):
        widget_container = QtWidgets.QWidget()

        label_widget = QtWidgets.QLabel("Import Photos from Volume")
        label_widget.setAlignment(QtCore.Qt.AlignCenter)

        group_box_source = QtWidgets.QGroupBox("Source Location")
        vbox_source = QtWidgets.QVBoxLayout()

        self.file_picker_src = FilePicker(
            label="Import Location",
            is_directory=True,
            placeholder_text="/Volumes",
            filepath_root="/Volumes")

        widget_storage = QtWidgets.QWidget()
        hbox_storage = QtWidgets.QHBoxLayout()
        label_storage = QtWidgets.QLabel("Free Space")

        self.storage_bar = QtWidgets.QProgressBar()
        self.storage_bar.setRange(0, 100)
        hbox_storage.addWidget(label_storage)
        hbox_storage.addWidget(self.storage_bar)
        widget_storage.setLayout(hbox_storage)


        group_box_dest = QtWidgets.QGroupBox("Import Location")
        vbox_dest = QtWidgets.QVBoxLayout()


        path = "${HOME}/Pictures/PhotoImportLibrary"
        self.file_picker_dst = FilePicker(
            label="Library Folder",
            is_directory=True,
            placeholder_text=os.path.expandvars(path),
            filepath_root=os.path.expandvars(path))

        self.file_picker_src.textChanged.connect(self._enableImport)
        self.file_picker_src.textChanged.connect(self._updateStorageBar)
        self.file_picker_dst.textChanged.connect(self._enableImport)

        widget_progress = QtWidgets.QWidget()
        hbox_progress = QtWidgets.QHBoxLayout()
        label_progress = QtWidgets.QLabel("Progress")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        hbox_progress.addWidget(label_progress)
        hbox_progress.addWidget(self.progress_bar)
        widget_progress.setLayout(hbox_progress)

        widget_buttons = QtWidgets.QWidget()
        hbox_buttons = QtWidgets.QHBoxLayout()

        self.button_import = QtWidgets.QPushButton("Import")
        self.button_import.setToolTip("Run image import from the source location and copy to the Library Folder")
        self.button_import.clicked.connect(self._runImport)
        self.button_import.setEnabled(False)

        self.button_cancel_import = QtWidgets.QPushButton("Cancel")
        self.button_cancel_import.clicked.connect(self._cancelImport)
        self.button_cancel_import.setEnabled(False)

        hbox_buttons.addWidget(self.button_import)
        hbox_buttons.addWidget(self.button_cancel_import)
        widget_buttons.setLayout(hbox_buttons)

        vbox_layout = QtWidgets.QVBoxLayout()

        vbox_source.addWidget(label_widget)
        vbox_source.addWidget(self.file_picker_src)
        vbox_source.addWidget(widget_storage)
        group_box_source.setLayout(vbox_source)

        settings_hud = self._createSettingsHudWidget()
        vbox_dest.addWidget(self.file_picker_dst)
        vbox_dest.addWidget(settings_hud)
        vbox_dest.addWidget(widget_buttons)
        group_box_dest.setLayout(vbox_dest)

        vbox_layout.addWidget(group_box_source)
        vbox_layout.addWidget(group_box_dest)

        vbox_layout.addWidget(widget_progress)
        vbox_layout.addStretch()

        widget_container.setLayout(vbox_layout)
        self._enableImport()
        self._updateStorageBar()

        return widget_container

    def _enableImport(self):
        if self.file_picker_src.fileExists() and self.file_picker_dst.fileExists():
            self.button_import.setEnabled(True)
            self.statusbar.showMessage("Ready")
        else:
            self.statusbar.showMessage("Import locations and library paths must exist.")
            self.button_import.setEnabled(False)

    def _updateStorageBar(self):
        # Use os.path.abspath to resolve any relative path issues
        directory = self.file_picker_src.text()
        if not os.path.exists(directory):
            used_percentage = 0
        else:
            total, used, free = shutil.disk_usage(directory)
            used_percentage = (used / total) * 100
        self.storage_bar.setToolTip(f"{used_percentage}% Used")
        self.storage_bar.setValue(used_percentage)

    def _runImport(self):

        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        import_movies = settings.value('import_movies', True, bool)
        run_compress = settings.value('compression_enabled', True, bool)

        if not os.path.exists("/opt/homebrew/bin/gm") and run_compress is True:
            if self.promptUser("PhotoImporter", "Graphics Magick is required to compress images. It isnt installed. Install it now?"):
                core.installGm()
                self.notifyUser("PhotoImporter", f"You must restart PhotoImporter")
                return
            else:
                run_compress = False

        self.button_cancel_import.setEnabled(True)
        self.statusbar.showMessage("Importing Images")
        self.file_picker_src.setEnabled(False)
        self.file_picker_dst.setEnabled(False)
        self.button_import.setEnabled(False)

        workdir = self.file_picker_dst.text()

        QtWidgets.QApplication.processEvents()
        import_locations = self._getImportLocations()
        num_threads = settings.value('num_threads', 8, int)
        compression_quality = settings.value('compression_amount', 90.0, float)

        self.worker = core.Worker(workdir, num_threads, import_locations, run_compress, import_movies, compression_quality)
        self.worker.moveToThread(self.thread_import)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.prange.connect(self.progress_bar.setRange)
        self.worker.status.connect(self.statusbar.showMessage)
        self.worker.finished.connect(self._importThreadCompleted)
        self.worker.canceled.connect(self._taskCanceled)

        self.thread_import.started.connect(self.worker.run)
        self.thread_import.start()

    def _importThreadCompleted(self):
        self.thread_import.exit()
        self.thread_import.wait()
        self.say("Import Complete")
        self.file_picker_src.setEnabled(True)
        self.file_picker_dst.setEnabled(True)
        self.button_import.setEnabled(True)
        self.button_cancel_import.setEnabled(False)

    def _cancelImport(self):
        self.worker.cancel()

    def _taskCanceled(self):
        self.thread_import.quit()
        self.thread_import.wait()
        self.file_picker_src.setEnabled(True)
        self.file_picker_dst.setEnabled(True)
        self.button_import.setEnabled(True)
        self.button_cancel_import.setEnabled(False)
        self.statusbar.showMessage("Import canceled.")

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

        if "state" in settings.allKeys():
            self.restoreState(settings.value('state'))

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
        settings.setValue('state', self.saveState())
        settings.sync()

    def closeEvent(self, event):
        try:
            self.thread_import.quit()
            self.thread_import.wait()
        except:
            pass
        self._saveWidgetSettings()
        # super().closeEvent(event)
        super(MainWindow, self).closeEvent(event)

    def promptUser(self, title, question):
        # app = QtWidgets.QApplication.instance()  # checks if QApplication already exists
        # if not app:  # create QApplication if it doesnt exist
        #     app = QtWidgets.QApplication(sys.argv)

        response = QtWidgets.QMessageBox.question(
            None, title, question,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)

        if response == QtWidgets.QMessageBox.Yes:
            return True
        else:
            return False

    def notifyUser(self, title, message):
        msg_box = QtWidgets.QMessageBox()  # Create a new QMessageBox
        msg_box.setWindowTitle(title)  # Set the title for the message box
        msg_box.setText(message)  # Set the text for the message box
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)  # Add an OK button to the message box
        msg_box.exec()  # Execute the message box

    def say(self, msg):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        if settings.value('play_sound', True, bool):
            os.system(f'say {msg}')

    def _getImportLocations(self):

        selected_import_path = self.file_picker_src.text()
        import_folders = []
        if os.path.exists(selected_import_path) and "DCIM" in os.listdir(selected_import_path):
            dcim = os.path.join(selected_import_path, "DCIM")
            import_folders.extend(
                list(os.path.join(dcim, fuji) for fuji in os.listdir(dcim) if os.path.isdir(os.path.join(dcim, fuji))))

        workdir = self.file_picker_dst.text()
        jpg_dir = os.path.join(workdir, "JPG")
        compressed_dir = os.path.join(workdir, "Compressed")
        video_dir = os.path.join(workdir, "Video")

        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        import_movies = settings.value('import_movies', True, bool)
        run_compress = settings.value('compression_enabled', True, bool)

        if len(import_folders) < 1:
            self.notifyUser("PhotoImporter",
                            "No DCIM directories found in any volumes. Plug in a SD card.")
            return []

        if not os.path.exists(jpg_dir):
            if not self.promptUser("Photo Importer", f"Output directory {jpg_dir} does not exists. Would you like to create it?"):
                return []
            os.mkdir(jpg_dir)

        if not os.path.exists(compressed_dir) and run_compress is True:
            if not self.promptUser("Photo Importer", f"Output directory {compressed_dir} does not exists. Would you like to create it?"):
                return []
            os.mkdir(compressed_dir)

        if not os.path.exists(video_dir) and import_movies is True:
            if not self.promptUser("Photo Importer", f"Output directory {video_dir} does not exists. Would you like to create it?"):
                return []
            os.mkdir(video_dir)

        return import_folders


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('icon.png'))

    w = MainWindow()
    app.exec()
