from django.shortcuts import render, redirect
from django.contrib import messages
from appAdministrador.models import tbl_Correo, ConfiguracionEmail
from django.contrib.auth.decorators import login_required
from django.db import transaction


from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required

@login_required
def correo(request):
    NOMBRE_PLANTILLA = 'dataMaestra/correo/panel_correo.html'
    RUTA_REDIRECCION = 'correo'

    # --- LÓGICA PARA PROCESAR EL FORMULARIO (POST) ---
    if request.method == 'POST':
        asunto = request.POST.get('asunto', '').strip()
        cuerpo = request.POST.get('cuerpo', '').strip()
        errores = {}

        # Validaciones básicas
        if not asunto:
            errores['asunto'] = "El campo 'Asunto' no puede estar vacío."
        elif len(asunto) > 255:
            errores['asunto'] = "El asunto no puede exceder los 255 caracteres."

        if not cuerpo:
            errores['cuerpo'] = "El campo 'Cuerpo' no puede estar vacío."

        if errores:
            # Si hay errores, recuperamos la configuración para no romper la vista
            config_email = ConfiguracionEmail.objects.first()
            contexto = {
                'valor_asunto': asunto,
                'valor_cuerpo': cuerpo,
                'errores': errores,
                'config_email': config_email,
            }
            messages.warning(request, "Por favor corrija los errores del formulario.")
            return render(request, NOMBRE_PLANTILLA, contexto)

        try:
            with transaction.atomic():
                plantilla, creada = tbl_Correo.objects.update_or_create(
                    pk=1,
                    defaults={'asunto': asunto, 'cuerpo': cuerpo}
                )
                accion = "creada" if creada else "actualizada"
                messages.success(request, f"Plantilla de correo {accion} con éxito.")
                return redirect(RUTA_REDIRECCION)

        except Exception as error_guardado:
            messages.error(request, f"Ocurrió un error al guardar la plantilla: {error_guardado}")
            return redirect(RUTA_REDIRECCION)

    # --- LÓGICA PARA CARGAR LA VISTA (GET) ---
    
    # 1. Obtenemos la configuración de email de forma independiente
    config_email = ConfiguracionEmail.objects.first()

    # 2. Intentamos obtener la plantilla existente
    try:
        plantilla = tbl_Correo.objects.get(pk=1)
        valor_asunto = plantilla.asunto
        valor_cuerpo = plantilla.cuerpo
    except tbl_Correo.DoesNotExist:
        valor_asunto = ''
        valor_cuerpo = ''

    contexto = {
        'valor_asunto': valor_asunto,
        'valor_cuerpo': valor_cuerpo,
        'errores': {},
        'config_email': config_email,
    }

    return render(request, NOMBRE_PLANTILLA, contexto)

