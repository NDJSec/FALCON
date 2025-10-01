# This file should be placed inside your new 'backend_src' directory.
FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Copy only the dependency definition file first to leverage Docker layer caching.
COPY pyproject.toml ./

# Install the project dependencies. The '.' tells pip to install the project
# defined by the pyproject.toml in the current directory.
RUN pip install --no-cache-dir .

# Copy the rest of the application code. This includes your 'backend' package.
COPY ./backend ./backend

# Expose the port the app runs on
EXPOSE 8000

# Run the uvicorn server. This command will now work correctly because
# the 'backend' package is properly installed and located.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
