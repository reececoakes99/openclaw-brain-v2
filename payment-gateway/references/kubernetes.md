# Kubernetes Deployment Architecture

## Cluster Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     GCP / AWS / Azure                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Kubernetes Cluster (EKS/GKE/EKS)             │ │
│  │                                                        │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │ │
│  │  │ Namespace │ │ Namespace │ │ Namespace │ │ Namespace │   │ │
│  │  │payments-1 │ │payments-2 │ │ vault-db  │ │ infra    │   │ │
│  │  │          │ │          │ │          │ │          │   │ │
│  │  │ message- │ │ rest-api │ │ vault-svc │ │监控      │   │ │
│  │  │ engine   │ │          │ │          │ │prometheus│   │ │
│  │  │ hsm-svc  │ │ admin-ui │ │ redis    │ │ grafana  │   │ │
│  │  │ psd2-    │ │          │ │ postgres │ │ alerts   │   │ │
│  │  │ gateway  │ │          │ │          │ │          │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               Managed Services                          │ │
│  │  CloudSQL (PostgreSQL) │ Memorystore (Redis)           │ │
│  │  CloudHSM │ Cloud Armor (WAF) │ Cloud CDN               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Namespace Structure

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: neopay-payments
  labels:
    env: production
    team: payments
    pci-scope: "true"

---
apiVersion: v1
kind: Namespace
metadata:
  name: neopay-vault
  labels:
    env: production
    team: security
    pci-scope: "true"
    # Vault namespace has stricter network policies

---
apiVersion: v1
kind: Namespace
metadata:
  name: neopay-infrastructure
  labels:
    env: production
    team: platform
    pci-scope: "false"
```

## Message Engine Deployment

```yaml
# message-engine-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: message-engine
  namespace: neopay-payments
  labels:
    app: message-engine
    tier: core
spec:
  replicas: 6
  selector:
    matchLabels:
      app: message-engine
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 0  # Zero downtime for payment processing
  template:
    metadata:
      labels:
        app: message-engine
        tier: core
        version: "2.1.0"
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: [message-engine]
                topologyKey: kubernetes.io/hostname
      
      containers:
        - name: message-engine
          image: neopay/message-engine:2.1.0
          ports:
            - containerPort: 8080
              name: http
            - containerPort: 9090
              name: grpc
          
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
            limits:
              cpu: "4"
              memory: "8Gi"
              # Memory limit = request for guaranteed QoS
          
          env:
            - name: JAVA_OPTS
              value: "-Xms2g -Xmx4g -XX:+UseG1GC 
                      -XX:MaxGCPauseMillis=50
                      -Djava.security.egd=file:/dev/./urandom
                      -XX:+HeapDumpOnOutOfMemoryError"
            - name: SPRING_PROFILES_ACTIVE
              value: "production"
            - name: RABBITMQ_HOST
              valueFrom:
                secretKeyRef:
                  name: rabbitmq-credentials
                  key: host
            - name: RABBITMQ_USER
              valueFrom:
                secretKeyRef:
                  name: rabbitmq-credentials
                  key: username
            - name: RABBITMQ_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: rabbitmq-credentials
                  key: password
          
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8080
            initialDelaySeconds: 60
            periodSeconds: 30
            failureThreshold: 3
          
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
          
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 30"]  # Graceful drain
          # Allow 30s for in-flight messages to complete
```

## HSM Service (PCI Scope — Isolated Deployment)

```yaml
# hsm-service-deployment.yaml
# Runs in dedicated node pool, no internet access
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hsm-service
  namespace: neopay-vault
  labels:
    app: hsm-service
    tier: security
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hsm-service
  template:
    metadata:
      labels:
        app: hsm-service
    spec:
      # Dedicated node pool (no other workloads)
      nodeSelector:
        workload-type: hsm
      
      tolerations:
        - key: "dedicated"
          operator: "Equal"
          value: "hsmpool"
      
      containers:
        - name: hsm-service
          image: neopay/hsm-service:1.3.0
          
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
              # No memory limit = guaranteed QoS for HSM ops
          
          env:
            - name: HSM_TYPE
              value: "THALES_LUNA"
            - name: HSM_HOST
              value: "hsm-cluster.neopay.internal"
            - name: HSM_SLOT
              value: "0"
            - name: VAULT_KEY_VERSION
              value: "3"
          
          # No liveness probe (HSM must not be restarted)
          # Only readiness for load balancing
          readinessProbe:
            exec:
              command: ["/app/check_hsm_connection.sh"]
            initialDelaySeconds: 30
            periodSeconds: 60
          
          securityContext:
            runAsNonRoot: false
            runAsUser: 0
            # Runs as root to access HSM hardware
          
          # Strict network policy (can only talk to HSM)
          # See network-policy.yaml
