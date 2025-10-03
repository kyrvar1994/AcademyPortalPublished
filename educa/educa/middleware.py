from threading import local

_request_local = local()

def get_current_request():
    return getattr(_request_local, 'request', None)

def get_current_domain():
    request = get_current_request()
    if request:
        return request.get_host()
    return 'localhost:8000'

class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _request_local.request = request
        response = self.get_response(request)
        del _request_local.request
        return response