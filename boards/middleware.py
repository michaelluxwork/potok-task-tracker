from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent
from django.db import OperationalError, DatabaseError
from django.http import HttpResponse

class BoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.get_host()
        if request.method == 'POST':
            if request.content_type != 'application/x-www-form-urlencoded':
                return self.headers(HttpResponse('Поддерживается только отправка формы.', status=415, content_type='text/plain; charset=utf-8'))
            try:
                length = int(request.META.get('CONTENT_LENGTH') or 0)
                if length > 32768:
                    return self.headers(HttpResponse('Форма слишком большая. Сократите описание.', status=413))
                if any(len(values) != 1 for _, values in request.POST.lists()):
                    return self.headers(HttpResponse('Повторяющиеся поля формы недопустимы.', status=400))
            except (ValueError, RequestDataTooBig, TooManyFieldsSent):
                return self.headers(HttpResponse('Некорректная или слишком большая форма.', status=400))
        response = self.get_response(request)
        return self.headers(response)

    @staticmethod
    def headers(response):
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, (OperationalError, DatabaseError)):
            from .views import error_response
            return error_response(request, 503, 'Хранилище временно недоступно. Проверьте доску перед повторной отправкой.')
