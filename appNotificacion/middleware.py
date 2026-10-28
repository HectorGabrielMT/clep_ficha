import zoneinfo
import urllib.parse
from django.utils import timezone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.COOKIES.get('django_timezone')
        if tzname:
            # El valor de la cookie puede llegar percent-encoded (ej. "America%2FCaracas")
            # porque se guardó con encodeURIComponent en el navegador; los navegadores
            # no lo decodifican al reenviarlo, así que hay que hacerlo aquí.
            tzname = urllib.parse.unquote(tzname)
            try:
                timezone.activate(zoneinfo.ZoneInfo(tzname))
            except Exception:
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)