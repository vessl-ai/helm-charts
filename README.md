# VESSL Helm Charts

This repository contains Helm charts to integrate a Kubernetes cluster with VESSL.

(Only one chart for now)

## How to install on Kubernetes

```
helm repo add vessl https://vessl-ai.github.io/helm-charts
helm repo update
helm install vessl vessl/vessl --namespace vessl --create-namespace
```

## Development guide

1. Install depending charts

a. Add repos

```bash
helm repo add node-feature-discovery https://kubernetes-sigs.github.io/node-feature-discovery/charts
helm repo add gpu-feature-discovery https://nvidia.github.io/gpu-feature-discovery
helm repo add prometheus https://prometheus-community.github.io/helm-charts
helm repo add dcgm-exporter https://nvidia.github.io/dcgm-exporter/helm-charts
helm repo add nvidia-k8s-device-plugin https://nvidia.github.io/k8s-device-plugin
helm repo update
```

b. Build dependencies

```bash
cd charts/vessl
helm dependency build
```

2. Make changes

3. Test

`helm install vessl ./charts/vessl --dry-run -n vessl --set agent.accessToken='dummy'`

## How to Release a Chart

1. Update the chart version in Chart.yaml and push the changes.
2. Create a pull request (PR) with the `release` label.
3. Once the PR is reviewed and approved, you can proceed to merge it.


### Tips

1. Make dry run before your change, and check diff with the one after you change

```bash
# before change
helm install vessl ./charts/vessl --dry-run -n vessl --set agent.accessToken='dummy' > before

# after make some change
helm install vessl ./charts/vessl --dry-run -n vessl --set agent.accessToken='dummy' > after

# diff
diff before after

# cleanup
rm before after
```
