#!/bin/bash

# Load environment variables for the mongoDB from .env in project root
if [ -f "../.env" ]; then
  source "../.env"
else
  echo "Error: .env file not found in project root directory."
  exit 1
fi

# Check if MongoDB is running
if ! mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    echo "Error: MongoDB is not running."
    exit 1
fi

# Check if there are any documents in the collection
EXISTING_DOCS=$(mongosh "$PROJECT_DATABASE" --eval "db.$PROJECT_COLLECTION.countDocuments({})" --quiet)

# Import the sample data into mongoDB if there are no EXISTING_DOCS
if [ "$EXISTING_DOCS" -eq 0 ]; then
    echo "Collection: '$PROJECT_COLLECTION' is empty."
    exit 0
else
    echo "Database:'$PROJECT_DATABASE' Collection:'$PROJECT_COLLECTION' contains '$EXISTING_DOCS' objects. Proceed with delete? (Y/N)"
    read -r CONFIRMATION
    if [[ "$CONFIRMATION" =~ ^[Yy]$ ]]; then
      if mongosh "$PROJECT_DATABASE" --eval "db.$PROJECT_COLLECTION.deleteMany({})" --quiet; then
        echo "All documents in '$PROJECT_COLLECTION' have been deleted."
        exit 0
      else
        echo "Error: Failed to delete documents."
        exit 1
      fi
    else
      echo "Deletion cancelled by user."
      exit 0
    fi
fi

