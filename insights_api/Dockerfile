FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTONUNBUFFERED=1

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY common/ ./common/

RUN cd common && pip install -e .

COPY insights_api/pyproject.toml insights_api/poetry.lock ./

RUN poetry config virtualenvs.create false && poetry install --only main

COPY insights_api/ ./insights_api/

WORKDIR /app/insights_api

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

