FROM python:3.11-slim

WORKDIR /action

# Install git and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /action/
RUN pip install --no-cache-dir -r /action/requirements.txt

COPY review_prompt.md /action/
COPY src /action/src

ENV PYTHONPATH="/action/src/code_review"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/action/src/code_review/review.py"]
