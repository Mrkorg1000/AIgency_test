FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

# Общие пакеты (editable install)
COPY common/ ./common/
RUN cd common && pip install -e .

# Зависимости alembic-проекта
COPY alembic/pyproject.toml alembic/poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --only main

# Исходники alembic
COPY alembic/ ./alembic/

WORKDIR /app/alembic

# Команда по умолчанию переопределяется в docker-compose, но оставим безопасную
CMD ["alembic", "--help"]

