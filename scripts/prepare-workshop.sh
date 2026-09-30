#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/scripts/lib/common.sh"

packmate_require_auth
packmate_load_or_default_config "${ROOT}"
packmate_assert_rhoai_35
packmate_discover_model_url
packmate_write_local_config "${ROOT}"

APP_LABEL_KEY="${WORKSHOP_PART_OF_LABEL%%=*}"
APP_LABEL_VALUE="${WORKSHOP_PART_OF_LABEL#*=}"
MANAGED_LABEL_KEY="${WORKSHOP_MANAGED_LABEL%%=*}"
MANAGED_LABEL_VALUE="${WORKSHOP_MANAGED_LABEL#*=}"
BUILD_TAG="workshop"

packmate_apply_namespace

OGX_SERVER_NAME="$(oc get ogxserver -n "${MODEL_NAMESPACE}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [[ -z "${OGX_SERVER_NAME}" ]]; then
  printf 'ERROR: no OGXServer found in %s\n' "${MODEL_NAMESPACE}" >&2
  exit 1
fi

OGX_BASE_URL="http://${OGX_SERVER_NAME}-service.${MODEL_NAMESPACE}.svc.cluster.local:8321/v1"
OGX_MODEL_ID="vllm-inference-1/${MODEL_NAME}"
OGX_WEATHER_MCP_URL="http://weather-mcp.${WORKSHOP_NAMESPACE}.svc.cluster.local:8080/mcp"
OGX_BAGGAGE_MCP_URL="http://baggage-policy-mcp.${WORKSHOP_NAMESPACE}.svc.cluster.local:8080/mcp"

oc patch ogxserver "${OGX_SERVER_NAME}" -n "${MODEL_NAMESPACE}" --type=merge -p "{
  \"spec\": {
    \"network\": {
      \"port\": 8321,
      \"policy\": {
        \"enabled\": true,
        \"policyTypes\": [\"Ingress\"],
        \"ingress\": [
          {
            \"from\": [
              {\"podSelector\": {}},
              {\"namespaceSelector\": {\"matchLabels\": {\"kubernetes.io/metadata.name\": \"redhat-ods-applications\"}}},
              {\"namespaceSelector\": {\"matchLabels\": {\"network.openshift.io/policy-group\": \"ingress\"}}},
              {\"namespaceSelector\": {\"matchLabels\": {\"kubernetes.io/metadata.name\": \"${WORKSHOP_NAMESPACE}\"}}}
            ],
            \"ports\": [
              {\"port\": 8321, \"protocol\": \"TCP\"}
            ]
          },
          {
            \"from\": [
              {\"namespaceSelector\": {\"matchLabels\": {\"network.openshift.io/policy-group\": \"monitoring\"}}}
            ],
            \"ports\": [
              {\"port\": 9464, \"protocol\": \"TCP\"}
            ]
          }
        ]
      }
    }
  }
}" >/dev/null

oc apply -f - <<EOF
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: packmate-backend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
---
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: packmate-frontend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
---
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: weather-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
---
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: baggage-policy-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: packmate-backend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
  output:
    to:
      kind: ImageStreamTag
      name: packmate-backend:${BUILD_TAG}
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: packmate-frontend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
  output:
    to:
      kind: ImageStreamTag
      name: packmate-frontend:${BUILD_TAG}
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: weather-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
  output:
    to:
      kind: ImageStreamTag
      name: weather-mcp:${BUILD_TAG}
---
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: baggage-policy-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
  output:
    to:
      kind: ImageStreamTag
      name: baggage-policy-mcp:${BUILD_TAG}
EOF

oc -n "${WORKSHOP_NAMESPACE}" start-build packmate-backend --from-dir="${ROOT}/app/backend" --follow --wait
oc -n "${WORKSHOP_NAMESPACE}" start-build packmate-frontend --from-dir="${ROOT}/app/frontend" --follow --wait
oc -n "${WORKSHOP_NAMESPACE}" start-build weather-mcp --from-dir="${ROOT}/mcp/weather" --follow --wait
oc -n "${WORKSHOP_NAMESPACE}" start-build baggage-policy-mcp --from-dir="${ROOT}/mcp/baggage" --follow --wait

BACKEND_BUILD_VERSION="$(oc -n "${WORKSHOP_NAMESPACE}" get buildconfig packmate-backend -o jsonpath='{.status.lastVersion}')"
FRONTEND_BUILD_VERSION="$(oc -n "${WORKSHOP_NAMESPACE}" get buildconfig packmate-frontend -o jsonpath='{.status.lastVersion}')"
WEATHER_BUILD_VERSION="$(oc -n "${WORKSHOP_NAMESPACE}" get buildconfig weather-mcp -o jsonpath='{.status.lastVersion}')"
BAGGAGE_BUILD_VERSION="$(oc -n "${WORKSHOP_NAMESPACE}" get buildconfig baggage-policy-mcp -o jsonpath='{.status.lastVersion}')"

