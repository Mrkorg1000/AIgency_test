FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTONUNBUFFERED=1

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY common/ ./common/

RUN cd common && pip install -e .

COPY intake_api/pyproject.toml intake_api/poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --only main

COPY intake_api/ ./intake_api/

WORKDIR /app/intake_api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

