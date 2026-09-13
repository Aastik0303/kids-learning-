"""Sending email, over SMTP, with the credentials from the environment.

Two messages leave this app, and both of them are the difference between a
parent being able to get into their account and not: the **sign-in code** and
the **password-reset link**. There was no mailer at all until now - the reset
flow handed its token back in the HTTP response outside production and could not
be completed in production at all - so this closes that as well as carrying the
new code.

Some decisions worth stating, because each was a fork:

* **The port decides the encryption**, which is how every provider documents it:
  465 is implicit TLS, everything else is a plain connection immediately
  upgraded with STARTTLS, and an upgrade that fails is a failure rather than a
  quiet fall back to cleartext. A sign-in code sent in the clear is not a second
  factor.
* **It is sent synchronously.** A background thread would make sign-in faster
  and would also make "we could not send your code" unsayable - the parent would
  sit in front of a code box waiting for a mail that was never going to arrive.
  Sign-in happens once a month; being honest about it is worth the second.
* **The body says what to do and nothing about the child.** No name, no class,
  no progress. Mail is the least private thing this system touches, it is
  forwarded and screenshotted, and a code needs none of that to work.
* **A failure raises.** It never returns quietly, because every caller here has
  something it must not do if the mail did not go - chiefly, tell the parent to
  go and look for it.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from app.config import Settings, get_settings
from app.services.errors import app_error


logger = logging.getLogger(__name__)

# Implicit TLS. Anything else is upgraded with STARTTLS.
SMTPS_PORT = 465


class MailNotSent(Exception):
    """The provider refused, or could not be reached."""


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    # Optional: a plain-text-only mail is perfectly good, and some of these are
    # read by a client that will not render anything else.
    html: str | None = None


def configured(settings: Settings | None = None) -> bool:
    """Whether there is enough here to send anything at all.

    Callers ask before they promise a parent that something is on its way.
    """
    settings = settings or get_settings()
    return bool(settings.smtp_host.strip() and _from_address(settings))


def _from_address(settings: Settings) -> str:
    """The envelope sender. Falls back to the username, which for Gmail, Zoho,
    Fastmail and most others is the address anyway - one fewer thing to set
    wrong."""
    return (settings.smtp_from_email.strip() or settings.smtp_username.strip()).strip()


def _build(message: Message, settings: Settings) -> EmailMessage:
    mail = EmailMessage()
    mail["Subject"] = message.subject
    mail["From"] = formataddr((settings.smtp_from_name.strip() or None, _from_address(settings)))
    mail["To"] = message.to
    # A stable domain on the id rather than the machine's hostname, which on a
    # container is a random hex string and reads as spam.
    mail["Message-ID"] = make_msgid(domain=_from_address(settings).split("@")[-1] or None)
    # Neither of these is a mailing list and neither should ever be answered by
    # a machine that files it as a bulk message.
    mail["Auto-Submitted"] = "auto-generated"
    mail.set_content(message.text)
    if message.html:
        mail.add_alternative(message.html, subtype="html")
    return mail


def send(message: Message) -> None:
    """Send one message, or raise.

    `MailNotSent` on anything that went wrong with the provider; an app error
    with a 503 when this deployment has no mailer configured, because that is
    this server's fault and not the parent's.
    """
    settings = get_settings()
    if not configured(settings):
        raise app_error(
            "MAIL_NOT_CONFIGURED",
            "We cannot send email from this server yet. Please try again later.",
            503,
        )

    mail = _build(message, settings)
    context = ssl.create_default_context()
    timeout = max(1, settings.smtp_timeout_seconds)

    try:
        if settings.smtp_port == SMTPS_PORT:
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout, context=context
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)

        with server:
            server.ehlo()
            if settings.smtp_port != SMTPS_PORT:
                # Not optional, and not attempted-and-shrugged-off: if the
                # server will not upgrade, the alternative is sending a sign-in
                # code across the internet in the clear.
                server.starttls(context=context)
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(mail)
    except Exception as error:  # noqa: BLE001 - smtplib raises a wide family,
        # and a DNS failure or a refused socket is not in it at all.
        # The address is logged because an operator needs to know which send
        # failed; the body never is, because the body is a credential.
        logger.warning("Could not send '%s' to %s: %s", message.subject, message.to, error)
        raise MailNotSent(str(error)) from error

    logger.info("Sent '%s' to %s", message.subject, message.to)


# --------------------------------------------------------------------------
# The two messages this app sends
# --------------------------------------------------------------------------


def sign_in_code(*, to: str, code: str, minutes: int) -> Message:
    """The second factor. Deliberately dull, and deliberately warns.

    The warning line is there because this is the message an attacker causes to
    be sent: they have the password and are waiting for someone to read out the
    code. A parent who was not signing in needs to be told what that means
    without being told to panic.
    """
    text = (
        f"Your Saksham IQ sign-in code is {code}\n\n"
        f"It works for the next {minutes} minutes and can be used once.\n\n"
        "If you were not signing in, someone else may know your password. "
        "Do not share this code with anyone - change your password instead.\n"
    )
    html = f"""\
<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:420px">
  <p style="font-size:16px;color:#333">Your Saksham IQ sign-in code is</p>
  <p style="font-size:34px;font-weight:800;letter-spacing:.18em;margin:16px 0;color:#111">{code}</p>
  <p style="font-size:14px;color:#555">It works for the next {minutes} minutes and can be used once.</p>
  <p style="font-size:13px;color:#777;margin-top:24px">
    If you were not signing in, someone else may know your password.
    Do not share this code with anyone &mdash; change your password instead.
  </p>
</div>"""
    return Message(to=to, subject=f"{code} is your Saksham IQ sign-in code", text=text, html=html)


def password_reset(*, to: str, link: str, minutes: int) -> Message:
    text = (
        "Someone asked to reset the password on your Saksham IQ account.\n\n"
        f"{link}\n\n"
        f"The link works for the next {minutes} minutes and can be used once.\n\n"
        "If this was not you, you can ignore this email - nothing has changed.\n"
    )
    html = f"""\
<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:420px">
  <p style="font-size:16px;color:#333">Someone asked to reset the password on your Saksham IQ account.</p>
  <p style="margin:20px 0">
    <a href="{link}" style="background:#2f9e5e;color:#fff;padding:14px 22px;border-radius:14px;
       text-decoration:none;font-weight:700;display:inline-block">Choose a new password</a>
  </p>
  <p style="font-size:14px;color:#555">The link works for the next {minutes} minutes and can be used once.</p>
  <p style="font-size:13px;color:#777;margin-top:24px">
    If this was not you, you can ignore this email &mdash; nothing has changed.
  </p>
</div>"""
    return Message(to=to, subject="Reset your Saksham IQ password", text=text, html=html)
