#!/bin/bash

# Load environment variables for the mongoDB from .env in project root
if [ -f "../.env" ]; then
  source "../.env"
else
  echo "Error: .env file not found in project root directory."
  exit 1
fi

# Check the sample data file exists
if [ ! -f "test_data/sample_books.json" ]; then
  echo "Error: sample_books.json file not found in test_data directory."
  exit 1
fi

# Check if MongoDB is running
if ! mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    echo "Error: MongoDB is not running."
    exit 1
fi

# Check if documents already exist in the collection
EXISTING_DOCS=$(mongosh "$PROJECT_DATABASE" --eval "db.$PROJECT_COLLECTION.countDocuments({})" --quiet)

# Import the sample data into mongoDB if there are no EXISTING_DOCS
if [ "$EXISTING_DOCS" -eq 0 ]; then
  if mongoimport --db "$PROJECT_DATABASE" --collection "$PROJECT_COLLECTION" --file test_data/sample_books.json --jsonArray; then
    echo "Database '$PROJECT_DATABASE', collection '$PROJECT_COLLECTION' populated successfully."
  else
    echo "Error: Failed to populate the database."
      exit 1
  fi
else
  echo "There are already documents in the collection, please check. Skipping Insertion."
fi