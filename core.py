import os
import datetime
import subprocess
import re
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image


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


def _processImages(input_file, date_taken, output_jpg_file, output_compressed_file):
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


def _getOutputImageList(input_files, num_threads, workdir, progress_bar):
    jpg_dir = os.path.join(workdir, "JPG")
    compressed_dir = os.path.join(workdir, "Compressed")

    def _checkInputThread(input_file):
        date_taken, output_jpg_file, output_compressed_file = \
            getOutputImageNames(
                input_file, jpg_dir, compressed_dir)
        if not os.path.exists(output_compressed_file):
            return (input_file, date_taken, output_jpg_file, output_compressed_file)
        else:
            return None

    DEBUG = False
    output = []

    if DEBUG is True:
        progress_bar.setRange(0, len(input_files))
        counter = 0
        for input_file in input_files:
            date_taken, output_jpg_file, output_compressed_file = \
                getOutputImageNames(
                    input_file, jpg_dir, compressed_dir)
            if not os.path.exists(output_compressed_file):
                output.append(
                    (input_file, date_taken, output_jpg_file, output_compressed_file))
            counter += 1
            progress_bar.setValue(counter)
    else:
        # with tqdm.tqdm(total=len(input_files)) as pbar:
        progress_bar.setRange(0, len(input_files))
        counter = 0
        with ThreadPoolExecutor(max_workers=num_threads) as ex:
            futures = [
                ex.submit(_checkInputThread, input_file)
                for input_file in input_files
            ]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    output.append(result)
                    counter += 1
                    progress_bar.setValue(counter)
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


def _processMovies(outputs, statusbar, progress_bar):
    global DEBUG
    progress_bar.setRange(0, len(outputs))
    counter = 0
    for (input_file, date_taken, output_mov_file) in outputs:
        if not os.path.exists(os.path.dirname(output_mov_file)):
            os.mkdir(os.path.dirname(output_mov_file))

        shutil.copyfile(input_file, output_mov_file)
        statusbar.showMessage(f"Copying {input_file}, {output_mov_file}")
        counter += 1
        progress_bar.setValue(counter)


def runImport(import_locations, workdir, num_threads, statusbar, progress_bar):
    # import_locations = _getImportLocations()
    if len(import_locations) <= 0:
        return

    outputs = []
    input_files = _getInputFileList(import_locations, ".jpg")
    statusbar.showMessage(f"Checking {len(input_files)} images from input volume.")
    outputs = _getOutputImageList(input_files, num_threads, workdir, progress_bar)
    statusbar.showMessage(f"Importing {len(outputs)} images from input volume.")

    # Make the new directories in the main thread
    for input_file, date_taken, output_jpg_file, output_compressed_file in outputs:
        if not os.path.exists(os.path.dirname(output_jpg_file)):
            os.mkdir(os.path.dirname(output_jpg_file))
        if not os.path.exists(os.path.dirname(output_compressed_file)):
            os.mkdir(os.path.dirname(output_compressed_file))

    if len(outputs) > 0:
        progress_bar.setRange(0, len(outputs))
        counter = 0
        image_lists = _splitList(outputs, num_threads)
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(_processImages, input_file, date_taken, output_jpg_file, output_compressed_file)
                       for sublist in image_lists for input_file, date_taken, output_jpg_file, output_compressed_file in sublist]
            # Use as_completed to iterate over completed futures
            for future in as_completed(futures):
                try:
                    result = future.result()
                    counter += 1
                    progress_bar.setValue(counter)
                    if result is not None:
                        statusbar.showMessage(f"{result} failed to write.", file=sys.stderr)
                except Exception as e:
                    print("Exception:", e, file=sys.stderr)
                    traceback.print_exc()
    else:
        statusbar.showMessage("All images are up to date.")

    input_movies = _getInputFileList(import_locations, ".mov")
    statusbar.showMessage(f"Checking {len(input_movies)} movies from input volumes.")
    input_movies = _getInputFileList(import_locations, ".mov")
    output_movies = _getOutputMovieList(workdir, input_movies)
    statusbar.showMessage(f"Importing {len(output_movies)} movies from input volumes.")

    if len(output_movies) > 0:
        _processMovies(output_movies, statusbar, progress_bar)
    else:
        statusbar.showMessage("All movies are up to date.")

    statusbar.showMessage("Import complete.")
