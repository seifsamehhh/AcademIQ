# AcademIQ ML service — Hugging Face Docker Space
# Build from monorepo root:
#   docker build -f ml-service/Dockerfile -t academiq-ml .
# Or from ml-service/ after copying models into ml-service/models/performance_model:
#   docker build -t academiq-ml .

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/app/models/performance_model \
    PORT=7860

COPY ml-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml-service/app ./app

# Artifacts: copy from monorepo models/ (adjust if deploying ml-service as standalone repo)
COPY models/performance_model ./models/performance_model

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
