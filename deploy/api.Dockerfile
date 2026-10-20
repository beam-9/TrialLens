FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home triallens \
    && mkdir /app/data \
    && chown triallens:triallens /app/data
COPY --chown=triallens:triallens apps/api/triallens ./triallens
USER triallens
EXPOSE 8000
CMD ["uvicorn", "triallens.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
