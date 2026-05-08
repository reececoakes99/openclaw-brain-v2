# CI/CD Pipeline — GitLab for Payment Gateway

## Pipeline Overview

```yaml
stages:
  - build
  - test
  - security
  - deploy-staging
  - integration-test
  - deploy-prod
```

## Build Stage

```yaml
build:
  stage: build
  image: maven:3.9-eclipse-temurin-17
  script:
    - mvn clean package -DskipTests
    - docker build -t $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA .
    - docker build -t $ECR_REGISTRY/payment-worker:$CI_COMMIT_SHA ./worker
    - docker push $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA
    - docker push $ECR_REGISTRY/payment-worker:$CI_COMMIT_SHA
    - docker tag $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA $ECR_REGISTRY/payment-engine:latest
    - docker push $ECR_REGISTRY/payment-engine:latest
  artifacts:
    paths: [target/*.jar]
    expire_in: 1 hour
  variables:
    MAVEN_OPTS: "-Dmaven.repo.local=.m2/repository"
    DOCKER_BUILDKIT: "1"
```

## Test Stage

```yaml
unit-tests:
  stage: test
  image: maven:3.9-eclipse-temurin-17
  script:
    - mvn test -Dspring.profiles.active=test
    - mvn jacoco:report
  coverage: '/Total.*?([0-9]{1,2})%/'
  artifacts:
    reports:
      junit: target/surefire-reports/*.xml
      coverage: coverage.xml

integration-tests:
  stage: test
  services:
    - redis:7
    - postgres:15
  script:
    - mvn verify -Dspring.profiles.active=integration
  artifacts:
    reports:
      junit: target/surefire-reports/*.xml

load-tests:
  stage: test
  image: python:3.11
  script:
    - pip install locust
    - locust -f tests/load/locustfile.py --headless -t 60s -r 100 -H https://staging.paybox.example.com --csv results
  artifacts:
    paths: [results/]
    expire_in: 7 days
  variables:
    TPS_THRESHOLD: "1500"
```

## Security Stage

```yaml
trivy-scan:
  stage: security
  image: aquasec/trivy:latest
  script:
    - trivy image --exit-code 1 --severity HIGH,CRITICAL $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA
  allow_failure: false

dependency-check:
  stage: security
  image: owasp/dependency-check:latest
  script:
    - dependency-check.sh --project payment-engine --scan ./target
  artifacts:
    paths: [dependency-check-report.html]
    expire_in: 30 days

container-signing:
  stage: security
  image: chainguard/crane:latest
  script:
    - crane digest $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA
    - cosign sign --yes $ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA
  variables:
    COSIGN_KEY: $COSIGN_PRIVATE_KEY
```

## Deploy Staging

```yaml
deploy-staging:
  stage: deploy-staging
  environment:
    name: staging
    url: https://staging.paybox.example.com
  script:
    - echo $KUBECONFIG | base64 -d > /tmp/kubeconfig
    - export KUBECONFIG=/tmp/kubeconfig
    - helm upgrade --install payment-engine ./helm \
        --namespace payment-staging \
        --set image.tag=$CI_COMMIT_SHA \
        --set env=staging \
        --timeout 5m \
        --wait
    - kubectl rollout status deployment/payment-engine -n payment-staging
  smoke-test:
    script:
      - curl -sf https://staging.paybox.example.com/health || exit 1
      - python tests/smoke/test_iso8583.py --host staging.paybox.example.com --count 10
```

## Integration Test

```yaml
integration-tests:
  stage: integration-test
  script:
    - python tests/integration/iso8583_validation.py --env staging
    - python tests/integration/scheme_simulator.py --validate-mti 0100,0200,0400
    - python tests/integration/hsmpin_block.py --test-encrypt --test-mac
  artifacts:
    reports:
      junit: results/*.xml
```

## Deploy Production

```yaml
deploy-prod:
  stage: deploy-prod
  environment:
    name: production
    url: https://paybox.example.com
  when: manual
  script:
    - echo $KUBECONFIG | base64 -d > /tmp/kubeconfig
    - export KUBECONFIG=/tmp/kubeconfig
    - helm upgrade --install payment-engine ./helm \
        --namespace payment-prod \
        --set image.tag=$CI_COMMIT_SHA \
        --set env=production \
        --atomic \
        --timeout 10m \
        --wait
    - kubectl set image deployment/payment-engine payment-engine=$ECR_REGISTRY/payment-engine:$CI_COMMIT_SHA -n payment-prod
  rollback:
    script:
      - helm rollback payment-engine -n payment-prod
      - kubectl rollout undo deployment/payment-engine -n payment-prod
  notify:
    script:
      - python scripts/notify-deploy.py --env prod --version $CI_COMMIT_SHA --status success
```

## Environment Variables

```yaml
variables:
  AWS_REGION: eu-west-1
  ECR_REGISTRY: 123456789.dkr.ecr.eu-west-1.amazonaws.com
  HELM_VALUES_STAGING: values.staging.yaml
  HELM_VALUES_PROD: values.prod.yaml
  SONAR_TOKEN: $SONAR_TOKEN
  COSIGN_PRIVATE_KEY: $COSIGN_PRIVATE_KEY
```

## Pipeline Rules

```yaml
workflow:
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_COMMIT_BRANCH =~ "^release/.*"
    - if: $CI_COMMIT_TAG
```

## Monitoring

- Pipeline duration: target < 20 minutes
- Test coverage gate: > 80%
- Load test gate: TPS > 1500, error rate < 0.5%
- Security gates: 0 HIGH/CRITICAL vulnerabilities (trivy)
- Rollback trigger: auto on error rate > 1% within 5 minutes of deploy