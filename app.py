import os
import time
import threading
import requests
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Cluster endpoints from environment
CLUSTERS = {}
for key, val in os.environ.items():
    if key.startswith("CLUSTER_") and key.endswith("_URL"):
        name = key.replace("CLUSTER_", "").replace("_URL", "").lower().replace("_", "-")
        env_key = f"CLUSTER_{key.split('_')[1]}_ENV"
        CLUSTERS[name] = {
            "url": val,
            "env": os.environ.get(env_key, "unknown"),
            "name": name,
        }

# Health check history per cluster
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "5"))  # seconds
MAX_HISTORY = 360  # last 30 min at 5s intervals

health_data = {}
lock = threading.Lock()


def init_cluster_data(name):
    return {
        "name": name,
        "url": CLUSTERS[name]["url"],
        "env": CLUSTERS[name]["env"],
        "status": "unknown",
        "latency_ms": 0,
        "last_check": None,
        "uptime_pct": 100.0,
        "checks_total": 0,
        "checks_ok": 0,
        "checks_fail": 0,
        "history": [],  # list of {ts, status, latency_ms, k8s_version, cluster_info}
        "k8s_version": "unknown",
        "node_name": "unknown",
        "pod_name": "unknown",
        "current_response": {},
    }


def check_cluster(name, info):
    start = time.time()
    try:
        resp = requests.get(f"{info['url']}/api/info", timeout=3)
        latency = round((time.time() - start) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            status = "up"
            cluster_info = data
        else:
            status = "down"
            latency = round((time.time() - start) * 1000)
            cluster_info = {}
    except Exception:
        status = "down"
        latency = round((time.time() - start) * 1000)
        cluster_info = {}

    now = datetime.now(timezone.utc).isoformat()

    with lock:
        d = health_data[name]
        d["status"] = status
        d["latency_ms"] = latency
        d["last_check"] = now
        d["checks_total"] += 1
        if status == "up":
            d["checks_ok"] += 1
            d["k8s_version"] = cluster_info.get("k8s_version", d["k8s_version"])
            d["node_name"] = cluster_info.get("node_name", d["node_name"])
            d["pod_name"] = cluster_info.get("pod_name", d["pod_name"])
            d["current_response"] = cluster_info
        else:
            d["checks_fail"] += 1

        d["uptime_pct"] = round(d["checks_ok"] / d["checks_total"] * 100, 2) if d["checks_total"] > 0 else 0

        d["history"].append({
            "ts": now,
            "status": status,
            "latency_ms": latency,
        })
        if len(d["history"]) > MAX_HISTORY:
            d["history"] = d["history"][-MAX_HISTORY:]


def monitor_loop():
    while True:
        threads = []
        for name, info in CLUSTERS.items():
            t = threading.Thread(target=check_cluster, args=(name, info))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        time.sleep(CHECK_INTERVAL)


# Init
for name in CLUSTERS:
    health_data[name] = init_cluster_data(name)

monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
monitor_thread.start()


@app.route("/")
def index():
    return render_template("index.html", clusters=CLUSTERS, check_interval=CHECK_INTERVAL)


@app.route("/api/status")
def api_status():
    with lock:
        return jsonify(health_data)


@app.route("/api/reset", methods=["POST"])
def reset_history():
    with lock:
        for name in health_data:
            health_data[name] = init_cluster_data(name)
    return jsonify({"status": "reset", "message": "All cluster history cleared"})


@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
