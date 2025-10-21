import os

base_url = os.environ.get("DLAI_LOCAL_URL", "https://server.testhup.site")
print("Remote server is running at:")
print(base_url.format(port=8001) + "sse")
