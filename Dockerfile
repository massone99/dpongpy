FROM sunpeek/poetry:py3.11-slim

WORKDIR /app

# Install system dependencies for pygame
RUN apt-get update && apt-get install -y \
    python3-dev \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY poetry.lock pyproject.toml ./
RUN poetry install

# Run your app
COPY . /app
CMD [ "python -m", "dpongpy.etcd" ]