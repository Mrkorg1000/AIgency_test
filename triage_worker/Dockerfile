FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTONUNBUFFERED=1

ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY ./common /common

COPY ./pyproject.toml ./poetry.lock ./

RUN pip install -e . && pip install -e /common

COPY . .

CMD ["python", "-m", "triage_worker.main"]