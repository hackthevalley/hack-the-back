import requests
from django.conf import settings
from django.core import mail
from django.template import Context, Template

mjml_api_url = settings.MJML_API_URL
mjml_app_id = settings.MJML_APPLICATION_ID
mjml_secret = settings.MJML_SECRET_KEY


def _render_template_with_context(html, context):
    template = Template(html)
    context = Context(context)
    return template.render(context)


def render_mjml(mjml, context=None):
    """
    Provided MJML, render it to HTML. Render with context if context is
    provided.
    """
    req = requests.post(
        mjml_api_url,
        auth=(mjml_app_id, mjml_secret),
        json={"mjml": mjml},
    )
    if req.status_code != 200:
        return None
    html = req.json()["html"]
    if context is None:
        return html
    return _render_template_with_context(html, context)


def send_emails(subject, recipients, plaintext, html):
    """
    Send individual e-mails to each user in the list of recipients with the
    subject as `subject`, and the body as `plaintext` and `html`.
    """
    conn = mail.get_connection()
    conn.open()
    emails = []
    for recipient in recipients:
        html = _render_template_with_context(html, {"user": recipient})
        if plaintext is None:
            email = mail.EmailMessage(subject, html, to=[recipient.email])
            email.content_subtype = "html"
        else:
            email = mail.EmailMultiAlternatives(
                subject, plaintext, to=[recipient.email]
            )
            email.attach_alternative(html, "text/html")
        emails.append(email)
    conn.send_messages(emails)
    conn.close()
