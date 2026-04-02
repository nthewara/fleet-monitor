import os
import time
import socket
import threading
import requests
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Cluster endpoints from environment
CLUSTERS = {}
for key, val in os.environ.items():
    if key.startswith("CLUSTER_") and key.endswith("_URL"):
        name_part = key.replace("CLUSTER_", "").replace("_URL", "")
        name = name_part.lower().replace("_", "-")
        env_key = f"CLUSTER_{name_part}_ENV"
        CLUSTERS[name] = {
            "url": val,
            "env": os.environ.get(env_key, "unknown"),
            "name": name,
        }

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "5"))
MAX_HISTORY = 360

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
        "history": [],
        "k8s_version": "unknown",
        "node_name": "unknown",
        "pod_name": "unknown",
        "current_response": {},
    }


def tcp_check(host, port, timeout=2):
    """Reliable TCP connectivity check — no HTTP overhead."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.time()
        result = sock.connect_ex((host, port))
        latency = round((time.time() - start) * 1000)
        sock.close()
        return result == 0, latency
    except Exception:
        return False, 0


def parse_host_port(url):
    """Extract host and port from URL."""
    url = url.replace("http://", "").replace("https://", "")
    if ":" in url:
        parts = url.split(":")
        return parts[0], int(parts[1].split("/")[0])
    return url, 80


def check_cluster(name, info):
    host, port = parse_host_port(info["url"])

    # Primary: TCP check (reliable, fast)
    tcp_ok, latency = tcp_check(host, port)

    # Secondary: HTTP info (best-effort, for metadata only)
    cluster_info = {}
    if tcp_ok:
        try:
            resp = requests.get(f"{info['url']}/api/info", timeout=2)
            if resp.status_code == 200:
                cluster_info = resp.json()
        except Exception:
            pass  # TCP passed, HTTP metadata is optional

    status = "up" if tcp_ok else "down"
    now = datetime.now(timezone.utc).isoformat()

    with lock:
        d = health_data[name]
        d["status"] = status
        d["latency_ms"] = latency
        d["last_check"] = now
        d["checks_total"] += 1
        if status == "up":
            d["checks_ok"] += 1
            if cluster_info:
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


@app.route("/api/reset")
def api_reset():
    with lock:
        for name in health_data:
            health_data[name] = init_cluster_data(name)
    return jsonify({"status": "reset"})


@app.route("/api/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
