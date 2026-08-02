#!/usr/bin/env bash
# Smoke-tests the Kafka broker from docker-compose: publishes one message to
# order-events and confirms a consumer reads it back. Confirms the broker
# and its topics are alive — no business logic, no real consumer code yet.
#
# Reads from a captured start offset (via kafka-get-offsets.sh), not
# --from-beginning and not a consumer group's committed offset. After any
# saga script run (test-reservation-saga.sh, test-notifications-saga.sh,
# etc.) order-events has a backlog of real events; a plain
# --from-beginning/no-group consumer would either read some unrelated old
# message or have to burn through the whole backlog to reach ours. Capturing
# the log-end-offset immediately before publishing and consuming from
# exactly that offset (via --partition/--offset, no consumer group at all)
# guarantees we only ever see the message this run just published,
# regardless of backlog size — and, since there's no consumer group,
# nothing to leak between repeated runs either.
#
# Requires: curl, jq, docker compose stack up (`docker compose up -d kafka
# kafka-topic-init`) and the `kafka` container healthy.
set -euo pipefail

TOPIC="order-events"
MARKER="smoke-test-$(date +%s)-$$"
MESSAGE="{\"event_id\":\"$MARKER\",\"event_type\":\"SmokeTest\",\"payload\":{\"marker\":\"$MARKER\"}}"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

kafka_exec() { docker compose exec -T kafka "$@"; }

echo "--- Capturing current end offset of $TOPIC ---"
START_OFFSET=$(kafka_exec /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" --time -1 \
  | cut -d: -f3 | tr -d '\r') \
  || fail "could not read end offset of $TOPIC"
[ -n "$START_OFFSET" ] || fail "empty end offset for $TOPIC"

echo "--- Publishing '$MARKER' to $TOPIC ---"
echo "$MESSAGE" | kafka_exec /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" \
  || fail "producer could not publish to $TOPIC"

echo "--- Consuming from $TOPIC starting at offset $START_OFFSET ---"
RECEIVED=$(kafka_exec /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" \
  --partition 0 --offset "$START_OFFSET" --max-messages 1 --timeout-ms 15000 2>/dev/null) \
  || fail "consumer did not receive any message from $TOPIC within timeout"

echo "$RECEIVED" | jq -e ".event_type == \"SmokeTest\" and .payload.marker == \"$MARKER\"" >/dev/null \
  || fail "consumed message does not match what was published (got: '$RECEIVED')"
pass "producer -> $TOPIC -> consumer round-trip"
