FROM python:3.11

WORKDIR /app
COPY . /app

# Set environment variables for etcd connection
ENV ETCD_HOST=etcd \
    ETCD_PORT=2379

RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

# Install the local package
RUN pip install -e .

CMD ["python", "-m", "dpongpy.etcd"]