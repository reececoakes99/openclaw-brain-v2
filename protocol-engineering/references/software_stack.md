# Software Stack Reference

Complete software and tooling inventory for the Neopay payment platform — core suite, runtime, containerization, databases, CI/CD, security, and testing.

## Neopay Suite Modules

Neopay's core platform consists of these integrated components:

### 1. Converter / Message Normalizer
Converts between ISO8583 (HISO93 binary/ASCII), SPDH/HPDH, ISO20022 MX, SWIFT MT, and REST APIs.
- **Input:** raw terminal / scheme / API messages
- **Output:** normalized internal message format
- **Key features:** field mapping rules, currency conversion, date/time normalization, bitmaps parsing

### 2. Switch Router
Routes normalized messages based on configurable rules (MTI + field conditions → connector).
- **Input:** normalized message JSON
- **Output:** routed to destination connector(s)
- **Key features:** rule engine, priority routing, fallover routing, load balancing

### 3. Interface Connectors
Manages all external protocol connections — schemes, POS, APIs.
- Handles connection pooling, heartbeat, reconnection
- Manages session state per terminal

### 4. Authorization Host
On-line authorization processing — fraud rules, velocity checks, balance verification.
- **Input:** authorization request ISO8583
- **Output:** approved/declined with auth code
- **Key features:** rule engine, risk scoring, 3DS handling, AVS/CVV checks

### 5. Issuing Host
Card issuance, account management, EMV applet lifecycle.
- Handles account lookup, EMV offline approval, PIN management

### 6. Simulators
- **Scheme Simulator:** Visa/MC/Amex message responder for testing
- **Terminal Simulator:** emulates POS/ATM behavior
- **HSM Simulator:** mock HSM for development (never use in prod)
- **Bank Simulator:** mock bank responses for SEPA/open banking

### 7. Alerts / Data Warehouse
Real-time event stream → analytics + SIEM integration.
- Kafka → data lake (S3/GCS)
- Real-time fraud alerts via Splunk/ELK

## Runtime Environment

```yaml
# Runtime requirements
java:
  version: "17 LTS"  # Java 17 or Java 21
  vendor: "Eclipse Temurin"  # or Amazon Corretto, Azul Zulu
  heap:
    min: "4g"
    max: "16g"
  gc:
    algorithm: "G1GC"  # ZGC for ultra-low latency
    target_pause_ms: 200

jvm_arguments:
  - "-XX:+UseG1GC"
  - "-XX:MaxGCPauseMillis=200"
  - "-XX:+UseStringDeduplication"
  - "-XX:+OptimizeStringConcat"
  - "-Djava.security.egd=file:/dev/./urandom"
  - "-Dsun.security.ssl.handshake.limit=8192"

# Docker runtime
docker:
  base_image: "eclipse-temurin:17-jre-alpine"
  jvm_in_container:
    xms: "4g"
    xmx: "12g"
    max_direct_memory: "2g"
```

## Containerization & Orchestration

```yaml
# Dockerfile
FROM eclipse-temurin:17-jre-alpine
RUN apk add --no-cache \
    fontconfig \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Europe/Vilnius /etc/localtime

COPY target/neopay-switch.jar /app/neopay-switch.jar
COPY config/ /app/config/
RUN addgroup -g 1001 neopay && adduser -u 1001 -G neopay -s /bin/sh -D neopay

USER neopay
WORKDIR /app
EXPOSE 8888 8443 8080

# JVM args for containerized HSM/Docker
ENTRYPOINT ["java", "-XX:+UseG1GC", "-Xms4g", "-Xmx12g", "-jar", "neopay-switch.jar"]
```

### Kubernetes Deployment

```yaml
# assets/k8s/ deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: neopay-switch
  namespace: neopay-prod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: neopay-switch
  template:
    metadata:
      labels:
        app: neopay-switch
        version: "2.1"
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchLabels:
                    app: neopay-switch
                topologyKey: kubernetes.io/hostname
      containers:
        - name: switch
          image: neopay-registry.io/neopay/switch:2.1.0
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
            limits:
              cpu: "4"
              memory: "16Gi"
          ports:
            - name: admin
              containerPort: 8080
            - name: hsm
              containerPort: 8888
            - name: ssl
              containerPort: 8443
          env:
            - name: JAVA_OPTS
              value: "-XX:+UseG1GC -Xms4g -Xmx12g -XX:+UseContainerSupport"
            - name: SPRING_PROFILES_ACTIVE
              value: "production"
            - name: SPRING_DATASOURCE_URL
              valueFrom:
                secretKeyRef:
                  name: neopay-db-secret
                  key: url
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8080
            initialDelaySeconds: 60
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 5
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
      volumes:
        - name: config
          configMap:
            name: neopay-switch-config

---
apiVersion: v1
kind: Service
metadata:
  name: neopay-switch-svc
  namespace: neopay-prod
spec:
  type: ClusterIP
  ports:
    - name: admin
      port: 8080
      targetPort: 8080
    - name: hsm
      port: 8888
      targetPort: 8888
  selector:
    app: neopay-switch

---
# HPA — Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: neopay-switch-hpa
  namespace: neopay-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: neopay-switch
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "500"
```

