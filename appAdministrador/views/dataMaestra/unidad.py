
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
import re
from django.contrib import messages
from appAdministrador.models import tbl_Unidad, tbl_CCPP, tbl_CCPP_Unidad, tbl_Cronograma, tbl_Ficha
import logging
from django.contrib.auth.decorators import login_required
logger = logging.getLogger(__name__)



@login_required
def vista_unidad(request):
    if request.method != 'GET':
        messages.error(request, "Método no permitido.")
        return render(request, 'dataMaestra/unidad/panel_unidad.html', {})

  #  try:
    # Obtener todas las unidades ordenadas por el campo 'orden'
    lista_unidades = tbl_Unidad.objects.all().order_by('orden')

    # Obtener valores únicos para los filtros
    valores_unidad = (
        tbl_Unidad.objects
        .values_list('unidad', flat=True)
        .distinct()
        .order_by('unidad')
    )

    valores_capitulo = (
        tbl_Unidad.objects
        .values_list('capitulo', flat=True)
        .distinct()
        .order_by('capitulo')
    )

    valores_observacion = (
        tbl_Unidad.objects
        .values_list('observacion', flat=True)
        .distinct()
        .order_by('observacion')
    )

    valores_doc = (
        tbl_Unidad.objects
        .values_list('doc', flat=True)
        .distinct()
        .order_by('doc')
    )
    
    # Nuevos filtros para los campos adicionales
    valores_descripcion = (
        tbl_Unidad.objects
        .values_list('descripcion', flat=True)
        .distinct()
        .order_by('descripcion')
    )
    
    valores_orden = (
        tbl_Unidad.objects
        .values_list('orden', flat=True)
        .distinct()
        .order_by('orden')
    )

    unidades_por_capitulo = {}
    for unidad in lista_unidades:
        if unidad.capitulo not in unidades_por_capitulo:
            unidades_por_capitulo[unidad.capitulo] = 0
        unidades_por_capitulo[unidad.capitulo] += 1

    contexto = {
        'unidades': lista_unidades,
        'valores_unidad': valores_unidad,
        'valores_capitulo': valores_capitulo,
        'valores_observacion': valores_observacion,
        'valores_doc': valores_doc,
        'valores_descripcion': valores_descripcion,  # Nuevo
        'valores_orden': valores_orden,  # Nuevo
        'unidades_por_capitulo': unidades_por_capitulo,
    }

    return render(request, 'dataMaestra/unidad/panel_unidad.html', contexto)

  #  except Exception as error:
  #      logger.exception(f"Error al cargar la vista de unidades: {error}")
   #     messages.error(request, "Ocurrió un error al cargar los datos de unidades. Intente nuevamente más tarde.")
    #    return render(request, 'dataMaestra/unidad/panel_unidad.html', {})






import logging
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse


# Configuración del logger
logger = logging.getLogger(__name__)

LIMITE_CARACTERES = 200
PATRON_DOC = r'^\d{2} \d{2} \d{2}$'


def validar_unidad(nombre_unidad, nombre_capitulo, descripcion, observacion, codigo_doc, unidad_id=None):
    errores = {}

    # Validar nombre de unidad
    if not nombre_unidad:
        errores["unidad"] = "El campo 'Unidad' es obligatorio."
    elif len(nombre_unidad) > LIMITE_CARACTERES:
        errores["unidad"] = f"Máximo {LIMITE_CARACTERES} caracteres permitidos."
    elif unidad_id:
        if tbl_Unidad.objects.filter(unidad=nombre_unidad).exclude(pk=unidad_id).exists():
            errores["unidad"] = "Ya existe otra unidad con ese nombre."
    else:
        if tbl_Unidad.objects.filter(unidad=nombre_unidad).exists():
            errores["unidad"] = "Ya existe una unidad con ese nombre."

    # Validar capítulo
    if not nombre_capitulo:
        errores["capitulo"] = "El campo 'Capítulo' es obligatorio."
    elif len(nombre_capitulo) > LIMITE_CARACTERES:
        errores["capitulo"] = f"Máximo {LIMITE_CARACTERES} caracteres permitidos."

    # Validar descripción
    if descripcion and len(descripcion) > LIMITE_CARACTERES:
        errores["descripcion"] = f"Máximo {LIMITE_CARACTERES} caracteres permitidos."

    # Validar observación
    if observacion and len(observacion) > LIMITE_CARACTERES:
        errores["observacion"] = f"Máximo {LIMITE_CARACTERES} caracteres permitidos."

    # Validar doc
    if codigo_doc:
        doc_limpio = codigo_doc.strip().replace(" ", "")
        # Regla: Debe ser un número de 6 dígitos
        if not (doc_limpio.isdigit() and len(doc_limpio) == 6):
            errores["doc"] = "El DOC debe ser un número de exactamente 6 dígitos."
        else:
            # Regla: Unicidad (excluyendo la unidad actual si es edición)
            query = tbl_Unidad.objects.filter(doc=doc_limpio)
            if unidad_id:
                query = query.exclude(pk=unidad_id)
            if query.exists():
                errores["doc"] = "Este código DOC ya pertenece a otra unidad."

    return errores




