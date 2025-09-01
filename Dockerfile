FROM python:3.9-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libblas-dev \
    liblapack-dev \
    gfortran \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt

# Install CPU torch compatible with py3.9 and SB3==1.6.2
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir torch==1.11.0 torchvision==0.12.0 \
  && pip install --no-cache-dir -r /app/requirements.txt \
  && pip install --no-cache-dir mplfinance==0.12.10b0

COPY . /app

# Default command is a no-op; use docker run with envs to execute run_portfolio.sh
CMD ["bash"]

