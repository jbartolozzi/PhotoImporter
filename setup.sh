#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}/python"

CONDA_DIR="${HOME}/conda/photoimporterdev"
if [ ! -d "${CONDA_DIR}" ]; then
    
    if [[ $(uname -m) == 'arm64' ]]; then
        wget https://repo.anaconda.com/miniconda/Miniconda3-py311_24.3.0-0-MacOSX-arm64.sh -O Miniconda3-latest-MacOSX.sh
    else
        wget https://repo.anaconda.com/miniconda/Miniconda3-py311_24.3.0-0-MacOSX-x86_64.sh -O Miniconda3-latest-MacOSX.sh
    fi
    /bin/bash ./Miniconda3-latest-MacOSX.sh -b -s -p "${CONDA_DIR}"

    ${CONDA_DIR}/bin/conda update -y conda 
    ${CONDA_DIR}/bin/conda install -y numpy pandas opencv pillow pyside6 --solver classic
    ${CONDA_DIR}/bin/conda install -y conda-forge::pyside6 --solver classic
    ${CONDA_DIR}/bin/conda install -y conda-forge::pyinstaller --solver classic
    yes | ${CONDA_DIR}/bin/pip install Pillow
    
    rm -f Miniconda3-latest-MacOSX.sh
fi

export PATH="${CONDA_DIR}/bin:$PATH"

pyinstaller PhotoImporter.spec --noconfirm
