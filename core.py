import os
import datetime
import subprocess
import re
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from PySide6.QtCore import QObject, Signal


def _splitList(input_list, n):
    # Calculate the size of each sublist
    k, m = divmod(len(input_list), n)
    # Create the sublists
    sublists = [input_list[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]
    return sublists


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


def ymdToMdy(ymd):
    parsed = datetime.datetime.strptime(ymd, '%Y/%m/%d %H:%M:%S')
    return parsed.strftime('%m/%d/%Y %H:%M:%S')


def getFileList(directory):
    if os.path.exists(directory):
        return list(os.path.join(root, file) for root, dirs, files in os.walk(directory) for file in files)
    else:
        return []


def runCommand(command):
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_output, cmd_err = process.communicate()
    return (cmd_output.decode("utf-8").strip(), cmd_err.decode("utf-8").strip())


def getOutputImageNames(input_file, output_jpg_dir, output_compressed_dir):
    date_taken = getDateTaken(input_file)
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


def _getOutputMovieNames(input_file, movie_dir):
    date_taken = getDateTaken(input_file)
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


def _getOutputMovieList(workdir, input_files):
    mov_dir = os.path.join(workdir, "Video")
    output = []
    # for input_file in tqdm.tqdm(input_files):
    for input_file in input_files:
        date_taken, output_mov_file = _getOutputMovieNames(input_file, mov_dir)
        if not os.path.exists(output_mov_file):
            output.append((input_file, date_taken, output_mov_file))
    return output





def _getInputFileList(import_locations, file_type):
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


class Worker(QObject):
    progress = Signal(int)  # Signal to emit progress
    status = Signal(str)
    prange = Signal(int, int)
    finished = Signal()
    canceled = Signal()

    def __init__(self, workdir, num_threads, import_locations):
        super().__init__()
        self.is_canceled = False
        self.workdir = workdir
        self.num_threads = num_threads
        self.import_locations = import_locations

    def cancel(self):
        self.is_canceled = True

    def run(self):

        src_files = self.getAllSrcImageFiles(self.import_locations, self.workdir)

        self.prange.emit(0, len(src_files))
        new_source_images_tuple = self.getNewSrcImageFiles(
            src_files, self.num_threads, self.workdir)
        self.progress.emit(0)

        if len(new_source_images_tuple) > 0:
            self.prange.emit(0, len(new_source_images_tuple))
            self.runImageImport(new_source_images_tuple, self.workdir, self.num_threads)
            self.progress.emit(len(new_source_images_tuple))
        else:
            self.status.emit(f"All images up to date.")
            self.prange.emit(0, 1)
            self.progress.emit(0)
        self.finished.emit()

    def _processImages(self, input_file, date_taken, output_jpg_file, output_compressed_file):
        if self.is_canceled:
            return
        shutil.copyfile(input_file, output_jpg_file)
        runCommand(
            f"/opt/homebrew/bin/gm convert -quality 90% {input_file} {output_compressed_file}")

        if os.path.exists(output_compressed_file):
            runCommand("SetFile -d \"%s\" \"%s\"" %
                       (ymdToMdy(date_taken), output_compressed_file))

        if os.path.exists(output_jpg_file):
            runCommand("SetFile -d \"%s\" \"%s\"" %
                       (ymdToMdy(date_taken), output_jpg_file))

        else:
            print(f"Error: output file {output_compressed_file} not found. Exiting.")
            return

    def _processMovies(self, outputs):
        # progress_bar.setRange(0, len(outputs))
        counter = 0
        for (input_file, date_taken, output_mov_file) in outputs:
            if not os.path.exists(os.path.dirname(output_mov_file)):
                os.mkdir(os.path.dirname(output_mov_file))

            shutil.copyfile(input_file, output_mov_file)
            # statusbar.showMessage(f"Copying {input_file}, {output_mov_file}")
            counter += 1
            # progress_bar.setValue(counter)

    def _getOutputImageList(self, input_files, num_threads, workdir):
        jpg_dir = os.path.join(workdir, "JPG")
        compressed_dir = os.path.join(workdir, "Compressed")

        def _checkInputThread(input_file):
            if self.is_canceled:
                self.canceled.emit()
                return None
            date_taken, output_jpg_file, output_compressed_file = \
                getOutputImageNames(
                    input_file, jpg_dir, compressed_dir)
            if not os.path.exists(output_compressed_file):
                return (input_file, date_taken, output_jpg_file, output_compressed_file)
            else:
                return None

        output = []
        counter = 0
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(_checkInputThread, input_file)
                for input_file in input_files
            ]
            for future in as_completed(futures):
                if self.is_canceled:
                    executor.shutdown(wait=False)
                    break
                result = future.result()
                counter += 1
                self.progress.emit(counter)
                if result is not None:
                    output.append(result)

            if self.is_canceled:
                self.canceled.emit()

        return output

    def getAllSrcImageFiles(self, import_locations, workdir):
        if len(import_locations) <= 0:
            return []
        return _getInputFileList(import_locations, ".jpg")

    def getNewSrcImageFiles(self, input_files, num_threads, workdir):
        jpg_dir = os.path.join(workdir, "JPG")
        compressed_dir = os.path.join(workdir, "Compressed")

        def _checkInputThread(input_file):
            if self.is_canceled:
                self.canceled.emit()
                return None
            date_taken, output_jpg_file, output_compressed_file = \
                getOutputImageNames(
                    input_file, jpg_dir, compressed_dir)
            if not os.path.exists(output_compressed_file):
                return (input_file, date_taken, output_jpg_file, output_compressed_file)
            else:
                return None

        output = []
        counter = 0
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(_checkInputThread, input_file)
                for input_file in input_files
            ]
            for future in as_completed(futures):
                if self.is_canceled:
                    executor.shutdown(wait=False)
                    break

                result = future.result()
                counter += 1
                self.progress.emit(counter)
                if result is not None:
                    output.append(result)

            if self.is_canceled:
                self.canceled.emit()
        return output

    def runImageImport(self, new_source_images_tuple, workdir, num_threads):
        if len(new_source_images_tuple) <= 0:
            return

        # Make the new directories in the main thread
        for input_file, date_taken, output_jpg_file, output_compressed_file in new_source_images_tuple:
            if not os.path.exists(os.path.dirname(output_jpg_file)):
                os.mkdir(os.path.dirname(output_jpg_file))
            if not os.path.exists(os.path.dirname(output_compressed_file)):
                os.mkdir(os.path.dirname(output_compressed_file))

        if len(new_source_images_tuple) > 0:
            # progress_bar.setRange(0, len(new_source_images_tuple))
            counter = 0
            image_lists = _splitList(new_source_images_tuple, num_threads)
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(self._processImages, input_file, date_taken, output_jpg_file, output_compressed_file)
                           for sublist in image_lists for input_file, date_taken, output_jpg_file, output_compressed_file in sublist]
                # Use as_completed to iterate over completed futures
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        counter += 1
                        self.progress.emit(counter)
                        if result is not None:
                            self.status.emit(f"{result} failed to write.", file=sys.stderr)
                    except Exception as e:
                        print("Exception:", e, file=sys.stderr)
                        traceback.print_exc()
        else:
            self.status.emit("All images are up to date.")

        # input_movies = _getInputFileList(import_locations, ".mov")
        # statusbar.showMessage(f"Checking {len(input_movies)} movies from input volumes.")
        # input_movies = _getInputFileList(import_locations, ".mov")
        # output_movies = _getOutputMovieList(workdir, input_movies)
        # statusbar.showMessage(f"Importing {len(output_movies)} movies from input volumes.")

        # if len(output_movies) > 0:
        #     _processMovies(output_movies, statusbar, progress_bar)
        # else:
        #     statusbar.showMessage("All movies are up to date.")

        # statusbar.showMessage("Import complete.")
