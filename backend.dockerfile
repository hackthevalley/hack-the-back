FROM python:3.8

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN pip install poetry

# Install PostgreSQL database adapter
RUN pip install psycopg2-binary

# Install HTTP server for production
RUN pip install gunicorn

# Copy only requirements
WORKDIR /app
COPY pyproject.toml poetry.lock* /app/

# Initialize project
RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

# Copy code into working directory
COPY . /app

# Hack the Back HTTP server instance should be running on port 8000
EXPOSE 8000
CMD ["gunicorn", "--bind", ":8000", "hacktheback.wsgi:application"]
