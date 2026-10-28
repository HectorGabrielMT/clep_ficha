"""INSPECCIONES"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError 
from appAdministrador.models import tbl_inspeccion 
from django.contrib.auth.decorators import login_required


@login_required
def vista_inspecciones(request):

    inspecciones = tbl_inspeccion.objects.all() 

    context = {
        'inspecciones': inspecciones, 
    }
    
    return render(request, 'dataMaestra/inspeccion/panel_inspeccion.html', context)




@login_required
def editar_inspeccion(request, inspeccion_id):
    inspeccion = get_object_or_404(tbl_inspeccion, pk=inspeccion_id)

    contexto = {
        'inspeccion': inspeccion,
        'errores': {},
        'valor_codigo': inspeccion.codigo_inspeccion,
        'valor_nombre': inspeccion.nombre_inspeccion,
        'valor_notifica': inspeccion.notificacionA_inspeccion,
        'valor_descripcion': inspeccion.descripcion_inspeccion,
        'valor_color_inspeccion': inspeccion.color_inspeccion,
    }

    if request.method != 'POST':
        return render(request, 'dataMaestra/inspeccion/formulario_inspeccion.html', contexto)

    # Captura de datos del formulario
    notifica = request.POST.get('notifica', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()

    errores = {}


    # Si hay errores, persistimos datos y mostramos mensajes
    if errores:
        contexto.update({
            'errores': errores,
            'valor_notifica': notifica,
            'valor_descripcion': descripcion,
        })
        messages.warning(request, "Por favor corrija los errores del formulario.")
        return render(request, 'dataMaestra/inspeccion/formulario_inspeccion.html', contexto)

    # Guardado seguro
    inspeccion.notificacionA_inspeccion = notifica
    inspeccion.descripcion_inspeccion = descripcion

    try:
        inspeccion.save()
        messages.success(request, "Inspección actualizada correctamente.")
        return redirect('inspecciones')
    except Exception as error_guardado:
        errores['error_bd'] = f"Ocurrió un error al guardar los cambios: {error_guardado}"
        contexto['errores'] = errores
        messages.error(request, errores['error_bd'])
        return render(request, 'dataMaestra/inspeccion/formulario_inspeccion.html', contexto)
    


    
    

