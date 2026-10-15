FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The case-specific source is copied by the reviewed build context.
COPY . /app

# Case owners should replace this with the repository's pinned, reviewed
# dependency installation. No network is available during the default build.
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

ENTRYPOINT ["python"]
