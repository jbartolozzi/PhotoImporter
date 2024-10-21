from setuptools import setup

APP = ['app.py']  # Change 'main.py' to the name of your main script
DATA_FILES = []

frameworks = [
    "/opt/homebrew/Cellar/libffi/3.4.6/lib/libffi.8.dylib",
]


OPTIONS = {
    'frameworks': frameworks,
    'argv_emulation': True,
    'packages': ['PySide6',
                 "concurrent",
                 "core",
                 "datetime",
                 "PIL",
                 "re",
                 "shutil",
                 "shutil",
                 "subprocess",
                 "traceback"],
    # 'resources': ["/opt/homebrew/Cellar/libffi/3.4.6/lib/libffi.8.dylib"],
    'iconfile': 'icon.icns',  # Path to your .icns icon file
}

setup(
    app=APP,
    name="PhotoImporter",  # Name your application
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
