# =============================================================================
# Multi-stage Dockerfile for Payment Protocol Engineering
# Base: Eclipse Temurin JDK 21 (Alpine for small footprint)
# Builder: Maven/Gradle build stage
# Runtime: JRE-only slim image with non-root user (uid 10000)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM eclipse-temurin:21-jdk-alpine AS builder

# Labels
LABEL maintainer="neopay-platform@neopay.io"
LABEL org.opencontainers.image.title="Neopay Protocol Converter"
LABEL org.opencontainers.image.description="ISO8583/HISO93 message converter and switch"

# Build arguments
ARG MAVEN_VERSION=3.9.6
ARG GRADLE_VERSION=8.5
ARG BUILD_PROFILE=production

# Install build tools
RUN apk add --no-cache \
    curl \
    tar \
    bash \
    gzip \
    maven=${MAVEN_VERSION} \
    gradle=${GRADLE_VERSION}

WORKDIR /build

# Copy pom.xml / build.gradle first for Docker layer caching
COPY pom.xml ./
COPY build.gradle ./
COPY gradle.properties ./

# Download dependencies (cached layer if pom.xml unchanged)
RUN if [ -f pom.xml ]; then mvn dependency:go-offline -B; fi
RUN if [ -f build.gradle ]; then gradle dependencies --no-daemon; fi

# Copy source
COPY src/ ./src/

# Build arguments
ARG JAR_FILE=target/*.jar
ARG JAR_CLASSIFIER=
ARG APP_NAME=neopay-converter

# Maven build
RUN mvn clean package -B \
    -DskipTests \
    -P${BUILD_PROFILE} \
    -Dmaven.javadoc.skip=true

# Gradle alternative (commented)
# RUN gradle bootJar --no-daemon -x test

# Capture JAR
RUN if [ -f target/*.jar ]; then ls -la target/*.jar; fi

# -----------------------------------------------------------------------------
# Stage 2: JRE Runtime (slim)
# -----------------------------------------------------------------------------
FROM eclipse-temurin:21-jre-alpine AS runtime

# Labels
LABEL maintainer="neopay-platform@neopay.io"
LABEL org.opencontainers.image.title="Neopay Protocol Converter"
LABEL org.opencontainers.image.version="1.0.0"

# Install runtime dependencies
RUN apk add --no-cache \
    bash \
    curl \
    busybox-extras \
    tzdata \
    openssl \
    && cp /usr/share/zoneinfo/UTC /etc/localtime \
    && echo "UTC" > /etc/timezone

# Create non-root user (uid 10000, gid 10000)
RUN adduser -D -u 10000 -g 10000 -s /bin/bash neopay \
    && addgroup neopay neopay

# Create application directories
RUN mkdir -p /opt/neopay/{config,logs,data,keys,scripts} \
    && chown -R neopay:neopay /opt/neopay \
    && chmod 750 /opt/neopay/keys

WORKDIR /opt/neopay

# Copy JMX agent (optional)
COPY --from=builder /opt/jmx-exporter/ /opt/jmx-exporter/

# Copy health check script
COPY docker-entrypoint.sh /

# Switch to non-root user
USER neopay:neopay

# Expose ports
EXPOSE 8080 8443 9090 7001 7002

# =============================================================================
# JVM Tuning Flags
# - Heap sizing via ergonomics
# - G1GC for balanced throughput/latency
# - Pre-touch for memory-mapped files
# - NUMA-aware allocation
# - GC log rotation
# =============================================================================
ENV JAVA_OPTS="\
  -server \
  -Xms512m -Xmx2048m \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -XX:+UseNUMA \
  -XX:+AlwaysPreTouch \
  -XX:+UnlockCommercialFeatures \
  -XX:+FlightRecorder \
  -XX:StartFlightRecording=delay=30s,duration=60s,filename=/opt/neopay/logs/flight.jfr \
  -XX:FlightRecorderOptions=defaultrecording=true,disk=true,maxsize=100m \
  -Djava.awt.headless=true \
  -Dfile.encoding=UTF-8 \
  -Dsun.net.inetaddr.ttl=60 \
  -Dnetworkaddress.cache.ttl=300 \
  -Dnetworkaddress.cache.negative.ttl=60 \
  -Djava.rmi.server.hostname=localhost \
  -Dcom.sun.management.jmxremote \
  -Dcom.sun.management.jmxremote.port=7001 \
  -Dcom.sun.management.jmxremote.rmi.port=7001 \
  -Dcom.sun.management.jmxremote.authenticate=true \
  -Dcom.sun.management.jmxremote.ssl=false \
  -Dcom.sun.management.jmxremote.access.file=/opt/neopay/config/jmxremote.access \
  -Dcom.sun.management.jmxremote.password.file=/opt/neopay/config/jmxremote.password \
  -javaagent:/opt/jmx-exporter/jmx-exporter.jar=9090:/opt/jmx-exporter/config.yml"

ENV GC_LOG_OPTS="\
  -Xlog:gc*:file=/opt/neopay/logs/gc.log:time,uptime,level,tags:filecount=10,filesize=50M \
  -Xlog:print老人家tion=info \
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/opt/neopay/logs/heapdump.hprof"

# =============================================================================
# Signal Handling
# Docker sends SIGTERM first, then SIGKILL after graceful timeout
# =============================================================================
STOPSIGNAL SIGTERM

# Entry point
ENTRYPOINT ["sh", "/docker-entrypoint.sh"]
CMD ["java", "-server", "${JAVA_OPTS}", "${GC_LOG_OPTS}", "-jar", "/opt/neopay/app.jar"]

# =============================================================================
# Health Check
# - HTTP health endpoint (Spring Actuator)
# - Startup grace period: 60s
# - Interval: 30s
# - Retries: 3
# - Start period: 90s (includes JVM warmup)
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -sf http://localhost:8080/actuator/health || exit 1

# =============================================================================
# Multi-arch build target (amd64 + arm64)
# Build: docker buildx build --platform linux/amd64,linux/arm64 -t neopay/converter:v1.0.0 .
# =============================================================================
