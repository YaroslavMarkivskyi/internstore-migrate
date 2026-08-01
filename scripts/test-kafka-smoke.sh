#!/usr/bin/env bash
# Smoke-tests the Kafka broker from docker-compose: publishes one message to
# order-events and confirms a consumer reads it back. Confirms the broker
# and its topics are alive — no business logic, no real consumer code yet.
#
# Requires: docker compose stack up (`docker compose up -d kafka
# kafka-topic-init`) and the `kafka` container healthy.
set -euo pipefail

TOPIC="order-events"
MESSAGE="smoke-test-$(date +%s)"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

echo "--- Publishing '$MESSAGE' to $TOPIC ---"
echo "$MESSAGE" | docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" \
  || fail "producer could not publish to $TOPIC"

echo "--- Consuming from $TOPIC ---"
RECEIVED=$(docker compose exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" \
  --from-beginning --max-messages 1 --timeout-ms 15000 2>/dev/null) \
  || fail "consumer did not receive any message from $TOPIC within timeout"

echo "$RECEIVED" | grep -qF "$MESSAGE" || fail "consumed message does not match what was published (got: '$RECEIVED')"
pass "producer -> $TOPIC -> consumer round-trip"
