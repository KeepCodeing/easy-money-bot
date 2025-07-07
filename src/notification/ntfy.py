import requests
from config import settings


def send(name: str, message: str, url="", headers=None):
    api = f'https://ntfy.sh/{name}'
    if url:
        api = f'{url}/{name}'

    if not headers:
        headers = {}


    if settings.AUTH_TOKEN and not api.startswith('https://ntfy.sh'):
        headers.update({
            "Authorization": f"Bearer {settings.AUTH_TOKEN}"
        })

    r = requests.post(api,  data=message, headers=headers)
    print(api, r.text)

    return r.json()
