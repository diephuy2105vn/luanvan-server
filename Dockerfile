FROM python:3.11.4-slim-bullseye as base

ENV POETRY_VERSION=1.4.2

# Install dependencies
RUN apt-get update \
 && apt-get install -y curl build-essential \
 && curl -sSL https://install.python-poetry.org | python3 - \
 && ln -s /root/.local/bin/poetry /usr/local/bin/poetry \
 && poetry config virtualenvs.create false

# Copy and install dependencies
WORKDIR /app/src
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main

# Copy source code
COPY . .

FROM base as prod
CMD ["python", "-m", "server"]


FROM base as dev
RUN poetry install
