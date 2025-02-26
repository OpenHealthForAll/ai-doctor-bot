FROM python:3.12

# Install poetry
RUN pip install -U poetry

# Working directory
WORKDIR /app

# Copy poetry files
COPY poetry.lock pyproject.toml /app/

# Install dependencies
RUN poetry install --no-root

# Copy the rest of the files
COPY . /app

# Generate Prisma client
RUN poetry run prisma generate

# Run the application
CMD ["poetry", "run", "python", "app.py"]