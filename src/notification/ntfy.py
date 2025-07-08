import requests
from config import settings


def send(name: str, message: str, url="", headers=None, method="POST"):
    """
    发送消息到ntfy服务器
    
    Args:
        name: 主题名称
        message: 消息内容或二进制数据
        url: 可选的服务器URL
        headers: 可选的HTTP头
        method: HTTP方法，默认为POST，可以是PUT
        
    Returns:
        服务器响应的JSON数据
    """
    api = f'https://ntfy.sh/{name}'
    if url:
        api = f'{url}/{name}'

    if not headers:
        headers = {}

    if settings.AUTH_TOKEN and not api.startswith('https://ntfy.sh'):
        headers.update({
            "Authorization": f"Bearer {settings.AUTH_TOKEN}"
        })
    
    # 如果消息是字符串，确保使用UTF-8编码
    if isinstance(message, str):
        message = message.encode('utf-8')
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'text/plain; charset=utf-8'
    
    # 如果没有指定Content-Type，且消息是文本，添加UTF-8编码
    if isinstance(message, bytes) and 'Content-Type' in headers and headers['Content-Type'].startswith('text/'):
        if 'charset=' not in headers['Content-Type']:
            headers['Content-Type'] = f"{headers['Content-Type']}; charset=utf-8"

    r = requests.request(method, api, data=message, headers=headers)
    print(api, r.text)

    return r.json()
