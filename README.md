# VESSL Helm Charts

This repository contains Helm charts to integrate a Kubernetes cluster with VESSL.

(Only one chart for now)

## How to install on Kubernetes

```
helm repo add vessl https://vessl-ai.github.io/helm-charts
helm repo update
helm install vessl/vessl
```