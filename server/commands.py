"""Bot commands as pure functions (testable without WhatsApp).  Owner: D2.

client <name> | brief <name> | tasks | help | anything else -> pipeline.process_live_message
"""


def handle(sender, body):
    """Return the reply text for an incoming text message."""
    # STUB
    return "Commands: client <name> · brief <name> · tasks · help"
