import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QProgressBar


class Worker(QObject):
    finished = Signal()
    progress = Signal(int)  # This will carry the progress increment

    def run(self):
        # Number of tasks
        num_tasks = 10
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.task, i) for i in range(num_tasks)]

            # Process completed tasks
            completed_tasks = 0
            for future in as_completed(futures):
                future.result()  # We wait for the result to ensure task completion
                completed_tasks += 1
                self.progress.emit((completed_tasks / num_tasks) * 100)  # Emit progress percentage

        self.finished.emit()

    def task(self, value):
        from time import sleep
        sleep(10)  # Simulate a task taking time
        return value * value


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('QThread with ThreadPoolExecutor Example')
        self.setGeometry(300, 300, 300, 150)
        self.widget = QWidget(self)
        self.layout = QVBoxLayout(self.widget)

        self.progressBar = QProgressBar(self)
        self.progressBar.setMaximum(100)  # Set to 100 for percentage
        self.layout.addWidget(self.progressBar)

        self.setCentralWidget(self.widget)

        # Set up the thread and worker
        self.thread = QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.worker.finished.connect(self.thread.quit)
        self.worker.progress.connect(self.updateProgressBar)
        self.thread.started.connect(self.worker.run)

        # Start the thread
        self.thread.start()

    def updateProgressBar(self, value):
        self.progressBar.setValue(int(value))

    def closeEvent(self, event):
        self.thread.quit()
        self.thread.wait()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
