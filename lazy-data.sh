#!/bin/bash

# Path to your virtual environment
VENV_PATH="/opt/lazy-macro/venv"

# Path to your Python script
SCRIPT_PATH="/opt/lazy-macro/lazy-macro.py"

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Run the Python script and capture the output
DATA=$(python3 "$SCRIPT_PATH")

# Print the output
echo "document.writeln (\"$DATA\")"

# Deactivate the virtual environment
deactivate