```

## Network Policies (Zero-Trust)

```yaml
# message-engine-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: message-engine-netpol
  namespace: neopay-payments
spec:
  podSelector:
    matchLabels:
      app: message-engine
  
  policyTypes:
    - Ingress
    - Egress
  
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: neopay-ingress  # Ingress controller namespace
          podSelector:
            matchLabels:
              app: nginx-ingress
      ports:
        - protocol: TCP
          port: 8080
  
  egress:
    # Outbound: only to defined dependencies
    - to:
        - namespaceSelector:
            matchLabels:
              name: neopay-payments
      ports:
        - protocol: TCP
          port: 5672  # RabbitMQ
        - protocol: TCP
          port: 5432  # PostgreSQL
    
    - to:
        - namespaceSelector:
            matchLabels:
              name: neopay-vault
      ports:
        - protocol: TCP
          port: 8443  # Vault service
    
    - to:
        - namespaceSelector:
            matchLabels:
              name: neopay-infrastructure
      ports:
        - protocol: TCP
          port: 9090  # Prometheus metrics
    
    # Deny all other egress (including internet)
    - to:
        - namespaceSelector: {}
      ports: []
```

## Vault Service (PCI — Most Sensitive)

```yaml
# vault-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vault-service
  namespace: neopay-vault
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vault-service
  
  template:
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: zone
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: vault-service
      
      containers:
        - name: vault-service
          image: neopay/vault-service:3.0.0
          
          env:
            - name: ENCRYPTION_KEY_SOURCE
              value: "HSM"
            - name: HSM_ENDPOINT
              value: "hsm-service:8443"
          
          resources:
            requests:
              cpu: "1"
              memory: "2Gi"
            limits:
              cpu: "2"
              memory: "4Gi"
          
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: vault-secrets
              mountPath: /var/lib/vault/secrets
              readOnly: true
      
      volumes:
        - name: tmp
          emptyDir: {}
        - name: vault-secrets
          emptyDir:
            medium: Memory
            sizeLimit: 256Mi
          # In-memory storage for sensitive temp data
```

## Autoscaling

```yaml
# Horizontal Pod Autoscaler for message engine
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: message-engine-hpa
  namespace: neopay-payments
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: message-engine
  
  minReplicas: 6
  maxReplicas: 30
  
  metrics:
    # Scale on RabbitMQ queue depth
    - type: Pods
      pods:
        metric:
          name: rabbitmq_queue_messages
        target:
          type: AverageValue
          averageValue: "100"  # 100 messages per pod = scale up
    # Scale on CPU (cooldown during spikes)
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 min cooldown
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0  # Immediate scale up
      policies:
        - type: Pods
          value: 4
          periodSeconds: 60
```

## Helm Chart Structure

```
payment-gateway/
├── Chart.yaml
├── values.yaml
├── values-production.yaml
├── values-staging.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── pdb.yaml               # PodDisruptionBudget
│   ├── networkpolicy.yaml
│   ├── servicemonitor.yaml    # Prometheus scraping
│   └── secret.yaml
└── charts/
    ├── rabbitmq-12.0.0.tgz
    └── postgresql-11.0.0.tgz
```

## PodDisruptionBudget (Availability)

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: message-engine-pdb
  namespace: neopay-payments
spec:
  minAvailable: "80%"  # At least 80% pods available during disruption
  # For payment processing, we want high availability
  
# For vault (less critical for availability, more critical for security)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: vault-service-pdb
  namespace: neopay-vault
spec:
  maxUnavailable: 1  # Allow max 1 vault pod down (replicas:3)
```

## ServiceMonitor (Prometheus + Grafana)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: message-engine-monitor
  namespace: neopay-infrastructure
  labels:
    team: platform
spec:
  selector:
    matchLabels:
      app: message-engine
  endpoints:
    - port: http
      path: /actuator/prometheus
      interval: 15s
  
  # Key metrics to alert on:
  # - authorization_latency_p99 (target: < 500ms)
  # - rabbitmq_queue_depth (alert if > 1000)
  # - error_rate (alert if > 1%)
  # - hsm_operation_duration (alert if > 1000ms)
```

## Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: payments-quota
  namespace: neopay-payments
spec:
  hard:
    requests.cpu: "24"
    requests.memory: "48Gi"
    limits.cpu: "48"
    limits.memory: "96Gi"
    pods: "50"
    services: "20"
```