from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@login_required
def nueva_unidad(request, id_ccpp):
    if request.method == "GET":
        contexto = {
            "es_edicion": False,
            "unidad_val": "",
            "capitulo_val": "",
            "descripcion_val": "",
            "observacion_val": "",
            "doc_val": "",
            'ccpp_id':id_ccpp
        }
        return render(request, "dataMaestra/unidad/formulario_unidad.html", contexto)

    if request.method == "POST":
        datos = request.POST
        nombre_unidad = datos.get("unidad", "").strip()
        nombre_capitulo = datos.get("capitulo", "").strip()
        descripcion = datos.get("descripcion", "").strip()
        observacion = datos.get("observacion", "").strip()
        codigo_doc = datos.get("doc", "").strip()

        errores = validar_unidad(nombre_unidad, nombre_capitulo, descripcion, observacion, codigo_doc)

        if errores:
            messages.warning(request, "Por favor corrija los errores del formulario.")
            return render(request, "dataMaestra/unidad/formulario_unidad.html", {
                "es_edicion": False,
                "unidad_val": nombre_unidad,
                "capitulo_val": nombre_capitulo,
                "descripcion_val": descripcion,
                "observacion_val": observacion,
                "doc_val": codigo_doc,
                "errores": errores,
                'ccpp_id':id_ccpp
            })

        try:
            # Manejo de campo único opcional: si está vacío, guardar como None
            codigo_doc_limpio = codigo_doc.replace(" ", "") if codigo_doc else None

            with transaction.atomic():
                nueva_unid = tbl_Unidad.objects.create(
                    unidad=nombre_unidad,
                    capitulo=nombre_capitulo,
                    descripcion=descripcion,
                    observacion=observacion,
                    doc=codigo_doc_limpio,
                )
                messages.success(request, "La unidad fue registrada exitosamente.")
                # Redirección directa al editar de la unidad recién creada
                return redirect(reverse("editar_unidad", args=[nueva_unid.pk, id_ccpp]))

        except Exception as error:
            logger.exception("Error al crear unidad: %s", error)
            messages.error(request, f"Ocurrió un error al guardar: {error}")
            return redirect(reverse("nueva_unidad", id_ccpp))







from django.db import transaction, connection
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib import messages
import logging

# Configuración del logger
logger = logging.getLogger(__name__)

