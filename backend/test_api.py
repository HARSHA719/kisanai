import requests

API_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"

options = [
    "9ef84268-d588-465a-a308-a864a43d0070",
    "3b01bcb80b144abfb6f2c1bfd384ba69"
]

for rid in options:
    url = f"https://api.data.gov.in/resource/{rid}?api-key={API_KEY}&format=json&limit=5"
    print(f"Testing {rid}...")
    try:
        r = requests.get(url, timeout=5)
        print("Status Code:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("Records found:", len(data.get("records", [])))
            for rec in data.get("records", []):
                print(rec)
            break
    except Exception as e:
        print("Error:", e)
