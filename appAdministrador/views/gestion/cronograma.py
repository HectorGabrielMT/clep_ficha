# views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import JsonResponse
import json
from datetime import date
import logging

logger = logging.getLogger(__name__)

from appAdministrador.models import (
    tbl_CCPP, tbl_Cronograma, tbl_Notificacion,
    tbl_inspeccion, tbl_CCPP_Unidad, tbl_FichaControl
)
from appAdministrador.views.gestion import pago

@login_required
def vista_panel_principal(request):
    """
    Recupera solo las CCPP habilitadas de la base de datos y las pasa a la plantilla.
    """
    ccpp_listado = tbl_CCPP.objects.filter(habilitada=True)

    contexto = {
        'ccpp_listado': ccpp_listado,
    }
    return render(request, 'gestion/panel_principal.html', contexto)





###################################################################################################################################################################


















###################################################################################################################################################################


from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction




from django.db.models import Q, Count



from django.db.models import Count, Q

def contar_notificaciones_respuestas(ccpp_id, unidad_ids=None):
    """
    Devuelve un diccionario con el conteo agrupado por unidad y año relativo.
    Clave: (id_unidad, anio_relativo)
    """
    filtros = Q(id_ccpp_id=ccpp_id)

    if unidad_ids:
        filtros &= Q(id_unidad_id__in=unidad_ids)

    # Agrupamos directamente por los campos de la tabla
    notificaciones = (
        tbl_Notificacion.objects
        .filter(filtros)
        .values('id_unidad_id', 'anio') # 'anio' ya es 0, 1, 2... en la BD
        .annotate(
            total_noti=Count('id_notificacion'),
            total_resp=Count(
                'id_notificacion',
                filter=Q(NotificacionContestada=True)
            )
        )
    )

    resultado = {}

    for n in notificaciones:
        # Si en la BD se guarda 0 para el primer año, 1 para el segundo, etc.
        # NO restes 1, usa el valor directo.
        anio_relativo = n['anio']

        resultado[(n['id_unidad_id'], anio_relativo)] = {
            'total_noti': n['total_noti'],
            'total_resp': n['total_resp'],
        }

    return resultado





import logging
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseServerError
from django.db.models import Count, Q
from datetime import date

# Configuración del Logger
logger = logging.getLogger(__name__)

