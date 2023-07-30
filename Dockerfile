# FOR LOCAL DEVELOPER USE ONLY
# base image
FROM python:3.8
# # setup environment variable
ENV DockerHOME=/htb/

# # set work directory
RUN mkdir -p $DockerHOME

# # where your code lives
WORKDIR $DockerHOME

COPY pyproject.toml poetry.lock* $DockerHOME

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip

# run this command to install all dependencies
RUN pip install poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction \
    && rm -rf /root/.cache/pypoetry
RUN pip install psycopg2
# port where the Django app runs
EXPOSE 8000 5000 3000
