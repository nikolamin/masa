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

# Install CPU torch and pin build tools to support old gym packaging
RUN pip install --no-cache-dir "pip<24.1" "setuptools==59.8.0" "wheel==0.38.4" "packaging==21.3" \
  && (pip install --no-cache-dir --only-binary=:all: gym==0.21.0 || pip install --no-cache-dir gym==0.21.0) \
  && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch==1.11.0 torchvision==0.12.0 \
  && pip install --no-cache-dir -r /app/requirements.txt \
  && pip install --no-cache-dir mplfinance==0.12.10b0

COPY . /app

# Default command is a no-op; use docker run with envs to execute run_portfolio.sh
CMD ["bash"]