BACKEND_REPOSITORY="$(oc -n "${WORKSHOP_NAMESPACE}" get imagestream packmate-backend -o jsonpath='{.status.dockerImageRepository}')"
FRONTEND_REPOSITORY="$(oc -n "${WORKSHOP_NAMESPACE}" get imagestream packmate-frontend -o jsonpath='{.status.dockerImageRepository}')"
WEATHER_REPOSITORY="$(oc -n "${WORKSHOP_NAMESPACE}" get imagestream weather-mcp -o jsonpath='{.status.dockerImageRepository}')"
BAGGAGE_REPOSITORY="$(oc -n "${WORKSHOP_NAMESPACE}" get imagestream baggage-policy-mcp -o jsonpath='{.status.dockerImageRepository}')"

BACKEND_DIGEST="$(oc -n "${WORKSHOP_NAMESPACE}" get build "packmate-backend-${BACKEND_BUILD_VERSION}" -o jsonpath='{.status.output.to.imageDigest}')"
FRONTEND_DIGEST="$(oc -n "${WORKSHOP_NAMESPACE}" get build "packmate-frontend-${FRONTEND_BUILD_VERSION}" -o jsonpath='{.status.output.to.imageDigest}')"
WEATHER_DIGEST="$(oc -n "${WORKSHOP_NAMESPACE}" get build "weather-mcp-${WEATHER_BUILD_VERSION}" -o jsonpath='{.status.output.to.imageDigest}')"
BAGGAGE_DIGEST="$(oc -n "${WORKSHOP_NAMESPACE}" get build "baggage-policy-mcp-${BAGGAGE_BUILD_VERSION}" -o jsonpath='{.status.output.to.imageDigest}')"

BACKEND_IMAGE="${BACKEND_REPOSITORY}@${BACKEND_DIGEST}"
FRONTEND_IMAGE="${FRONTEND_REPOSITORY}@${FRONTEND_DIGEST}"
WEATHER_IMAGE="${WEATHER_REPOSITORY}@${WEATHER_DIGEST}"
BAGGAGE_IMAGE="${BAGGAGE_REPOSITORY}@${BAGGAGE_DIGEST}"

oc -n "${WORKSHOP_NAMESPACE}" create secret generic packmate-llm \
  --from-literal=BASE_URL="${OGX_BASE_URL}" \
  --from-literal=MODEL="${OGX_MODEL_ID}" \
  --from-literal=LITELLM_API_KEY="dummy" \
  --dry-run=client -o yaml | oc apply -f -
oc -n "${WORKSHOP_NAMESPACE}" label secret/packmate-llm \
  "${APP_LABEL_KEY}=${APP_LABEL_VALUE}" "${MANAGED_LABEL_KEY}=${MANAGED_LABEL_VALUE}" --overwrite >/dev/null

oc -n "${WORKSHOP_NAMESPACE}" create configmap packmate-backend-config \
  --from-literal=PACKMATE_RUNTIME_MODE=ogx \
  --from-literal=PACKMATE_TOOL_MODE=mcp \
  --from-literal=PACKMATE_WEATHER_MCP_URL="${OGX_WEATHER_MCP_URL}" \
  --from-literal=PACKMATE_BAGGAGE_MCP_URL="${OGX_BAGGAGE_MCP_URL}" \
  --from-literal=PACKMATE_MCP_TIMEOUT_SECONDS=10 \
  --from-literal=PACKMATE_MCP_MAX_RETRIES=2 \
  --dry-run=client -o yaml | oc apply -f -
oc -n "${WORKSHOP_NAMESPACE}" label configmap/packmate-backend-config \
  "${APP_LABEL_KEY}=${APP_LABEL_VALUE}" "${MANAGED_LABEL_KEY}=${MANAGED_LABEL_VALUE}" --overwrite >/dev/null

oc -n "${WORKSHOP_NAMESPACE}" create configmap packmate-workshop-info \
  --from-literal=validated_openshift_version=4.20.38 \
  --from-literal=validated_rhoai_version=3.5.1 \
  --from-literal=shared_model_name="${MODEL_NAME}" \
  --from-literal=shared_model_namespace="${MODEL_NAMESPACE}" \
  --from-literal=shared_model_base_url="${MODEL_BASE_URL}" \
  --dry-run=client -o yaml | oc apply -f -
oc -n "${WORKSHOP_NAMESPACE}" label configmap/packmate-workshop-info \
  "${APP_LABEL_KEY}=${APP_LABEL_VALUE}" "${MANAGED_LABEL_KEY}=${MANAGED_LABEL_VALUE}" --overwrite >/dev/null

