#!/bin/bash

# Run pylint on the folder ignoring virtual environment folder
pylint --ignore=venv .
# Check the exit code to determine if Pylint passed or failed
if [ $? -eq 0 ]; then
    echo "Pylint passed successfully on all files."
else
    echo "Pylint found issues. Please fix them."
    exit 1
fi