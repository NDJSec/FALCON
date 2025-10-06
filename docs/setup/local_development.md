# Local Development Setup

This guide will walk you through setting up and running the complete FALCON application on your local machine for development.

## Prerequisites

- Docker and Docker Compose: The entire application is containerized. You must have Docker installed and running on your system. You can get it from the official Docker website.

## Running the Application

1. Clone the Repository: If you haven't already, clone the project repository to your local machine.

2. Navigate to Project Root: Open a terminal and `cd` into the root directory of the project (the same folder that contains `docker-compose.yaml`).

3. Build and Start Services: Run the following command. This will build the Docker images for all services and start them in the background.

    `docker-compose up --build`

    The first time you run this, it may take several minutes to download the base images and build all the services. Subsequent builds will be much faster.

4. Access the Services: Once all containers are running, you can access the different parts of the application:
    - Frontend UI: http://localhost:3001
    - Backend API: http://localhost:8000 (Chat backend API not available outside docker network in production)
    - Documentation Site: http://localhost:8008 (Currently not available)

## Creating a Test User

To use the application, you need a valid user token. You can insert a test user directly into the database with the following commands.

1. Connect to the database container:

    `docker-compose exec db psql -U postgres -d metrics`

2. Enable the UUID generation function (you only need to do this once):

    `CREATE EXTENSION IF NOT EXISTS "pgcrypto";`

3. Insert the test user:

    `INSERT INTO users (id, email, username, is_active) VALUES (gen_random_uuid(), 'test@example.com', 'test-token', true);`

4. Exit the SQL shell:

    `\q`

You can now use test-token in the user token field on the frontend to log in.