oc apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weather-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    app: weather-mcp
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: weather-mcp
  template:
    metadata:
      labels:
        app: weather-mcp
        ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
        ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
    spec:
      containers:
      - name: weather-mcp
        image: ${WEATHER_IMAGE}
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: weather-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  selector:
    app: weather-mcp
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: weather-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
  annotations:
    haproxy.router.openshift.io/timeout: 60s
spec:
  to:
    kind: Service
    name: weather-mcp
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: baggage-policy-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    app: baggage-policy-mcp
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: baggage-policy-mcp
  template:
    metadata:
      labels:
        app: baggage-policy-mcp
        ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
        ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
    spec:
      containers:
      - name: baggage-policy-mcp
        image: ${BAGGAGE_IMAGE}
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: baggage-policy-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  selector:
    app: baggage-policy-mcp
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: baggage-policy-mcp
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
  annotations:
    haproxy.router.openshift.io/timeout: 60s
spec:
  to:
    kind: Service
    name: baggage-policy-mcp
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: packmate-backend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    app: packmate-backend
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: packmate-backend
  template:
    metadata:
      labels:
        app: packmate-backend
        ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
        ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
    spec:
      containers:
      - name: packmate-backend
        image: ${BACKEND_IMAGE}
        envFrom:
        - secretRef:
            name: packmate-llm
        - configMapRef:
            name: packmate-backend-config
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: packmate-backend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  selector:
    app: packmate-backend
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: packmate-frontend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    app: packmate-frontend
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: packmate-frontend
  template:
    metadata:
      labels:
        app: packmate-frontend
        ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
        ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
    spec:
      containers:
      - name: packmate-frontend
        image: ${FRONTEND_IMAGE}
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
---
apiVersion: v1
kind: Service
metadata:
  name: packmate-frontend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
spec:
  selector:
    app: packmate-frontend
  ports:
  - name: http
    port: 8080
    targetPort: 8080
---
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: packmate-frontend
  namespace: ${WORKSHOP_NAMESPACE}
  labels:
    ${APP_LABEL_KEY}: ${APP_LABEL_VALUE}
    ${MANAGED_LABEL_KEY}: "${MANAGED_LABEL_VALUE}"
  annotations:
    haproxy.router.openshift.io/timeout: 5m
spec:
  to:
    kind: Service
    name: packmate-frontend
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
EOF

oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/weather-mcp --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/baggage-policy-mcp --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/packmate-backend --timeout=10m
oc -n "${WORKSHOP_NAMESPACE}" rollout status deploy/packmate-frontend --timeout=10m

WEATHER_ROUTE="$(oc -n "${WORKSHOP_NAMESPACE}" get route weather-mcp -o jsonpath='{.spec.host}')"
BAGGAGE_ROUTE="$(oc -n "${WORKSHOP_NAMESPACE}" get route baggage-policy-mcp -o jsonpath='{.spec.host}')"

python3 - <<'PY' "${MCP_CONFIG_NAMESPACE}" "${WEATHER_ROUTE}" "${BAGGAGE_ROUTE}" "${APP_LABEL_KEY}" "${APP_LABEL_VALUE}" "${MANAGED_LABEL_KEY}" "${MANAGED_LABEL_VALUE}"
import json
import subprocess
import sys
import tempfile

ns, weather_host, baggage_host, app_key, app_val, managed_key, managed_val = sys.argv[1:8]

def oc_json(args):
    result = subprocess.run(["oc", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)

existing = oc_json(["get", "configmap", "gen-ai-aa-mcp-servers", "-n", ns, "-o", "json"])
data = {}
if existing:
    data = dict(existing.get("data") or {})

data["Packmate-Weather-MCP"] = json.dumps(
    {
        "url": f"https://{weather_host}/mcp",
        "description": "Packmate workshop weather MCP server. Tool: get_weather.",
    },
    indent=2,
)
data["Packmate-Baggage-Policy-MCP"] = json.dumps(
    {
        "url": f"https://{baggage_host}/mcp",
        "description": "Packmate workshop baggage MCP server. Tools: check_baggage_rules, get_general_baggage_rules.",
    },
    indent=2,
)

obj = {
    "apiVersion": "v1",
    "kind": "ConfigMap",
    "metadata": {
        "name": "gen-ai-aa-mcp-servers",
        "namespace": ns,
        "labels": {
            app_key: app_val,
            managed_key: managed_val,
        },
    },
    "data": data,
}

path = tempfile.mktemp(suffix=".json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(obj, handle)
subprocess.check_call(["oc", "apply", "-f", path], stdout=subprocess.DEVNULL)
subprocess.check_call(["rm", "-f", path])
print("Registered Packmate MCP servers in gen-ai-aa-mcp-servers")
PY

printf 'Workshop support services prepared in %s\n' "${WORKSHOP_NAMESPACE}"
