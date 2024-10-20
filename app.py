#!/usr/bin/env python3
import datetime
import os
import re
import shutil
import subprocess
import sys
import time
import tqdm
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from PySide6 import QtWidgets, QtCore, QtGui

NUM_THREADS = int(os.getenv("FUJI_IMPORT_THREADS", "8"))
WORKDIR = os.getenv("FUJI_IMPORT_DIR", os.path.expandvars("$HOME/Pictures/Fuji"))
JPG_DIR = os.path.join(WORKDIR, "JPG")
COMPRESSED_DIR = os.path.join(WORKDIR, "Compressed")
MOV_DIR = os.path.join(WORKDIR, "Video")


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
        # hbox.addWidget(self.status_label)
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


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Settings")
        layout = QtWidgets.QVBoxLayout(self)

        # Integer SpinBox for number of threads
        self.thread_spinbox = QtWidgets.QSpinBox(self)
        self.thread_spinbox.setRange(1, 64)  # Assuming 1 to 64 threads
        self.thread_spinbox.setValue(8)  # Default value
        layout.addWidget(QtWidgets.QLabel("Number of Threads:"))
        layout.addWidget(self.thread_spinbox)

        # Double SpinBox for compression amount (float)
        self.compression_spinbox = QtWidgets.QDoubleSpinBox(self)
        self.compression_spinbox.setRange(0.0, 100.0)  # Compression range
        self.compression_spinbox.setSingleStep(1.0)
        self.compression_spinbox.setValue(90.0)  # Default value
        layout.addWidget(QtWidgets.QLabel("Compression Amount (%):"))
        layout.addWidget(self.compression_spinbox)

        # CheckBox for playing a sound
        self.sound_checkbox = QtWidgets.QCheckBox("Play Sound on Completion", self)
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

    def saveSettings(self):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        settings.setValue('num_threads', self.thread_spinbox.value())
        settings.setValue('compression_amount', self.compression_spinbox.value())
        settings.setValue('play_sound', self.sound_checkbox.isChecked())

    def load_settings(self):
        settings = QtCore.QSettings('rischio', 'PhotoImporter')
        self.thread_spinbox.setValue(settings.value('num_threads', 4, int))
        self.compression_spinbox.setValue(settings.value('compression_amount', 50.0, float))
        self.sound_checkbox.setChecked(settings.value('play_sound', True, bool))


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

        self.widget_import = self._createImportWidget()
        self.widget_organize = self._createOrganizeWidget()

        self.tab_widget.addTab(self.widget_import, "Import")
        self.tab_widget.addTab(self.widget_organize, "Organize")

        menu_bar = QtWidgets.QMenuBar(self)
        self.setMenuBar(menu_bar)
        settings_menu = menu_bar.addMenu("Settings")
        settings_action = QtGui.QAction("Preferences...", self)
        settings_action.setShortcut("Meta+,")
        settings_action.triggered.connect(self._openSettings)
        settings_menu.addAction(settings_action)

        self.setCentralWidget(self.tab_widget)

        self._loadWidgetSettings()

        self.show()

    def _openSettings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _createImportWidget(self):
        widget_container = QtWidgets.QWidget()
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
        self.storage_bar.setTextVisible(True)
        self.storage_bar.setFormat("Free %p%")
        hbox_storage.addWidget(label_storage)
        hbox_storage.addWidget(self.storage_bar)
        widget_storage.setLayout(hbox_storage)

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

        self.button_import = QtWidgets.QPushButton("Import")
        self.button_import.clicked.connect(self._runImport)
        self.button_import.setEnabled(False)

        vbox_layout = QtWidgets.QVBoxLayout()
        vbox_layout.addWidget(self.file_picker_src)
        vbox_layout.addWidget(widget_storage)
        vbox_layout.addWidget(self.file_picker_dst)
        vbox_layout.addWidget(self.button_import)
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
        directory = os.path.abspath(self.file_picker_src.text())
        if not os.path.exists(directory):
            used_percentage = 0
        else:
            total, used, free = shutil.disk_usage(directory)
            used_percentage = (used / total) * 100
        self.storage_bar.setToolTip(f"{used_percentage}% Used")
        self.storage_bar.setValue(used_percentage)

    def _runImport(self):
        self.statusbar.showMessage("Importing Images")
        self.file_picker_src.setEnabled(False)
        self.file_picker_dst.setEnabled(False)
        self.button_import.setEnabled(False)

        QtWidgets.QApplication.processEvents()
        for widget in list(widget for (name, widget) in vars(self).items()
                           if isinstance(widget, QtWidgets.QWidget)):
            widget.repaint()

        time.sleep(3)
        self.file_picker_src.setEnabled(True)
        self.file_picker_dst.setEnabled(True)
        self.button_import.setEnabled(True)
        self.say("Import Complete")
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

    def getDateTaken(path):
        if path.lower().endswith(".mov"):
            c_timestamp = os.path.getctime(path)
            c_datestamp = datetime.datetime.fromtimestamp(c_timestamp)
            output = c_datestamp.strftime('%Y/%m/%d %H:%M:%S')
        else:
            exif = Image.open(path)._getexif()
            if not exif:
                raise Exception('Image {0} does not have EXIF data.'.format(path))
                return
            result = datetime.datetime.strptime(exif[36867], "%Y:%m:%d %H:%M:%S")
            output = result.strftime('%Y/%m/%d %H:%M:%S')

        return output

    def ymdToMdy(self, ymd):
        parsed = datetime.datetime.strptime(ymd, '%Y/%m/%d %H:%M:%S')
        return parsed.strftime('%m/%d/%Y %H:%M:%S')

    def getFileList(self, directory):
        if os.path.exists(directory):
            return list(os.path.join(root, file) for root, dirs, files in os.walk(directory) for file in files)
        else:
            return []

    def runCommand(self, command):
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        cmd_output, cmd_err = process.communicate()
        return (cmd_output.decode("utf-8").strip(), cmd_err.decode("utf-8").strip())

    def say(self, msg):
        os.system(f'say {msg}')

    def getImportLocations(self):
        import_locations = []
        volumes = "/Volumes"
        for volume in os.listdir(volumes):
            try:
                if "DCIM" in os.listdir(os.path.join(volumes, volume)):
                    dcim = os.path.join(volumes, volume, "DCIM")
                    import_locations.extend(
                        list(os.path.join(dcim, fuji) for fuji in os.listdir(dcim)))
            except PermissionError:
                # print("%s %s" % (color(f"Unable to read", "red"), color(volume, "bold")))
                pass

        return import_locations

    def getOutputImageNames(self, input_file, output_jpg_dir, output_compressed_dir):
        date_taken = self.getDateTaken(input_file)
        date_folder = date_taken.split(" ")[0].replace("/", "_")

        file_name = os.path.basename(input_file).replace("DSCF", "")
        file_number = re.findall(r'\d+', file_name)[-1]
        fuji_folder = os.path.basename(os.path.dirname(input_file))
        folder_numbers = re.findall(r'\d+', fuji_folder)

        if len(folder_numbers) > 0:
            combined_name = date_folder + "_" + \
                file_name.replace(file_number, folder_numbers[0] + file_number)
        else:
            combined_name = date_folder + "_" + file_name

        combined_name = combined_name
        output_jpg_file = os.path.join(
            output_jpg_dir, date_folder, combined_name)

        output_compressed_file = os.path.join(
            output_compressed_dir, date_folder,
            combined_name.replace(".JPG", ".jpg").replace(".jpg", "c.jpg"))

        return date_taken, output_jpg_file, output_compressed_file

    def _getOutputImageList(self, input_files):
        def _checkInputThread(input_file):
            date_taken, output_jpg_file, output_compressed_file = \
                self.getOutputImageNames(
                    input_file, JPG_DIR, COMPRESSED_DIR)
            if not os.path.exists(output_compressed_file):
                return (input_file, date_taken, output_jpg_file, output_compressed_file)
            else:
                return None

        global DEBUG
        output = []

        if DEBUG is True:

            print("Checking images using single thread.")
            for input_file in tqdm.tqdm(input_files):
                date_taken, output_jpg_file, output_compressed_file = \
                    self.getOutputImageNames(
                        input_file, JPG_DIR, COMPRESSED_DIR)
                if not os.path.exists(output_compressed_file):
                    output.append(
                        (input_file, date_taken, output_jpg_file, output_compressed_file))

        else:
            with tqdm.tqdm(total=len(input_files)) as pbar:
                with ThreadPoolExecutor(max_workers=NUM_THREADS) as ex:
                    futures = [
                        ex.submit(_checkInputThread, input_file)
                        for input_file in input_files
                    ]
                    for future in as_completed(futures):
                        result = future.result()
                        if result is not None:
                            output.append(result)
                        pbar.update(1)
        return output

    def _getOutputMovieNames(self, input_file, movie_dir):
        date_taken = self.getDateTaken(input_file)
        date_folder = date_taken.split(" ")[0].replace("/", "_")

        file_name = os.path.basename(input_file)
        file_number = re.findall(r'\d+', file_name)[-1]

        fuji_folder = os.path.basename(os.path.dirname(input_file))
        folder_numbers = re.findall(r'\d+', fuji_folder)

        if len(folder_numbers) > 0:
            combined_name = date_folder + "_" + \
                file_name.replace(file_number, "_" + folder_numbers[0] + file_number)
        else:
            combined_name = date_folder + "_" + file_name

        output_mov_file = os.path.join(
            movie_dir, date_folder, combined_name)

        return date_taken, output_mov_file

    def _getOutputMovieList(self, input_files):
        output = []
        for input_file in tqdm.tqdm(input_files):
            date_taken, output_mov_file = self._getOutputMovieNames(input_file, MOV_DIR)
            if not os.path.exists(output_mov_file):
                output.append((input_file, date_taken, output_mov_file))
        return output

    def _getImportLocations(self):
        import_locations = self.getImportLocations()
        if len(import_locations) < 1:
            # print(color("No DCIM directories found in any volumes.", "bold"))
            # print("... plug in a %s." % color("SD card", "underline"))
            return []

        if not os.path.exists(JPG_DIR):
            # if not promptUser(f"Output directory {JPG_DIR} does not exists. Would you like to create it?"):
            #     return []
            os.mkdir(JPG_DIR)

        if not os.path.exists(COMPRESSED_DIR):
            # if not promptUser(f"Output directory {COMPRESSED_DIR} does not exists. Would you like to create it?"):
            #     return []
            os.mkdir(COMPRESSED_DIR)

        # print("Importing data from\n%s" % "\n".join(
        #     list(color(location, "bold")
        #          for location in import_locations)))
        return import_locations

    def _getInputFileList(self, import_locations, file_type):
        output = []
        for import_location in import_locations:
            output.extend(
                sorted(
                    list(os.path.join(import_location, file)
                         for file in os.listdir(import_location)
                         if (file.endswith(file_type) or file.endswith(file_type.upper()))
                         and not file.startswith(".")
                         )))
        return output

    def _splitList(self, input_list, n):
        # Calculate the size of each sublist
        k, m = divmod(len(input_list), n)
        # Create the sublists
        sublists = [input_list[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]
        return sublists

    def _processImages(self, args):
        input_file, date_taken, output_jpg_file, output_compressed_file = args
        if DEBUG is True:
            print(f"Copying {input_file}, {output_jpg_file}")
            print(
                f"/opt/homebrew/bin/gm convert -quality 90% {input_file} {output_compressed_file}")

        # Cant make directories on multiple threads
        # if not os.path.exists(os.path.dirname(output_jpg_file)):
        #     os.mkdir(os.path.dirname(output_jpg_file))
        # if not os.path.exists(os.path.dirname(output_compressed_file)):
        #     os.mkdir(os.path.dirname(output_compressed_file))

        shutil.copyfile(input_file, output_jpg_file)
        self.runCommand(
            f"/opt/homebrew/bin/gm convert -quality 90% {input_file} {output_compressed_file}")

        if os.path.exists(output_compressed_file):
            self.runCommand("SetFile -d \"%s\" \"%s\"" %
                            (self.ymdToMdy(date_taken), output_compressed_file))

        if os.path.exists(output_jpg_file):
            self.runCommand("SetFile -d \"%s\" \"%s\"" %
                            (self.ymdToMdy(date_taken), output_jpg_file))

        else:
            print(f"Error: output file {output_compressed_file} not found. Exiting.")
            return

    def _processMovies(self, outputs):
        global DEBUG
        for (input_file, date_taken, output_mov_file) in tqdm.tqdm(outputs):
            if DEBUG is True:
                print(f"Copying {input_file}, {output_mov_file}")
            else:
                if not os.path.exists(os.path.dirname(output_mov_file)):
                    os.mkdir(os.path.dirname(output_mov_file))

                shutil.copyfile(input_file, output_mov_file)

    def runImport(self, args):

        # print("Copying images to %s" % color(JPG_DIR, "bold"))
        # print("Writing compressed images to %s" % color(COMPRESSED_DIR, "bold"))

        import_locations = self._getImportLocations()
        if len(import_locations) <= 0:
            return

        outputs = []
        input_files = self._getInputFileList(import_locations, ".jpg")

        # print("Checking %s images from input volumes." % color(len(input_files), "bold"))
        outputs = self._getOutputImageList(input_files)
        # print("Importing %s images from input volumes." % color(len(outputs), "bold"))

        # Make the new directories in the main thread
        for input_file, date_taken, output_jpg_file, output_compressed_file in outputs:
            if not os.path.exists(os.path.dirname(output_jpg_file)):
                os.mkdir(os.path.dirname(output_jpg_file))
            if not os.path.exists(os.path.dirname(output_compressed_file)):
                os.mkdir(os.path.dirname(output_compressed_file))

        if len(outputs) > 0:
            progress_bar = tqdm.tqdm(total=len(outputs),
                                     desc=f"Importing images", unit="image")
            if DEBUG:
                for args in outputs:
                    progress_bar.update(1)
                    self._processImages(args)
            else:
                image_lists = self._splitList(outputs, NUM_THREADS)
                with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
                    futures = [executor.submit(self._processImages, args)
                               for sublist in image_lists for args in sublist]
                    # Use as_completed to iterate over completed futures
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            progress_bar.update(1)
                            if result is not None:
                                print(f"{result} failed to write.", file=sys.stderr)
                        except Exception as e:
                            print("Exception:", e, file=sys.stderr)
                            traceback.print_exc()
        else:
            # print(color("All images are up to date.", "green"))
            pass
        input_movies = self._getInputFileList(import_locations, ".mov")

        # print("Checking %s movies from input volumes." % color(len(input_movies), "bold"))
        input_movies = self._getInputFileList(import_locations, ".mov")
        output_movies = self._getOutputMovieList(input_movies)
        # print("Importing %s movies from input volumes." % color(len(output_movies), "bold"))

        if len(output_movies) > 0:
            self._processMovies(output_movies)
        else:
            # print(color("All movies are up to date.", "green"))
            pass

        # for import_location in import_locations:
        # printDiskUsage(import_locations[0])

        # print(color("Import complete.", "green"))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('icon.png'))  # Optionally set the application icon
    w = MainWindow()
    app.exec()