### Kubernetes ConfigMaps & Secrets

```yaml
# assets/k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: neopay-switch-config
  namespace: neopay-prod
data:
  application.yml: |
    spring:
      application:
        name: neopay-switch
      profiles:
        active: production
    neopay:
      switch:
        mti-default-timeout: 45
        hsm:
          host: ${HSM_HOST}
          port: 8888
      connectors:
        kafka:
          bootstrap-servers: kafka-1:9092,kafka-2:9092
        rabbitmq:
          host: rabbitmq.neopay.io
          port: 5672
```

## Database Infrastructure

### Relational (Oracle / DB2)

```sql
-- Oracle ledger table (partitioned by month for performance)
CREATE TABLE tx_ledger (
    tx_id          RAW(16) PRIMARY KEY,
    rrn            CHAR(12) NOT NULL,
    stan           NUMBER(6) NOT NULL,
    pan_encrypted  RAW(128) NOT NULL,
    amount         NUMBER(16,2) NOT NULL,
    currency       CHAR(3) NOT NULL,
    mti            CHAR(4) NOT NULL,
    proc_code      CHAR(6),
    response_code  CHAR(2),
    acquirer_id    CHAR(11),
    merchant_id    CHAR(15),
    terminal_id    CHAR(8),
    created_at     TIMESTAMP DEFAULT SYSTIMESTAMP,
    settlement_date DATE,
    status         CHAR(1)
) PARTITION BY RANGE (created_at) (
    PARTITION p202606 VALUES LESS THAN (TO_DATE('2026-07-01','YYYY-MM-DD')),
    PARTITION p202607 VALUES LESS THAN (TO_DATE('2026-08-01','YYYY-MM-DD'))
);

CREATE INDEX idx_tx_ledger_rrn ON tx_ledger(rrn);
CREATE INDEX idx_tx_ledger_pan ON tx_ledger(pan_encrypted);
CREATE INDEX idx_tx_ledger_settlement ON tx_ledger(settlement_date, status);
```

### NoSQL (MongoDB / Redis)

```yaml
# MongoDB — transaction logging
mongodb:
  collection: "txlog"
  document:
    _id: ObjectId
    rrn: string
    stan: int
    pan_masked: string
    amount: Decimal128
    currency: string
    mti: string
    proc_code: string
    response_code: string
    acquirer_id: string
    merchant_id: string
    terminal_id: string
    raw_message: Binary  # full ISO8583 bytes
    created_at: ISODate
    received_at: ISODate
    processed_at: ISODate
    latency_ms: int
  indexes:
    - rrn: 1
    - stan: 1, acquirer_id: 1
    - created_at: -1
    - merchant_id: 1, created_at: -1
  ttl: 7776000  # 90 days auto-delete

# Redis — rate limiting / cache
redis:
  rate_limit:
    key_pattern: "rl:{pan}:{hour}"
    limit: 20
    window_seconds: 3600
  card_cache:
    key_pattern: "card:{pan_hash}"
    ttl_seconds: 300
  session:
    key_pattern: "session:{terminal_id}"
    ttl_seconds: 900
```

## CI/CD Pipeline

```yaml
# Bitbucket Pipeline (bitbucket-pipelines.yml)
image: maven:3.9-eclipse-temurin-17

pipelines:
  branches:
    main:
      - step:
          name: Build
          script:
            - mvn clean package -DskipTests
          artifacts:
            - target/*.jar
      - step:
          name: Unit Tests
          script:
            - mvn test
          caches:
            - maven
      - step:
          name: Security Scan
          script:
            - mvn dependency:tree
            - pip install safety bandit
            - safety check
            - bandit -r src/
      - step:
          name: Docker Build & Push
          services:
            - docker
          script:
            - docker build -t neopay-registry.io/neopay/switch:$BITBUCKET_COMMIT .
            - docker push neopay-registry.io/neopay/switch:$BITBUCKET_COMMIT
      - step:
          name: K8s Deploy Staging
          deployment: staging
          script:
            - kubectl set image deployment/neopay-switch switch=neopay-registry.io/neopay/switch:$BITBUCKET_COMMIT
            - kubectl rollout status deployment/neopay-switch -n neopay-staging

  pull-requests:
    '**':
      - step:
          name: Build & Test
          script:
            - mvn clean verify
          caches:
            - maven
```

