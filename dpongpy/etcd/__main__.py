import etcd3

if __name__ == "__main__":
    client = etcd3.client()

    key = "pong_lobby"
    value, metadata = client.get(key)

    if value:
        print(f"Key '{key}' exists with value: {value.decode('utf-8')}")
    else:
        print(f"Key '{key}' does not exist.")