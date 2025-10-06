# Running Tests

The FALCON backend includes a suite of unit and integration tests built with `pytest`. These tests are designed to run inside the backend's Docker container to ensure a consistent testing environment.

## Running the Test Suite

1. **Ensure Containers are Running**: Before running the tests, make sure your application stack is running. You can start it with:

    ```bash
    docker-compose up -d
    ```

    (The `-d` flag runs the containers in detached mode).

2. **Execute Pytest in the Container**: Use the `docker-compose exec` command to run `pytest` inside the `falcon_ai` service container. This command will discover and run all tests located in the `backend_src/tests` directory.

    ```bash
    docker-compose exec falcon_ai pytest
    ```

You will see the output from `pytest` directly in your terminal, indicating which tests passed and which failed.

## Writing New Tests

- All test files should be placed in the `backend_src/tests/` directory.
- Test filenames must start with `test_`.
- Test function names must start with `test_`.
- Fixtures for setting up test conditions (like a database session or a test client) are defined in `backend_src/tests/conftest.py`. You can use these fixtures in your test functions by adding them as arguments.