@login_required
def cronograma_ccpp__(request, id_ccpp):
    """
    Vista para generar el cronograma de un CCPP.
    Optimizada para velocidad y control de errores con logging.
    """
    try:
        # ===============================
        # 🔹 OBTENER CCPP
        # ===============================
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=id_ccpp)
        hoy = date.today()

        # Validación preventiva de datos maestros
        if not ccpp.fecha_entrega or ccpp.cantidad_anios is None:
            logger.warning(f"CCPP {id_ccpp} tiene datos incompletos (fecha_entrega o cantidad_anios).")
            anio_base = hoy.year
        else:
            anio_base = ccpp.fecha_entrega.year

        # ===============================
        # 🔹 DETERMINAR MODO DE VISUALIZACIÓN
        # ===============================
        modo = request.GET.get("modo", "anual")
        anios_a_cargar = []
        mostrar_columna_anio = (modo == "global")

        try:
            if modo == "global":
                anios_a_cargar = list(range(ccpp.cantidad_anios + 1))
            else:
                anio_param = request.GET.get("anio")
                if anio_param:
                    anios_a_cargar = [int(anio_param)]
                elif anio_base <= hoy.year <= anio_base + ccpp.cantidad_anios:
                    anios_a_cargar = [hoy.year - anio_base]
                else:
                    anios_a_cargar = [0]
        except (ValueError, TypeError) as e:
            logger.error(f"Error procesando parámetros de año en CCPP {id_ccpp}: {e}")
            anios_a_cargar = [0]

        # ===============================
        # 🔹 LISTA DE MESES
        # ===============================
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        meses_map = {mes: i + 1 for i, mes in enumerate(meses)}

        # ===============================
        # 🔹 CONSULTAS PRINCIPALES
        # ===============================
        inspecciones = tbl_inspeccion.objects.all().order_by("codigo_inspeccion")

        unidades = (
            tbl_CCPP_Unidad.objects
            .filter(ccpp=ccpp)
            .select_related("unidad")
            .order_by("unidad__orden")
        )

        # Generación de lista de años para el selector
        lista_anios = []
        if ccpp.cantidad_anios is not None:
            for i in range(ccpp.cantidad_anios + 1):
                lista_anios.append({
                    "indice": i,
                    "label": f"Año {i} ({anio_base + i})",
                    "anio_calendario": anio_base + i,
                })

        # Cronogramas indexados por (unidad_id, anio_relativo)
        cronogramas = tbl_Cronograma.objects.filter(
            id_ccpp=ccpp,
            anios__in=anios_a_cargar
        )
        cronograma_dict = {(c.id_unidad_id, c.anios): c for c in cronogramas}

        # ===============================
        # 🔹 NOTIFICACIONES
        # ===============================
        notificaciones_dict = {}
        unidad_ids = [u.unidad.id_unidad for u in unidades]

        notificaciones = (
            tbl_Notificacion.objects
            .filter(
                id_ccpp_id=ccpp.id_ccpp,
                id_unidad_id__in=unidad_ids,
                anio__in=anios_a_cargar
            )
            .values("id_unidad_id", "anio")
            .annotate(
                total_noti=Count("id_notificacion"),
                total_resp=Count("id_notificacion", filter=Q(NotificacionContestada=True))
            )
        )

        for n in notificaciones:
            notificaciones_dict[(n["id_unidad_id"], n["anio"])] = {
                "total_noti": n["total_noti"],
                "total_resp": n["total_resp"],
            }


        # ===============================
        # 🔹 INSPECCIONES OBLIGATORIAS SEGÚN FICHA ASIGNADA EN NOTIFICACIÓN
        # ===============================
        notif_ficha_map = {}
        ficha_ids = set()

        notificaciones_con_ficha = (
            tbl_Notificacion.objects
            .filter(
                id_ccpp_id=ccpp.id_ccpp,
                id_unidad_id__in=unidad_ids,
                anio__in=anios_a_cargar,
                id_ficha_control__isnull=False,
            )
            .values("id_unidad_id", "anio", "mes", "id_ficha_control__id_ficha_id")
        )

        for n in notificaciones_con_ficha:
            mes_normalizado = (n["mes"] or "").strip().lower()
            clave = (n["id_unidad_id"], n["anio"], mes_normalizado)
            id_ficha_de_control = n["id_ficha_control__id_ficha_id"]
            notif_ficha_map.setdefault(clave, set()).add(id_ficha_de_control)
            ficha_ids.add(id_ficha_de_control)

        ficha_obligatorias_map = {}
        if ficha_ids:
            controles_obligatorios = (
                tbl_FichaControl.objects
                .filter(
                    id_ficha_id__in=ficha_ids,
                    premisa__icontains="obligatorio",
                    id_inspeccion__isnull=False,
                )
                .values("id_ficha_id", "id_inspeccion_id")
                .distinct()
            )
            for c in controles_obligatorios:
                ficha_obligatorias_map.setdefault(
                    c["id_ficha_id"], set()
                ).add(str(c["id_inspeccion_id"]))


        # ===============================
        # 🔹 ARMADO DE TABLA
        # ===============================
        tabla_cronograma = []
        for rel in unidades:
            total_anios = len(anios_a_cargar)
            for idx, anio_indice in enumerate(anios_a_cargar):
                anio_calendario = anio_base + anio_indice
                cronograma = cronograma_dict.get((rel.unidad.id_unidad, anio_indice))
                conteo = notificaciones_dict.get(
                    (rel.unidad.id_unidad, anio_indice),
                    {"total_noti": 0, "total_resp": 0}
                )

                meses_info = []
                for mes in meses:
                    try:
                        valor_mes = getattr(cronograma, mes, "") if cronograma else ""
                    except AttributeError:
                        logger.error(f"El modelo tbl_Cronograma no tiene el campo: {mes}")
                        valor_mes = ""

                    meses_info.append({
                        "mes": mes,
                        "valor": valor_mes,
                        "is_past": (
                            anio_calendario < hoy.year or
                            (anio_calendario == hoy.year and meses_map[mes] < hoy.month)
                        ),
                    })

                tabla_cronograma.append({
                    "unidad": rel.unidad,
                    "mostrar_unidad": idx == 0,
                    "rowspan_unidad": total_anios,
                    "anio": f"{anio_indice} - {anio_calendario}",
                    "anio_relativo": anio_indice,
                    "cronograma": cronograma,
                    "meses_info": meses_info,
                    "total_noti": conteo["total_noti"],
                    "total_resp": conteo["total_resp"],
                    "nota": cronograma.nota if cronograma else "",
                })

        # ===============================
        # 🔹 DATA ADICIONAL
        # ===============================
        periodo_ccpp = f"{anio_base} - {anio_base + ccpp.cantidad_anios}" if ccpp.cantidad_anios else "N/A"
        anos_disponibles = [str(anio_base + i) for i in range((ccpp.cantidad_anios or 0) + 1)]

        return render(request, "gestion/cronograma/cronograma.html", {
            "ccpp": ccpp,
            "periodo_ccpp": periodo_ccpp,
            "tabla_cronograma": tabla_cronograma,
            "lista_meses": meses,
            "inspecciones": inspecciones,
            "lista_anios": lista_anios,
            "mostrar_columna_anio": mostrar_columna_anio,
            "modo_actual": modo,
            "total_unidades": unidades.count(),
            "anos_disponibles": anos_disponibles,
            "anio_seleccionado": anios_a_cargar[0] if (modo == "anual" and anios_a_cargar) else None,
        })

    except Exception as e:
        # Captura cualquier error no controlado y lo registra con el traceback completo
        logger.critical(f"Error 500 fatal en cronograma_ccpp para ID {id_ccpp}: {str(e)}", exc_info=True)
        return HttpResponseServerError(f"Error interno del servidor al procesar el CCPP {id_ccpp}. Revise los logs.")


