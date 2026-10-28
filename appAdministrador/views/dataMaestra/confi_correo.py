from django.shortcuts import render, redirect
from django.contrib import messages
from appAdministrador.models import ConfiguracionEmail
import logging

logger = logging.getLogger(__name__)

def actualizar_configuracion_email(request):
    config, created = ConfiguracionEmail.objects.get_or_create(pk=1)

    if request.method == 'POST':
        config.servidor_smtp = request.POST.get('servidor_smtp')
        config.puerto = request.POST.get('puerto')
        config.usuario_email = request.POST.get('usuario_email')
        config.password_aplicacion = request.POST.get('password_aplicacion')
        # Forzamos TLS siempre a True por seguridad
        config.usar_tls = True 
        config.save()
        
        messages.success(request, "Servidor de correo configurado correctamente.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    return render(request, 'tu_plantilla.html', {'config_email': config})



