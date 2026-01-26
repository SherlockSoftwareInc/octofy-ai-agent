from pymilvus import connections, utility

# Connect to Milvus
connections.connect("default", host="localhost", port="19530")

# Check server status
print(utility.get_server_version())
print(utility.list_collections())

