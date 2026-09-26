#!/bin/sh
# Generates the broker password file from environment variables, then starts Mosquitto.
set -eu

passwd_file=/mosquitto/data/passwd

: "${MQTT_INGEST_PASSWORD:?MQTT_INGEST_PASSWORD is required}"
: "${MQTT_SIMULATOR_PASSWORD:?MQTT_SIMULATOR_PASSWORD is required}"

rm -f "$passwd_file"
touch "$passwd_file"
chmod 0700 "$passwd_file"
mosquitto_passwd -b "$passwd_file" telemetry-ingest "$MQTT_INGEST_PASSWORD"
mosquitto_passwd -b "$passwd_file" fleet-simulator "$MQTT_SIMULATOR_PASSWORD"
chown mosquitto:mosquitto "$passwd_file"

exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