@login_required
def cronograma_ccpp(request, id_ccpp):
    """
    Vista para generar el cronograma de un CCPP.
    Optimizada para velocidad y control de errores con logging.
    """
    try:
        # ===============================
        # 🔹 OBTENER CCPP
        # ===============================
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=id_ccpp)
        hoy = date.today()

        # Validación preventiva de datos maestros
        if not ccpp.fecha_entrega or ccpp.cantidad_anios is None:
            logger.warning(f"CCPP {id_ccpp} tiene datos incompletos (fecha_entrega o cantidad_anios).")
            anio_base = hoy.year
        else:
            anio_base = ccpp.fecha_entrega.year

        # ===============================
        # 🔹 DETERMINAR MODO DE VISUALIZACIÓN
        # ===============================
        modo = request.GET.get("modo", "anual")
        anios_a_cargar = []
        mostrar_columna_anio = (modo == "global")

        try:
            if modo == "global":
                anios_a_cargar = list(range(ccpp.cantidad_anios + 1))
            else:
                anio_param = request.GET.get("anio")
                if anio_param:
                    anios_a_cargar = [int(anio_param)]
                elif anio_base <= hoy.year <= anio_base + ccpp.cantidad_anios:
                    anios_a_cargar = [hoy.year - anio_base]
                else:
                    anios_a_cargar = [0]
        except (ValueError, TypeError) as e:
            logger.error(f"Error procesando parámetros de año en CCPP {id_ccpp}: {e}")
            anios_a_cargar = [0]

        # ===============================
        # 🔹 LISTA DE MESES
        # ===============================
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        meses_map = {mes: i + 1 for i, mes in enumerate(meses)}

        # ===============================
        # 🔹 CONSULTAS PRINCIPALES
        # ===============================
        inspecciones = tbl_inspeccion.objects.all().order_by("codigo_inspeccion")

        unidades = (
            tbl_CCPP_Unidad.objects
            .filter(ccpp=ccpp)
            .select_related("unidad")
            .order_by("unidad__orden")
        )

        # Generación de lista de años para el selector
        lista_anios = []
        if ccpp.cantidad_anios is not None:
            for i in range(ccpp.cantidad_anios + 1):
                lista_anios.append({
                    "indice": i,
                    "label": f"Año {i} ({anio_base + i})",
                    "anio_calendario": anio_base + i,
                })

        # Cronogramas indexados por (unidad_id, anio_relativo)
        cronogramas = tbl_Cronograma.objects.filter(
            id_ccpp=ccpp,
            anios__in=anios_a_cargar
        )
        cronograma_dict = {(c.id_unidad_id, c.anios): c for c in cronogramas}

        # ===============================
        # 🔹 NOTIFICACIONES
        # ===============================
        notificaciones_dict = {}
        unidad_ids = [u.unidad.id_unidad for u in unidades]

        notificaciones = (
            tbl_Notificacion.objects
            .filter(
                id_ccpp_id=ccpp.id_ccpp,
                id_unidad_id__in=unidad_ids,
                anio__in=anios_a_cargar
            )
            .values("id_unidad_id", "anio")
            .annotate(
                total_noti=Count("id_notificacion"),
                total_resp=Count("id_notificacion", filter=Q(NotificacionContestada=True))
            )
        )

        for n in notificaciones:
            notificaciones_dict[(n["id_unidad_id"], n["anio"])] = {
                "total_noti": n["total_noti"],
                "total_resp": n["total_resp"],
            }

        # ===============================
        # 🔹 INSPECCIONES OBLIGATORIAS SEGÚN FICHA ASIGNADA EN NOTIFICACIÓN
        # ===============================
        notif_ficha_map = {}
        ficha_ids = set()

        notificaciones_con_ficha = (
            tbl_Notificacion.objects
            .filter(
                id_ccpp_id=ccpp.id_ccpp,
                id_unidad_id__in=unidad_ids,
                anio__in=anios_a_cargar,
                id_ficha_control__isnull=False,
            )
            .values("id_unidad_id", "anio", "mes", "id_ficha_control__id_ficha_id")
        )

        for n in notificaciones_con_ficha:
            mes_normalizado = (n["mes"] or "").strip().lower()
            clave = (n["id_unidad_id"], n["anio"], mes_normalizado)
            id_ficha_de_control = n["id_ficha_control__id_ficha_id"]
            notif_ficha_map.setdefault(clave, set()).add(id_ficha_de_control)
            ficha_ids.add(id_ficha_de_control)

        ficha_obligatorias_map = {}
        if ficha_ids:
            controles_obligatorios = (
                tbl_FichaControl.objects
                .filter(
                    id_ficha_id__in=ficha_ids,
                    premisa__icontains="obligatorio",
                    id_inspeccion__isnull=False,
                )
                .values("id_ficha_id", "id_inspeccion_id")
                .distinct()
            )
            for c in controles_obligatorios:
                ficha_obligatorias_map.setdefault(
                    c["id_ficha_id"], set()
                ).add(str(c["id_inspeccion_id"]))

        # ===============================
        # 🔹 ARMADO DE TABLA
        # ===============================
        tabla_cronograma = []
        for rel in unidades:
            total_anios = len(anios_a_cargar)
            for idx, anio_indice in enumerate(anios_a_cargar):
                anio_calendario = anio_base + anio_indice
                cronograma = cronograma_dict.get((rel.unidad.id_unidad, anio_indice))
                conteo = notificaciones_dict.get(
                    (rel.unidad.id_unidad, anio_indice),
                    {"total_noti": 0, "total_resp": 0}
                )

                meses_info = []
                for mes in meses:
                    try:
                        valor_mes = getattr(cronograma, mes, "") if cronograma else ""
                    except AttributeError:
                        logger.error(f"El modelo tbl_Cronograma no tiene el campo: {mes}")
                        valor_mes = ""

                    # Inspecciones que, para esta celda específica, se consideran
                    # "relevantes" según la ficha asignada en la notificación.
                    # Se calcula el conjunto completo (no solo si matchea el valor actual)
                    # para que el frontend pueda decidir dinámicamente al agregar/quitar.
                    fichas_de_celda = notif_ficha_map.get(
                        (rel.unidad.id_unidad, anio_indice, mes), set()
                    )
                    inspecciones_relevantes_celda = set()
                    for fid in fichas_de_celda:
                        inspecciones_relevantes_celda |= ficha_obligatorias_map.get(fid, set())

                    es_relevante = bool(valor_mes) and str(valor_mes) in inspecciones_relevantes_celda

                    meses_info.append({
                        "mes": mes,
                        "valor": valor_mes,
                        "es_relevante": es_relevante,
                        "inspecciones_relevantes": sorted(inspecciones_relevantes_celda),
                        "is_past": (
                            anio_calendario < hoy.year or
                            (anio_calendario == hoy.year and meses_map[mes] < hoy.month)
                        ),
                    })





                tabla_cronograma.append({
                    "unidad": rel.unidad,
                    "mostrar_unidad": idx == 0,
                    "rowspan_unidad": total_anios,
                    "anio": f"{anio_indice} - {anio_calendario}",
                    "anio_relativo": anio_indice,
                    "cronograma": cronograma,
                    "meses_info": meses_info,
                    "total_noti": conteo["total_noti"],
                    "total_resp": conteo["total_resp"],
                    "nota": cronograma.nota if cronograma else "",
                })

        # ===============================
        # 🔹 DATA ADICIONAL
        # ===============================
        periodo_ccpp = f"{anio_base} - {anio_base + ccpp.cantidad_anios}" if ccpp.cantidad_anios else "N/A"
        anos_disponibles = [str(anio_base + i) for i in range((ccpp.cantidad_anios or 0) + 1)]

        return render(request, "gestion/cronograma/cronograma.html", {
            "ccpp": ccpp,
            "periodo_ccpp": periodo_ccpp,
            "tabla_cronograma": tabla_cronograma,
            "lista_meses": meses,
            "inspecciones": inspecciones,
            "lista_anios": lista_anios,
            "mostrar_columna_anio": mostrar_columna_anio,
            "modo_actual": modo,
            "total_unidades": unidades.count(),
            "anos_disponibles": anos_disponibles,
            "anio_seleccionado": anios_a_cargar[0] if (modo == "anual" and anios_a_cargar) else None,
        })

    except Exception as e:
        # Captura cualquier error no controlado y lo registra con el traceback completo
        logger.critical(f"Error 500 fatal en cronograma_ccpp para ID {id_ccpp}: {str(e)}", exc_info=True)
        return HttpResponseServerError(f"Error interno del servidor al procesar el CCPP {id_ccpp}. Revise los logs.")







@csrf_exempt
@require_POST
@login_required
def guardar_celda_cronograma(request, id_ccpp):
    try:
        id_unidad = request.POST.get('id_unidad')
        anio = request.POST.get('anio')
        campo = request.POST.get('campo')
        valor = request.POST.get('valor', '')

        if not all([id_ccpp, id_unidad, anio, campo]):
            return JsonResponse(
                {'ok': False, 'error': 'Datos incompletos'},
                status=400
            )

        with transaction.atomic():
            cronograma, _ = tbl_Cronograma.objects.get_or_create(
                id_ccpp_id=id_ccpp,
                id_unidad_id=id_unidad,
                anios=int(anio)
            )

            if not hasattr(cronograma, campo):
                return JsonResponse(
                    {'ok': False, 'error': f'Campo inválido: {campo}'},
                    status=400
                )

            setattr(cronograma, campo, valor or None)
            cronograma.save(update_fields=[campo])

        return JsonResponse({'ok': True})

    except Exception as e:
        return JsonResponse(
            {'ok': False, 'error': str(e)},
            status=500
        )


































