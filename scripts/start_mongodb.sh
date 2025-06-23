#!/bin/bash

# Check if MongoDB is already running
if mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    echo "MongoDB is already running."
    exit 1
fi

# Check if colima is installed
if ! command -v colima >/dev/null 2>&1; then
  echo "Error: Colima is not installed. Please install Colima first."
  exit 1
fi

# Check if docker is installed
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed. Please install Colima first."
  exit 1
fi

# Check if colima is already running
if colima status | grep -q "running"; then
  echo "Colima is already running, continuing..."
else
  # Start colima
  echo "Starting colima..."
  colima start >/dev/null 2>&1
  # Check if colima is running
  if [ $? -ne 0 ]; then
    echo "Error: failed to start colima."
    exit 1
  fi
fi

# Check if the mongoDB Docker image has already been pulled
if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "mongodb/mongodb-community-server:latest"; then
  echo "MongoDB Docker image has already been pulled, continuing..."
else
  if ! docker pull mongodb/mongodb-community-server:latest; then
    echo "Error: Failed to pull MongoDB Docker image."
    exit 1
  fi
fi

# Check if a Docker container named "mongodb" already exists
if docker ps -a --format "{{.Names}}" | grep -q "mongodb"; then
  echo "A container with the name 'mongodb' already exists."

  # Check if the mongodb container is already running
  if docker ps --format "{{.Names}}" | grep -q "mongodb"; then
    echo "The container 'mongodb' is already running, exiting..."
    exit 0
  else
    echo "Starting the existing container 'mongodb'..."
    if ! docker start mongodb; then
      echo "Error: Failed to start the existing container."
      exit 1
    else
      echo "MongoDB is now running."
      exit 0
    fi
  fi
fi

# Start a new docker container using the mongoDB Docker image
echo "Starting docker container with mongoDB Docker image..."
docker run --name mongodb -p 27017:27017 -d mongodb/mongodb-community-server:latest

# Check if MongoDB is running correctly
if mongosh --eval "db.adminCommand('ping')" >/dev/null 2>&1; then
    echo "MongoDB is now running."
    exit 0
else
  echo "Error: MongoDB failed to initialise."
  exit 1
fi