@login_required
def editar_unidad(request, unidad_id, id_ccpp):
    # 1. Obtener la unidad existente
    unidad_existente = get_object_or_404(tbl_Unidad, pk=unidad_id)

    # LÓGICA GET: Mostrar el formulario con datos actuales
    if request.method == "GET":
        contexto = {
            "es_edicion": True,
            "unidad_id": unidad_id,
            "unidad_val": unidad_existente.unidad,
            "unidad_nombre": unidad_existente.unidad,
            "capitulo_val": unidad_existente.capitulo,
            "descripcion_val": unidad_existente.descripcion,
            "observacion_val": unidad_existente.observacion,
            "ccpp_id": id_ccpp,
            "doc_val": unidad_existente.doc or "",
        }
        return render(request, "dataMaestra/unidad/formulario_unidad.html", contexto)

    # LÓGICA POST: Procesar la actualización
    if request.method == "POST":
        datos = request.POST
        nombre_unidad = datos.get("unidad", "").strip()
        nombre_capitulo = datos.get("capitulo", "").strip()
        descripcion = datos.get("descripcion", "").strip()
        observacion = datos.get("observacion", "").strip()
        codigo_doc = datos.get("doc", "").strip()

        # Validar datos (asumiendo que tienes esta función definida)
        errores = validar_unidad(nombre_unidad, nombre_capitulo, descripcion, observacion, codigo_doc, unidad_id)

        if errores:
            messages.warning(request, "Por favor corrija los errores del formulario.")
            return render(request, "dataMaestra/unidad/formulario_unidad.html", {
                "es_edicion": True,
                "unidad_id": unidad_id,
                "unidad_val": nombre_unidad,
                "unidad_nombre": unidad_existente.unidad,
                "capitulo_val": nombre_capitulo,
                "descripcion_val": descripcion,
                "observacion_val": observacion,
                "doc_val": codigo_doc,
                "ccpp_id": id_ccpp,
                "errores": errores,
            })

        try:
            # Limpiamos el nuevo código DOC
            codigo_doc_limpio = codigo_doc.replace(" ", "") if codigo_doc else None
            
            with transaction.atomic():
                doc_anterior = unidad_existente.doc
                
                # Si el valor de DOC ha cambiado, necesitamos manejar la integridad referencial
                if doc_anterior != codigo_doc_limpio:
                    with connection.cursor() as cursor:
                        # DESACTIVAR temporalmente la revisión de llaves foráneas en MySQL/MariaDB
                        cursor.execute('SET FOREIGN_KEY_CHECKS = 0;')
                        
                        try:
                            # 1. Actualizar el registro PADRE (Unidad)
                            unidad_existente.unidad = nombre_unidad
                            unidad_existente.capitulo = nombre_capitulo
                            unidad_existente.descripcion = descripcion
                            unidad_existente.observacion = observacion
                            unidad_existente.doc = codigo_doc_limpio
                            unidad_existente.save()

                            # 2. Actualizar los registros HIJOS (Fichas)
                            tbl_Ficha.objects.filter(doc_unidad=doc_anterior).update(doc_unidad=codigo_doc_limpio)
                            
                        finally:
                            # REACTIVAR siempre la revisión de llaves foráneas
                            cursor.execute('SET FOREIGN_KEY_CHECKS = 1;')
                else:
                    # Si el DOC no cambió, simplemente guardamos los demás campos
                    unidad_existente.unidad = nombre_unidad
                    unidad_existente.capitulo = nombre_capitulo
                    unidad_existente.descripcion = descripcion
                    unidad_existente.observacion = observacion
                    unidad_existente.save()

            messages.success(request, "Unidad actualizada correctamente.")
            return redirect(reverse("editar_unidad", kwargs={'unidad_id': unidad_id, 'id_ccpp': id_ccpp}))

        except Exception as error:
            logger.exception("Error al editar unidad %s: %s", unidad_id, error)
            messages.error(request, f"Ocurrió un error al actualizar: {error}")
            return redirect(reverse("editar_unidad", kwargs={'unidad_id': unidad_id, 'id_ccpp': id_ccpp}))








@login_required
def eliminar_unidad(request, unidad_id, id_ccpp):
    # Asegúrate de que 'unidad' sea el nombre correcto en tus urls.py para el listado
    unidad_a_eliminar = get_object_or_404(tbl_Unidad, pk=unidad_id)

    if request.method == 'POST':
        try:
            unidad_a_eliminar.delete()
            messages.success(request, "Unidad eliminada correctamente.")
        except Exception as error:
            messages.error(request, "No se pudo eliminar la unidad.")
    
    return redirect(reverse('gestionUnidades_ccpp_modo', kwargs={'id_ccpp': id_ccpp, 'modo': 'gestion'}))





###################################################################################################


