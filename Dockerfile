FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/code

WORKDIR /code

COPY app/requirements.txt ./app/requirements.txt

RUN pip install --no-cache-dir -r ./app/requirements.txt

COPY app/ ./app/

EXPOSE 8001

CMD ["python", "-m", "app.main"]
