#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}/python"

# Environment name
ENV_NAME="photoimporter"

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Miniconda or Anaconda first."
    echo "Visit https://docs.conda.io/en/latest/miniconda.html for installation instructions."
    exit 1
fi

# Check if the environment already exists
if conda info --envs | grep -q "$ENV_NAME"; then
    echo "Environment '$ENV_NAME' already exists. Activating..."
    conda activate $ENV_NAME
else
    echo "Creating new conda environment: $ENV_NAME"
    conda create -n $ENV_NAME python=3.10 -y

    # Activate the environment
    echo "Activating conda environment: $ENV_NAME"
    conda activate $ENV_NAME

    conda install -y numpy pandas opencv pillow pyside6
    conda install -y conda-forge::pyside6 conda-forge::pyinstaller
    pip install --upgrade pip
    pip install --no-cache-dir -r requirements.txt

fi

echo ""
echo "Setup complete!"
echo "The environment '$ENV_NAME' is now active."
echo ""
echo "When you're done, deactivate the environment with:"
echo "conda deactivate"
echo ""
echo "To create a standalone executable, run:\npyinstaller PhotoImporter.spec --noconfirm"
