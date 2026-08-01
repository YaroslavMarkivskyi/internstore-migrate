import asyncio

import aiosmtplib
from email.message import EmailMessage

RETRY_DELAYS_SECONDS = (1, 2, 4)


class Mailer:
    """Thin aiosmtplib wrapper. Mailpit is a dev-only SMTP stub — see
    docs/EVENT_BROKER.md's accepted-gaps section — but the retry logic here
    is provider-agnostic and would apply the same way against a real SMTP
    endpoint (SES, etc.) later.

    On exhausted retries this raises rather than swallowing the failure —
    callers must let that propagate out of the Kafka dispatch so the
    consumer loop skips its offset commit (services/notifications/src/notifications/kafka.py),
    giving a natural at-least-once redelivery instead of a silently lost
    email. No outbox is needed here specifically because that commit-after-send
    ordering is sufficient (see the task's own reasoning): there's no
    separate DB write that could get out of sync with the send the way
    Orders/Inventory's domain state could with a bare post-commit publish.
    """

    def __init__(self, host: str, port: int, from_address: str) -> None:
        self._host = host
        self._port = port
        self._from_address = from_address

    async def send_email(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        last_error: Exception | None = None
        for attempt, delay in enumerate((0, *RETRY_DELAYS_SECONDS)):
            if delay:
                await asyncio.sleep(delay)
            try:
                await aiosmtplib.send(message, hostname=self._host, port=self._port)
                return
            except (aiosmtplib.SMTPConnectError, aiosmtplib.SMTPServerDisconnected, OSError) as exc:
                last_error = exc

        raise ConnectionError(f"failed to send email to {to} after {len(RETRY_DELAYS_SECONDS) + 1} attempts") from last_error
