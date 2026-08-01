import os
import random
import time
import urllib.error
import urllib.request
import json

TELEMETRY_URL = os.environ.get("TELEMETRY_URL", "http://telemetry:8000")
STORE_ID = os.environ["STORE_ID"]
BASE_TEMPERATURE = float(os.environ.get("BASE_TEMPERATURE", "4.0"))
TEMP_VARIANCE = float(os.environ.get("TEMP_VARIANCE", "0.5"))
INTERVAL_SECONDS = float(os.environ.get("INTERVAL_SECONDS", "300"))


def send_measurement() -> None:
    temperature = round(BASE_TEMPERATURE + random.uniform(-TEMP_VARIANCE, TEMP_VARIANCE), 2)
    humidity = round(random.uniform(35, 55), 1)
    body = json.dumps({"store_id": STORE_ID, "temperature": temperature, "humidity": humidity}).encode()
    request = urllib.request.Request(
        f"{TELEMETRY_URL}/measurements",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(f"sent temperature={temperature} humidity={humidity} -> {response.status}", flush=True)
    except urllib.error.URLError as exc:
        print(f"failed to send measurement: {exc}", flush=True)


if __name__ == "__main__":
    while True:
        send_measurement()
        time.sleep(INTERVAL_SECONDS)
