FROM python:3.8

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# --- Install dependencies (not including dev dependencies) ---
RUN pip install pipenv
COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv lock -r > requirements.txt
RUN pip install -r requirements.txt
# PostgreSQL database adapter
RUN pip install psycopg2-binary
# HTTP server for production
RUN pip install gunicorn

# Copy code into working directory
COPY . .

# Hack the Back HTTP server instance should be running on port 8000
EXPOSE 8000
CMD ["gunicorn", "--bind", ":8000", "hacktheback.wsgi:application"]
