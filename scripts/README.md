# Scripts Folder

This folder contains various shell scripts to manage and maintain the project. Below is a summary of each script and its purpose.

## Scripts

### `create_resources.sh`

This script populates a MongoDB collection with sample data from a JSON file, ensuring no duplicates are created.

### `delete_resources.sh`

This script deletes all documents from a specified MongoDB collection after confirming with the user.

### `run_pylint.sh`

This script runs Pylint on the project to check for code quality and style issues.

### `run_tests.sh`

This script runs tests using pytest with coverage and generates coverage reports.

### MongoDB Docker Setup Script

This script automates the setup and initialization of a MongoDB Docker container.

## Usage

To run the scripts, use the Makefile in the root directory. The Makefile provides targets for various tasks, including running the Flask app, running tests, linting, and more.

### Makefile Targets

- **`make run`:** Run the Flask app.
- **`make test`:** Run tests and generate a coverage report.
- **`make lint`:** Run the Pylint linter.
- **`make books`:** Populate the MongoDB collection with sample data.
- **`make clean`:** Remove all documents from the specified MongoDB collection.
- **`make help`:** Show the help message with available Makefile commands.
- **`make install`:** Set up the virtual environment and install dependencies.
- **`make cleanup`:** Clean up the project by removing the virtual environment and cache files.

### Requirements

- Ensure MongoDB is running and accessible.
- Ensure the .env file is properly configured with the necessary environment variables.
- Ensure the sample_books.json file is present in the test_data directory for the create_resources.sh script.

### Notes

- Make sure to give execute permissions to the scripts using chmod +x script_name.sh.
- These scripts are designed to be run using the Makefile targets. Ensure you are using the correct commands from the root directory.
