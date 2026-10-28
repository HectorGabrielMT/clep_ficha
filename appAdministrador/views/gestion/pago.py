
from appAdministrador.models import tbl_CCPP, tbl_Pago
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from datetime import datetime





@transaction.atomic
def gestion_pagos(request, id_ccpp):
    ccpp = get_object_or_404(tbl_CCPP, pk=id_ccpp)
    
    if request.method == 'POST':
        try:
            # 1. ACTUALIZAR tbl_CCPP (Cabecera y Notas)
            ccpp.FechaContrato = request.POST.get('FechaContrato') or None
            ccpp.FechaInicioControl = request.POST.get('FechaInicioControl') or None
            ccpp.CantViviendas = int(request.POST.get('CantViviendas') or 0)
            ccpp.LibroEdificio = request.POST.get('LibroEdificio') == 'True'
            ccpp.estado = request.POST.get('estado') == 'activo'
            ccpp.NumeroContrato = request.POST.get('NumeroContrato')
            
            # Mapeo exacto de notas a columnas de tbl_CCPP
            ccpp.nota_adaptacionLE = request.POST.get('nota_adaptacionLE', '')
            ccpp.nota_controlVerificacion = request.POST.get('nota_controlVerificacion', '')
            ccpp.nota_emisionInforme = request.POST.get('nota_emisionInforme', '')
            ccpp.nota_visitaTecnico = request.POST.get('nota_visitaTecnico', '')
            ccpp.nota_asistenciaReunion = request.POST.get('nota_asistenciaReunion', '')
            ccpp.nota_ampliacionEdificio = request.POST.get('nota_ampliacionEdificio', '')
            ccpp.nota_otrosConceptos = request.POST.get('nota_otrosConceptos', '')

            if 'ArchivoContrato_CCPP' in request.FILES:
                ccpp.ArchivoContrato = request.FILES['ArchivoContrato_CCPP']
            
            ccpp.save()

            # 2. PROCESAR tbl_Pago (Filas de la tabla)
            ids_pagos = request.POST.getlist('pago_id[]')
            anios = request.POST.getlist('anio[]')
            meses = request.POST.getlist('mes[]')
            
            adaptacion = request.POST.getlist('AdaptacionLE[]')
            control = request.POST.getlist('ControlVerificacion[]')
            emision = request.POST.getlist('EmisionInforme[]')
            visita = request.POST.getlist('VisitaTecnico[]')
            asistencia = request.POST.getlist('AsistenciaReunion[]')
            ampliacion = request.POST.getlist('AmpliacionEdificio[]')
            otros = request.POST.getlist('OtrosConceptos[]')
            refs_factura = request.POST.getlist('RefFactura[]')

            # Eliminar registros que ya no están en la tabla
            ids_validos = [int(i) for i in ids_pagos if i != 'nuevo']
            tbl_Pago.objects.filter(id_ccpp=ccpp).exclude(id_pago__in=ids_validos).delete()

            # Crear o actualizar cada fila
            for i in range(len(anios)):
                datos_pago = {
                    'anio': int(anios[i]),
                    'mes': meses[i],
                    'AdaptacionLE': float(adaptacion[i] or 0),
                    'ControlVerificacion': float(control[i] or 0),
                    'EmisionInforme': float(emision[i] or 0),
                    'VisitaTecnico': float(visita[i] or 0),
                    'AsistenciaReunion': float(asistencia[i] or 0),
                    'AmpliacionEdificio': float(ampliacion[i] or 0),
                    'OtrosConceptos': float(otros[i] or 0),
                    'RefFactura': refs_factura[i],
                }

                archivo_key = f'archivo_pago_{i}'
                archivo_subido = request.FILES.get(archivo_key)

                if ids_pagos[i] == 'nuevo':
                    pago_obj = tbl_Pago(id_ccpp=ccpp, **datos_pago)
                else:
                    pago_obj = get_object_or_404(tbl_Pago, pk=ids_pagos[i])
                    for key, value in datos_pago.items():
                        setattr(pago_obj, key, value)
                
                if archivo_subido:
                    pago_obj.ArchivoFactura = archivo_subido
                
                pago_obj.save()

            messages.success(request, f"Gestión de {ccpp.nombre} guardada con éxito.")
            return redirect('panel_pagos', id_ccpp)

        except Exception as e:
            messages.error(request, f"Error al guardar: {str(e)}")
            return redirect('panel_pagos', id_ccpp)

    # Lógica GET
    pagos = tbl_Pago.objects.filter(id_ccpp=ccpp).order_by('-anio', 'id_pago')
    anio_actual = datetime.now().year
    context = {
        'ccpp': ccpp,
        'pagos': pagos,
        'rango_anios': range(anio_actual - 5, anio_actual + 6),
        'meses_lista': ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
    }
    return render(request, 'gestion/pago/formulario_pago.html', context)






