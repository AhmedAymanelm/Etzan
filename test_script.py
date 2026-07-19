import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
response = client.get("/neuroscience/questions")
print(response.status_code)
print(response.text)
