# Fleet Monitor

Real-time monitoring dashboard for AKS Fleet Manager demos. Shows fleet topology, traffic flow, uptime tracking, and latency during cluster upgrades.

## Features

- **Visual Fleet Topology** — hub → member cluster diagram with live status indicators
- **Uptime Timeline** — per-cluster health history with green/red bars
- **Latency Chart** — response time trends per cluster
- **Live Polling** — configurable interval (default 5s)
- **Environment Colours** — 🔵 Dev, 🟡 Staging, 🔴 Production
- **Upgrade Visibility** — watch clusters go offline during rolling upgrades

## Architecture

```
Fleet Monitor (4th cluster)
      │
      ├── GET /api/info → Dev Cluster (fleet-dashboard)
      ├── GET /api/info → Staging Cluster (fleet-dashboard)  
      └── GET /api/info → Prod Cluster (fleet-dashboard)
```

## Quick Start

```bash
# Build image
az acr build --registry <acr-name> --image fleet-monitor:v1 .

# Deploy to monitor cluster
# Update k8s/deployment.yaml with ACR server and cluster URLs
kubectl apply -f k8s/deployment.yaml
```

## Configuration

Set cluster endpoints via environment variables:

```
CLUSTER_DEV_URL=http://20.193.9.67
CLUSTER_DEV_ENV=dev
CLUSTER_STAGING_URL=http://20.227.13.191
CLUSTER_STAGING_ENV=staging
CLUSTER_PROD_URL=http://20.40.179.149
CLUSTER_PROD_ENV=prod
CHECK_INTERVAL=5
```

## Demo Usage

1. Deploy fleet-dashboard to all 3 AKS member clusters
2. Deploy fleet-monitor to the 4th (non-fleet) monitoring cluster
3. Open the Fleet Monitor dashboard
4. Kick off Fleet Manager update run (K8s upgrade)
5. Watch clusters go offline/online in sequence during the staged rollout
