FROM python:3.11

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

# Install the local package
RUN pip install -e .

# Use the environment variable in the CMD
CMD ["sh", "-c", "python -m dpongpy.etcd --side $PLAYER_SIDE --keys wasd"]
