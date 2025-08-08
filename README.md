# NandS_BookAPIV.2

## Project Overview

This project provides a books API that will allow users to add, retrieve, reserve and edit books on a database. 

- [Contributing Guidelines](CONTRIBUTING.md)
- [License Information](LICENSE.md)

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python 3**: Version 3.7 or newer is recommended. You can download it from [python.org](https://www.python.org/downloads/).
*   **pip**: Python's package installer. It usually comes with Python installations.
*   **make**: A build automation tool. Pre-installed on macOS/Linux. Windows users may need to install it (e.g., via Chocolatey or WSL).
* [Docker](https://formulae.brew.sh/formula/docker)
* [Colima](https://github.com/abiosoft/colima) (for Mac/Linux users)
* [mongosh](https://www.mongodb.com/try/download/shell) (MongoDB shell client)
* *(Optional)* [MongoDB Compass](https://www.mongodb.com/try/download/compass) (GUI client)

## Getting Started

This project uses a `Makefile` to automate setup and common tasks.

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:methods/NandS_BookAPIV.2.git
    cd NandS_BookAPIV.2
    ```

2.  **View available commands:**
    To see a list of all available commands, run:
    ```bash
    make help
    ```

## Install Docker and Colima

This project requires MongoDB to be running locally. We recommend using **Docker** and **Colima** for a lightweight, consistent environment.

### Step 1: Install Colima

```bash
brew install colima
```

### Step 2: Install Docker

```bash
brew install docker
```
### Step 3: Setup and Run mongoDB

```bash
make mongo
```

### Step 4: Import sample data to mongoDB

```
make setup
```

### Step 5: Connect via `mongosh`

```
mongosh
```
This opens an interactive shell. You should see a connection string like:
```
mongodb://localhost:27017
```

### Step 6 (Optional): Use MongoDB Compass GUI

Open [MongoDB Compass](https://www.mongodb.com/try/download/compass)

Paste the connection string from `mongosh`:
`mongodb://localhost:27017`

Use Compass to explore, import JSON/CSV data, and manage your database visually.

## Common Commands

The `Makefile` will automatically create a virtual environment (`venv`) and install dependencies the first time you run a command.

## How to Run the API

To run the Flask application in debug mode:
```bash
make run
```
The API will be available at http://127.0.0.1:5000.

## API Documentation

This project uses the OpenAPI 3.0 standard for detailed API documentation. The full specification, which acts as the API's contract, is defined in the openapi.yml file.

This document is the single source of truth for:

* All available endpoints and their supported HTTP methods.
* The required request parameters and body schemas.
* The structure of all possible response objects, including error responses.
* The security schemes and which endpoints require authentication.

It is highly recommended to use an OpenAPI-compatible viewer to explore the API interactively. Many modern IDEs, such as VS Code (with the Swagger Viewer extension) and JetBrains IDEs, have built-in viewers that provide a "Try it out" feature for making live requests to the running application.

## Authentication and Authorization

This API now implements a robust authentication and authorization layer to protect sensitive endpoints.

### Authentication Flow

Authentication is handled via an OAuth 2.0 flow with Google as the identity provider. 
All write-access endpoints (POST, PUT, DELETE) require a user to be authenticated.
A user can authenticate by navigating to the following endpoint in their browser:

* GET http://localhost:5000/auth/login 

This will redirect the user to Google's sign-in page. 
After successful authentication and consent, the user will be redirected back to the application, 
and a secure session cookie will be set in their browser.

To log out and clear the current session, navigate to:

* GET http://localhost:5000/auth/logout

This will clear the user's session cookie and log them out of the application.

### Authorization (Role-Based Access Control)

Authorization is managed through a Role-Based Access Control (RBAC) system. 
When a new user signs in for the first time, they are automatically assigned a default role of viewer.
Certain API endpoints require specific roles to be accessed. 
These roles are checked on every request.

* viewer: The default role. Can access all public GET endpoints.
* editor: Can perform POST and PUT operations to create and update books.
* admin: Has all editor permissions and can also perform DELETE operations.

An administrator must manually update a user's roles array in the users collection in the MongoDB database to grant them elevated privileges.

### (Optional) How to Install the API dependencies without running it

```bash
make install
```

## How to Run Linting
This project uses **Pylint** to check code quality and style.

To run the linter, run the following command:

```bash
make lint
```

## How to Run Tests and Check Coverage
This project uses **coverage.py** to measure code coverage.

To run the test suite and see the coverage report:
```bash
make test
```

If old data is persisting, you can use an explicit
```bash
coverage erase
```
command to clean out the old data.

## Clean the Project

To remove the virtual environment and Python cache files:
```bash
make cleanup
```
This is useful if you want to start with a fresh environment.


## License
This project is licensed under the MIT License - see the LICENSE.md file for details.