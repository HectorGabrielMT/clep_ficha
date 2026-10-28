import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from appAdministrador.models import tbl_Unidad
from django.contrib.auth.decorators import login_required


import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from appAdministrador.models import tbl_Unidad
from django.contrib.auth.decorators import login_required

@login_required
def ordenar_capitulos(request):
    plantilla = 'dataMaestra/ordenar_capitulos/panel_ordenar_capitulos.html'

    if request.method == 'GET':
        try:
            # Obtenemos los capítulos únicos basándonos en el campo 'capitulo'
            datos_capitulos = (
                tbl_Unidad.objects
                .values('capitulo')
                .annotate(orden_maximo=Max('orden'))
                .order_by('orden_maximo', 'capitulo')
            )

            unidades = tbl_Unidad.objects.all().order_by('capitulo', 'orden')

            # Adaptado para usar el nombre del capítulo como identificador en la lista
            lista_capitulos = [
                {'nombre': capitulo['capitulo'], 'id': indice + 1}
                for indice, capitulo in enumerate(datos_capitulos)
            ]

            # Cambiamos unidad.id por unidad.id_unidad según el nuevo modelo
            lista_unidades = [
                {
                    'id': unidad.id_unidad,  # <--- Cambio aquí
                    'capitulo_nombre': unidad.capitulo,
                    'unidad_nombre': unidad.unidad,
                    'orden': unidad.orden,
                }
                for unidad in unidades
            ]

            contexto = {
                'capitulos': lista_capitulos,
                'unidades': lista_unidades,
            }
            return render(request, plantilla, contexto)

        except Exception as error:
            messages.error(request, "Error al cargar los capítulos.")
            print(f"Error al cargar los capítulos: {error}")
            return render(request, plantilla, {})

    elif request.method == 'POST':
        try:
            datos_recibidos = json.loads(request.body)
            orden_capitulos = datos_recibidos.get('chapters_order', [])
        except json.JSONDecodeError:
            messages.error(request, "Error al procesar los datos.")
            return redirect('ordenar_capitulos')

        if not orden_capitulos:
            messages.warning(request, "La lista de capítulos está vacía.")
            return redirect('ordenar_capitulos')

        try:
            with transaction.atomic():
                incremento_base = 1000

                for indice, nombre_capitulo in enumerate(orden_capitulos):
                    nuevo_orden_base = (indice + 1) * incremento_base

                    # Filtramos todas las unidades que pertenecen a este capítulo
                    unidades_capitulo = (
                        tbl_Unidad.objects
                        .filter(capitulo=nombre_capitulo)
                        .order_by('orden')
                    )

                    for subindice, unidad in enumerate(unidades_capitulo):
                        nuevo_orden = nuevo_orden_base + (subindice + 1)
                        # No es necesario cambiar la lógica de save, 
                        # Django reconoce automáticamente id_unidad como la PK
                        unidad.orden = nuevo_orden
                        unidad.save(update_fields=['orden'])

            messages.success(request, "Orden de capítulos guardado correctamente.")

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('ordenar_capitulos')

        except Exception as error:
            messages.error(request, f"Ocurrió un error al guardar el orden: {error}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False}, status=500)
            return redirect('ordenar_capitulos')

    else:
        messages.error(request, "Método no permitido.")
        return redirect('ordenar_capitulos')