```yaml
# Azure Pipelines (azure-pipelines.yml)
trigger:
  branches:
    include:
      - main
      - release/*

stages:
  - stage: Build
    jobs:
      - job: Maven_Build
        pool:
          vmImage: 'ubuntu-22.04'
        steps:
          - task: MavenAuthenticate@0
          - task: Bash: mvn clean package -DskipTests

  - stage: Test
    jobs:
      - job: Unit_Tests
        steps:
          - task: Bash: mvn test
          - task: PublishTestResults@2
      - job: Integration_Tests
        steps:
          - task: Bash: mvn verify -Pintegration
          services:
            docker: docker
            kafka: kafka
            redis: redis

  - stage: Security
    jobs:
      - job: SAST
        steps:
          - task: Bash: bandit -r src/ -f json -o bandit.json
          - task: PublishSecurityDebugLogs@0
      - job: Dependency_Scan
        steps:
          - task: Bash: mvn dependency:analyze

  - stage: Deploy_Staging
    jobs:
      - deployment: K8s_Staging
        environment: 'neopay-staging'
        strategy: runOnce
        steps:
          - task: Kubernetes@1
            inputs:
              kubectlVersion: 'latest'
              connectionType: 'Kubernetes Service Connection'
              namespace: 'neopay-staging'
              command: 'set image deployment/neopay-switch switch=$(registry)/neopay/switch:$(Build.BuildNumber)'

  - stage: Performance_Test
    jobs:
      - job: TPS_Load_Test
        steps:
          - task: Bash: |
              # JMeter load test — target 1500 TPS
              jmeter -n -t perf/iso8583_load_test.jmx \
                -l results.jtl \
                -e -o perf-report/ \
                -Jthreads=500 \
                -Jrampup=60 \
                -Jduration=300 \
                -Jtarget_tps=1500

  - stage: Deploy_Production
    condition: succeeded('Deploy_Staging')
    jobs:
      - deployment: K8s_Production
        environment: 'neopay-production'
        strategy:
          runOnce:
            deploy:
              steps:
                - task: Kubernetes@1
                  inputs:
                    command: |
                      kubectl rollout status deployment/neopay-switch -n neopay-prod
                      kubectl set image deployment/neopay-switch switch=$(registry)/neopay/switch:$(Build.BuildNumber)
```

## Performance Testing Targets

| Metric | Target | Notes |
|--------|--------|-------|
| TPS (ISO8583) | 1500 | sustained throughput |
| Auth latency (p99) | < 200ms | network + processing |
| Message parse time | < 1ms | per ISO8583 message |
| HSM response time | < 50ms | per PIN/MAC operation |
| End-to-end auth | < 500ms | terminal to response |
| Availability | 99.99% | SLA |
| Recovery Time Objective (RTO) | < 15 min | disaster recovery |

## Security & Monitoring Tools

| Tool | Purpose |
|------|---------|
| **Splunk / Elastic Stack** | SIEM — log aggregation, alerting |
| **Prometheus** | Metrics collection |
| **Grafana** | Dashboards (latency, throughput, error rates) |
| **Datadog** | APM + infrastructure monitoring |
| **Vault** | Secrets management (HashiCorp Vault) |
| **Falco** | Kubernetes runtime security |
| **Twistlock / Prisma Cloud** | Container image scanning |
| **OWASP ZAP** | API fuzzing |
| **Burp Suite** | Protocol-level testing |

## Testing Utilities

| Tool | Purpose |
|------|---------|
| **Postman** | REST API testing |
| **JMeter** | Load testing (1500 TPS target) |
| **SoapUI** | SOAP/XML protocol testing |
| **Neopay Online Tools** | ISO8583 parser, crypto calculators |
| **Wireshark** | Network packet analysis |
| **scapy** | Custom packet crafting |
| **Apache Bench / k6** | HTTP load testing |
| **Custom fuzzing scripts** | Random message mutation testing |