"""
Función para gestionar las unidades asignadas a una CCPP (Centro de Costo/Proyecto/Programa).
Permite agregar o eliminar unidades vinculadas a una CCPP y mantener sincronizados sus cronogramas.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, DatabaseError
from django.shortcuts import get_object_or_404, redirect, render


import logging
logger = logging.getLogger(__name__)


@login_required
def gestionar_unidades_ccpp(request, id_ccpp, modo=None):
    """
    Gestiona unidades asignadas a un CCPP en dos modos:
    - 'gestion': visualización/gestión general.
    - 'asignacion': asignar/quitar unidades y crear/eliminar cronogramas asociados.
    """


    ccpp = get_object_or_404(tbl_CCPP, pk=id_ccpp)

    # Validación defensiva de cantidad de años
    if ccpp.cantidad_anios is None or ccpp.cantidad_anios < 0:
        messages.error(
            request,
            "La configuración de años del CCPP es inválida. Verifique 'cantidad_anios'."
        )
        return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo="gestion")

    modos_permitidos = {"gestion", "asignacion"}
    modo_valido = modo if modo in modos_permitidos else None

    if not modo_valido:
        modo_valido = request.session.get(f"modo_unidades_{id_ccpp}", "gestion")
    else:
        request.session[f"modo_unidades_{id_ccpp}"] = modo_valido

    # Cambio de modo por GET
    if request.method == "GET" and "cambiar_modo" in request.GET:
        nuevo_modo = request.GET.get("modo")
        if nuevo_modo in modos_permitidos:
            request.session[f"modo_unidades_{id_ccpp}"] = nuevo_modo
            modo_valido = nuevo_modo


    if request.method == "POST" and modo_valido == "asignacion":
        # Validar presencia del campo esperado
        if "unidades_seleccionadas" not in request.POST:
            messages.error(request, "No se recibieron unidades seleccionadas.")
            return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo=modo_valido)

        try:
            # Normalizar y validar IDs recibidos
            ids_crudos = request.POST.getlist("unidades_seleccionadas")
            ids_seleccionadas = set()
            for raw in ids_crudos:
                try:
                    ids_seleccionadas.add(int(raw))
                except (ValueError, TypeError):
                    # Ignorar entradas inválidas, pero registrar
                    logger.warning(
                        "ID de unidad inválido recibido para CCPP %s: %s",
                        id_ccpp, raw
                    )

            # Obtener actuales en una sola consulta
            ids_actuales = set(
                tbl_CCPP_Unidad.objects
                .filter(ccpp=ccpp)
                .values_list("unidad_id", flat=True)
            )

            # Calcular diferencias
            ids_a_quitar = ids_actuales - ids_seleccionadas
            ids_a_agregar = ids_seleccionadas - ids_actuales

            # Validar que las unidades a agregar existan realmente
            if ids_a_agregar:
                ids_existentes = set(
                    tbl_Unidad.objects
                    .filter(id_unidad__in=ids_a_agregar)
                    .values_list("id_unidad", flat=True)
                )
                ids_inexistentes = ids_a_agregar - ids_existentes
                if ids_inexistentes:
                    messages.error(
                        request,
                        f"Algunas unidades no existen: {sorted(ids_inexistentes)}."
                    )
                    return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo=modo_valido)

            with transaction.atomic():
                # Quitar relaciones y cronogramas asociados
                if ids_a_quitar:
                    # Eliminar cronogramas primero para mantener integridad
                    deleted_cronos, _ = tbl_Cronograma.objects.filter(
                        id_ccpp=ccpp,
                        id_unidad_id__in=ids_a_quitar
                    ).delete()

                    deleted_rel, _ = tbl_CCPP_Unidad.objects.filter(
                        ccpp=ccpp,
                        unidad_id__in=ids_a_quitar
                    ).delete()

                    logger.info(
                        "CCPP %s: quitadas %s relaciones y %s cronogramas.",
                        id_ccpp, deleted_rel, deleted_cronos
                    )

                # Agregar nuevas relaciones y cronogramas
                if ids_a_agregar:
                    # Recuperar objetos unidad existentes (ya validados)
                    unidades_existentes = list(
                        tbl_Unidad.objects.filter(id_unidad__in=ids_a_agregar)
                    )

                    nuevas_relaciones = [
                        tbl_CCPP_Unidad(ccpp=ccpp, unidad=unidad)
                        for unidad in unidades_existentes
                    ]

                    # Crear cronogramas para cada unidad y cada año
                    nuevos_cronogramas = []
                    for unidad in unidades_existentes:
                        for numero_anio in range(ccpp.cantidad_anios + 1):
                            nuevos_cronogramas.append(
                                tbl_Cronograma(
                                    id_ccpp=ccpp,
                                    id_unidad=unidad,
                                    anios=numero_anio
                                )
                            )

                    if nuevas_relaciones:
                        tbl_CCPP_Unidad.objects.bulk_create(
                            nuevas_relaciones,
                            batch_size=1000
                        )

                    if nuevos_cronogramas:
                        tbl_Cronograma.objects.bulk_create(
                            nuevos_cronogramas,
                            batch_size=1000
                        )

                    logger.info(
                        "CCPP %s: agregadas %s relaciones y %s cronogramas.",
                        id_ccpp, len(nuevas_relaciones), len(nuevos_cronogramas)
                    )

            messages.success(
                request,
                f"Las unidades fueron actualizadas correctamente para {ccpp.nombre}."
            )
            return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo=modo_valido)

        except DatabaseError as db_err:
            logger.exception("Error de base de datos en CCPP %s: %s", id_ccpp, db_err)
            messages.error(
                request,
                "Ocurrió un error de base de datos al procesar la solicitud. "
                "No se aplicaron cambios."
            )
        except Exception as err:
            logger.exception("Error al gestionar unidades de la CCPP %s: %s", id_ccpp, err)
            messages.error(
                request,
                "Ocurrió un error inesperado al procesar la solicitud. "
                "No se aplicaron cambios."
            )

    # ===============================
    # 🔹 Consultas para render (modo visual)
    # ===============================
    # Evitar N+1 y reducir consultas: ordenar y usar valores distintos
    todas_las_unidades = tbl_Unidad.objects.all().order_by("orden")
    ids_unidades_asignadas = list(
        tbl_CCPP_Unidad.objects
        .filter(ccpp=ccpp)
        .values_list("unidad_id", flat=True)
    )

    total_unidades = todas_las_unidades.count()
    total_unidades_asignadas = len(ids_unidades_asignadas)

    # Valores para filtros (distinct + order_by)
    valores_unidad = (
        tbl_Unidad.objects.values_list("unidad", flat=True)
        .distinct().order_by("unidad")
    )
    valores_capitulo = (
        tbl_Unidad.objects.values_list("capitulo", flat=True)
        .distinct().order_by("capitulo")
    )
    valores_observacion = (
        tbl_Unidad.objects.values_list("observacion", flat=True)
        .distinct().order_by("observacion")
    )
    valores_doc = (
        tbl_Unidad.objects.values_list("doc", flat=True)
        .distinct().order_by("doc")
    )

    contexto = {
        "ccpp": ccpp,
        "unidades": todas_las_unidades,
        "ids_unidades_asignadas": ids_unidades_asignadas,
        "valores_unidad": valores_unidad,
        "valores_capitulo": valores_capitulo,
        "valores_observacion": valores_observacion,
        "valores_doc": valores_doc,
        "modo_inicial": modo_valido,
        "total_unidades": total_unidades,
        "total_unidades_asignadas": total_unidades_asignadas,
    }

    return render(request, "dataMaestra/unidad/panel_unidad.html", contexto)





from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.db import transaction, DatabaseError
from django.contrib import messages

@require_POST
def editar_capitulo(request, id_ccpp):
    # Normalizar entradas (eliminar espacios)
    capitulo_original = request.POST.get("capitulo_original", "").strip()
    nuevo_capitulo = request.POST.get("nuevo_capitulo", "").strip()

    # Validaciones básicas
    if not capitulo_original or not nuevo_capitulo:
        messages.error(request, "Debe indicar capítulo original y nuevo capítulo.")
        return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo="gestion")

    if capitulo_original == nuevo_capitulo:
        messages.warning(request, "El nuevo capítulo no puede ser igual al original.")
        return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo="gestion")

    try:
        with transaction.atomic():  # Garantiza que sea todo o nada
            # Verificar existencia previa
            existe = tbl_Unidad.objects.filter(capitulo=capitulo_original).exists()
            if not existe:
                messages.error(request, f"No se encontró el capítulo '{capitulo_original}'.")
                return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo="gestion")

            # Actualizar en bloque
            filas_afectadas = tbl_Unidad.objects.filter(
                capitulo=capitulo_original
            ).update(capitulo=nuevo_capitulo)

            if filas_afectadas > 0:
                messages.success(
                    request,
                    f"Capítulo '{capitulo_original}' actualizado correctamente a '{nuevo_capitulo}'."
                )
            else:
                messages.warning(
                    request,
                    "No se realizaron cambios en los capítulos."
                )

    except DatabaseError as e:
        # Error controlado de base de datos
        messages.error(request, f"Error al actualizar capítulo: {str(e)}")

    return redirect("gestionUnidades_ccpp_modo", id_ccpp=id_ccpp, modo="gestion")
