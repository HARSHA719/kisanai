import requests
import traceback

with open("error.txt", "w") as f:
    try:
        res = requests.post("http://localhost:8000/api/auth/register", json={
            "email": "testhttp11@test.com",
            "password": "pwd",
            "name": "tester"
        }, timeout=10)
        f.write(f"STATUS: {res.status_code}\n")
        f.write(f"BODY:\n{res.text}\n")
    except Exception as e:
        f.write(f"EXCEPT:\n{traceback.format_exc()}\n")
