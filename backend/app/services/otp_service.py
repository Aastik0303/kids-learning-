"""The emailed sign-in code: issuing one, and spending it.

A password proves what somebody knows. It is also the thing that leaks - reused
from another site, guessed, read off a note by the router - and this account
holds a child's name, birth month and whole learning history. The code proves
they still hold the address the account is on, which a stolen password does not
give anybody.

The shape of it:

* `POST /auth/login` checks the password and, if OTP is on, returns a
  **challenge** rather than a session. There is no session yet, and nothing in
  the challenge can be turned into one.
* The code goes to the account's address and nowhere else. It is never in the
  response - that would make the second factor a formality - except on a
  development machine with no mailer, where it is logged and returned so the
  flow can be finished at all. That door is bolted shut in production.
* `POST /auth/otp/verify` spends the challenge and issues the session.

**Google sign-in does not go through any of this.** Google has already proved
the address, with whatever second factor that account carries, and a code on top
of that is friction which buys nothing.

Three limits, and each closes something specific:

* **attempts per challenge** - six digits is one of a million only while the
  number of guesses is small. Five, and then the challenge is dead.
* **sends per challenge, with a cooldown** - "send it again" is otherwise a
  button that mails a stranger as fast as it can be pressed.
* **the account throttle**, shared with password guessing, so an attacker who
  has the password cannot grind codes across fresh challenges either.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db.repositories import security
from app.services import mailer
from app.services.errors import app_error


logger = logging.getLogger(__name__)


def enabled() -> bool:
    return get_settings().auth_otp_enabled


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ttl() -> timedelta:
    return timedelta(minutes=max(1, get_settings().auth_otp_ttl_minutes))


def new_code() -> str:
    """A numeric code, uniformly random.

    `secrets`, not `random`: the second one is a Mersenne Twister seeded from
    the clock, and a few of its outputs give away the rest of them. Zero-padded
    so "004821" is as likely as any other, and the length is not a hint.
    """
    length = max(4, get_settings().auth_otp_length)
    return f"{secrets.randbelow(10**length):0{length}d}"


def new_challenge_id() -> str:
    return secrets.token_urlsafe(32)


def masked(email: str) -> str:
    """The address, enough to recognise and not enough to learn.

    The parent is looking at a screen that says "we sent a code" and needs to
    know *where*, sometimes because the account is on an old address. Printing
    it in full would put it on the screen of whoever has the password.
    """
    name, _, domain = email.partition("@")
    if not domain:
        return "your email"
    head = name[:2] if len(name) > 3 else name[:1]
    return f"{head}{'•' * max(3, len(name) - len(head))}@{domain}"


def _deliver(*, email: str, code: str) -> str | None:
    """Send the code. Returns it only where it could not be sent and may be shown.

    Outside production a machine with no SMTP configured logs the code and hands
    it back, which is the same shape `forgot_password` has always had: the flow
    stays completable and testable without a mail account. In production an
    unconfigured mailer refuses the sign-in rather than skipping the factor,
    because "we could not send the code so we let them in" is not a fallback,
    it is the feature being off.
    """
    settings = get_settings()
    production = settings.env.lower() == "production"

    if not mailer.configured(settings):
        if production:
            logger.error(
                "A sign-in code could not be sent: SMTP is not configured. "
                "Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD, or set AUTH_OTP_ENABLED=0."
            )
            raise app_error(
                "MAIL_NOT_CONFIGURED",
                "We cannot send your sign-in code right now. Please try again later.",
                503,
            )
        logger.warning("No SMTP configured; sign-in code for %s is %s", email, code)
        return code

    try:
        mailer.send(
            mailer.sign_in_code(to=email, code=code, minutes=get_settings().auth_otp_ttl_minutes)
        )
    except mailer.MailNotSent as error:
        # Said plainly. The alternative is a parent watching a code box for a
        # mail that was never going to arrive.
        raise app_error(
            "MAIL_NOT_SENT",
            "We could not send your sign-in code just now. Please try again in a moment.",
            502,
        ) from error
    return None


def issue(session, *, parent, now: datetime | None = None) -> tuple[str, str | None]:
    """Open a challenge for this parent and send them the code.

    Returns the challenge handle, and the code itself only on a development
    machine with no mailer. Runs on the caller's session so the row and the
    throttle move in one transaction.
    """
    now = now or _now()
    code = new_code()
    challenge_id = new_challenge_id()
    security.create_challenge(
        session, parent_id=parent.id, challenge_id=challenge_id, code=code, now=now, ttl=ttl()
    )
    return challenge_id, _deliver(email=parent.email, code=code)


def resend(session, *, challenge, email: str, now: datetime | None = None) -> str | None:
    """A fresh code on the same challenge, behind a cooldown and a ceiling."""
    now = now or _now()
    settings = get_settings()

    waited = (now - _aware(challenge.last_sent_at)).total_seconds()
    remaining = settings.auth_otp_resend_cooldown_seconds - waited
    if remaining > 0:
        raise app_error(
            "OTP_RESEND_TOO_SOON",
            f"Please wait {int(remaining) + 1} more seconds before asking for another code.",
            429,
        )
    if challenge.sends >= settings.auth_otp_max_sends:
        raise app_error(
            "OTP_TOO_MANY_SENDS",
            "We have sent that code a few times already. Please sign in again.",
            429,
        )

    code = new_code()
    security.record_resend(session, challenge=challenge, code=code, now=now)
    return _deliver(email=email, code=code)


def _aware(value: datetime) -> datetime:
    """SQLite hands back a naive datetime; it is UTC, and the arithmetic above
    needs it to say so."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
