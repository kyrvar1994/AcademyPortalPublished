from django.urls import reverse
from educa.middleware import get_current_domain

def build_absolute_uri(relative_url):
    domain = get_current_domain()
    protocol = 'https' if 'ngrok' in domain else 'http'
    return f"{protocol}://{domain}{relative_url}"