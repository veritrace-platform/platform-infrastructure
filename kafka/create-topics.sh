#!/usr/bin/env bash
# Creates the Kafka topics defined in docs/contracts/messaging.md. Safe to run repeatedly.
set -euo pipefail

bootstrap="${KAFKA_BOOTSTRAP:?KAFKA_BOOTSTRAP is required}"
topics_cmd=/opt/kafka/bin/kafka-topics.sh

seven_days_ms=604800000
fourteen_days_ms=1209600000

create() {
  local name="$1" partitions="$2" retention_ms="$3"
  "$topics_cmd" --bootstrap-server "$bootstrap" --create --if-not-exists \
    --topic "$name" --partitions "$partitions" --replication-factor 1 \
    --config "retention.ms=${retention_ms}"
}

create iot.telemetry.raw 6 "$seven_days_ms"
create iot.telemetry.dlq 1 "$fourteen_days_ms"
create shipment.events 6 -1
create telemetry.incidents 6 -1

"$topics_cmd" --bootstrap-server "$bootstrap" --list
