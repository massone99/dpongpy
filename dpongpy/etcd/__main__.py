import etcd3
from dpongpy.log import logger

if __name__ == "__main__":
    client = etcd3.client()

    key = "pong_lobby"
    value, metadata = client.get(key)

    if value:
        print(f"Key '{key}' exists with value: {value.decode('utf-8')}")
    else:
        logger.info(f"Key '{key}' does not exist. Creating key with empty JSON value.")
        
        client.put(key, "{}")
        
        if client.get(key):
            logger.info(f"Key '{key}' created successfully.")
        else:
            logger.error(f"Failed to create key '{key}'.")
            raise Exception(f"Failed to create key '{key}' in etcd.")