FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY common/ ./common/

RUN cd common && pip install -e .

COPY triage_worker/pyproject.toml triage_worker/poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --only main

COPY triage_worker/ ./triage_worker/

WORKDIR /app/triage_worker

CMD ["python", "-m", "main"]