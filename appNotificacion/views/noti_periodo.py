"""
Vistas de appNotificacion.

Modelos en appAdministrador. Tareas asíncronas en appNotificacion.tareas.

Estructura del archivo (en este orden):
    1. Imports y constantes
    2. Funciones auxiliares generales
    3. Funciones auxiliares privadas — envío programado de correo
    4. Construcción de contexto — notificaciones
    5. Vistas principales — gestión de notificaciones (CRUD)
    6. Vistas — correo manual (modal "redactar correo")
    7. Generación de ficha PDF (NO MODIFICAR)
"""

import io
import os
import re
import uuid
import logging
import base64
import pytz
import zoneinfo

from datetime import datetime, timedelta
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.contrib.staticfiles import finders
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import urllib

from appAdministrador.models import (
    tbl_CCPP, tbl_Correo, tbl_Cronograma, tbl_Ficha, tbl_FichaControl,
    tbl_inspeccion, tbl_Notificacion, tbl_NotificacionDocumento,
    tbl_Unidad, ConfiguracionEmail,tbl_CCPP_Unidad
)
from appAdministrador.views.moduloGlobal import validar_permisos

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, KeepTogether, LongTable, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)

# Zona horaria única para todo el módulo — fuente de verdad en settings.py
ZONA_HORARIA = pytz.timezone(getattr(settings, 'ZONA_HORARIA_DEFECTO', 'UTC'))

# Meses válidos del cronograma (nombres de campo en tbl_Cronograma)
MESES_VALIDOS = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

# Constantes de layout PDF
ALTURA_PAGINA_UTIL_MM = (letter[1] / mm) - 35 - 15
ALTURA_MAX_FILA_MM = ALTURA_PAGINA_UTIL_MM * 0.82


# ═════════════════════════════════════════════════════════════════════════
# 2. FUNCIONES AUXILIARES GENERALES
# ═════════════════════════════════════════════════════════════════════════


def _resolver_adjunto_ficha(ccpp_id, unidad_id, notificacion=None):
    """
    Determina qué debe adjuntarse como PDF de ficha para una unidad-ccpp:

    - Si la notificación tiene un control asignado -> (ficha_id, control_id)
      del control, para generar el PDF con SOLO ese control.
    - Si no tiene control pero la unidad tiene ficha asignada -> (ficha_id, None),
      para generar el PDF con la ficha completa.
    - Si la unidad no tiene ficha asignada -> (None, None), no se adjunta nada.
    """
    if notificacion and notificacion.id_ficha_control_id:
        control = notificacion.id_ficha_control
        return control.id_ficha_id, control.pk

    relacion = tbl_CCPP_Unidad.objects.filter(
        ccpp_id=ccpp_id, unidad_id=unidad_id,
    ).select_related('ficha').first()

    if relacion and relacion.ficha_id:
        return relacion.ficha_id, None

    return None, None



def calcular_anio_real(fecha_entrega, anio_relativo):
    """Convierte un año relativo (0, 1, 2...) al año calendario real."""
    if not fecha_entrega or anio_relativo is None:
        return None
    return fecha_entrega.year + anio_relativo


def calcular_anio_relativo(fecha_entrega, anio_real):
    """Convierte un año calendario real a su equivalente relativo."""
    if not fecha_entrega or anio_real is None:
        return None
    return anio_real - fecha_entrega.year


def obtener_anios_disponibles(ccpp):
    """Devuelve la lista de años (relativo/etiqueta) disponibles para un CCPP."""
    if not ccpp or not ccpp.fecha_entrega:
        return []
    return [
        {
            'valor': i,
            'etiqueta': calcular_anio_real(ccpp.fecha_entrega, i),
        }
        for i in range(ccpp.cantidad_anios + 1)
    ]


def extraer_correos(texto: str) -> list:
    """Extrae correos únicos de un bloque de texto, preservando el orden."""
    if not texto:
        return []
    patron = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    vistos = set()
    resultado = []
    for correo in re.findall(patron, texto):
        clave = correo.lower()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(correo)
    return resultado


def reemplazar_etiquetas(texto: str, contexto: dict) -> str:
    """Reemplaza etiquetas especiales en el cuerpo o asunto de un correo."""
    if not texto:
        return ''
    hoy = datetime.now()
    reemplazos = {
        '<FECHA>': hoy.strftime('%d/%m/%Y'),
        '<AÑO>': str(hoy.year),
        '<CCPP-I>': contexto.get('id_ccpp', ''),
        '<CCPP-N>': contexto.get('nombre_ccpp', ''),
        '<UNIDAD>': contexto.get('unidad', ''),
        '<UNIDAD-D>': contexto.get('descripcion_unidad', ''),
        '<INSPECCION>': contexto.get('inspeccion', ''),
        '<INSPECCION-D>': contexto.get('descripcion_inspeccion', ''),
        '<INSPECCION-N>': contexto.get('notificacion_inspeccion', ''),
    }
    for etiqueta, valor in reemplazos.items():
        texto = texto.replace(etiqueta, str(valor))
    return texto


# ═════════════════════════════════════════════════════════════════════════
# 3. FUNCIONES AUXILIARES PRIVADAS — ENVÍO PROGRAMADO
# ═════════════════════════════════════════════════════════════════════════

def _cancelar_tarea_programada(notificacion: tbl_Notificacion) -> None:
    """Elimina la tarea de django-q2 asociada si existe y limpia los campos."""
    if notificacion.envio_ejecutado:
        # El correo ya se envió: no hay tarea que cancelar y no se debe
        # tocar su estado (evitaría marcarla incorrectamente como pendiente).
        return

    if notificacion.tarea_q_id:
        try:
            from django_q.models import Schedule
            Schedule.objects.filter(pk=notificacion.tarea_q_id).delete()
        except Exception as exc:
            logger.warning(
                "No se pudo eliminar tarea_q_id=%s: %s",
                notificacion.tarea_q_id, exc
            )

    tbl_Notificacion.objects.filter(
        id_notificacion=notificacion.id_notificacion
    ).update(
        fecha_envio_programado=None,
        tarea_q_id=None,
        envio_ejecutado=False,
    )






def _programar_envio(request, notificacion: tbl_Notificacion, fecha_envio_str: str):
    """
    Crea o reemplaza la tarea programada en django-q2.
    La zona horaria llega desde el formulario (nombre IANA, ej. "Europe/Madrid"),
    capturada en el navegador de quien programa. zoneinfo resuelve el
    horario de verano correctamente para la fecha específica que se programa
    (a diferencia de un offset fijo en minutos).
    """
    zona_nombre = (
        request.POST.get('zona_horaria')
        or urllib.parse.unquote(request.COOKIES.get('django_timezone', ''))
        or getattr(settings, 'ZONA_HORARIA_DEFECTO', 'UTC')
    )
    try:
        zona_usuario = zoneinfo.ZoneInfo(zona_nombre)
    except Exception:
        logger.warning(
            "Zona horaria inválida al programar envío notificacion_id=%s: %r",
            notificacion.id_notificacion, zona_nombre
        )
        return 'zona horaria inválida'

    try:
        dt_naive = datetime.strptime(fecha_envio_str, '%Y-%m-%dT%H:%M')
    except (TypeError, ValueError):
        logger.warning(
            "Fecha de envío programado inválida notificacion_id=%s valor=%r",
            notificacion.id_notificacion, fecha_envio_str
        )
        return 'fecha inválida'

    dt_local = dt_naive.replace(tzinfo=zona_usuario)
    dt_utc = dt_local.astimezone(pytz.utc)

    if dt_utc <= pytz.utc.localize(datetime.utcnow()):
        return 'la fecha y hora ya pasaron'

    try:
        from django_q.tasks import schedule
        from django_q.models import Schedule

        _cancelar_tarea_programada(notificacion)

        nombre_tarea = f'correo_{notificacion.id_notificacion}_{uuid.uuid4().hex[:8]}'

        tarea = schedule(
            'appNotificacion.tareas.enviar_correo_notificacion',
            notificacion.id_notificacion,
            schedule_type=Schedule.ONCE,
            next_run=dt_utc,
            name=nombre_tarea,
        )

        tbl_Notificacion.objects.filter(
            id_notificacion=notificacion.id_notificacion
        ).update(
            fecha_envio_programado=dt_utc,
            tarea_q_id=str(tarea.id),
            envio_ejecutado=False,
        )
        return None

    except Exception as exc:
        logger.error(
            "Error al programar envío notificacion_id=%s: %s",
            notificacion.id_notificacion, exc
        )
        return f'error interno ({exc})'






# ═════════════════════════════════════════════════════════════════════════
# 4. CONSTRUCCIÓN DE CONTEXTO — NOTIFICACIONES
# ═════════════════════════════════════════════════════════════════════════

def _cargar_contexto_notificaciones(
    request, ccpp_id,
    anio_relativo=None, mes=None, key_seleccionada=None,
):
    """
    Carga el contexto completo para la vista de notificaciones.
    Reutilizable desde gestion_notificaciones y gestion_notificaciones_auto.
    """
    try:
        ccpp = tbl_CCPP.objects.get(id_ccpp=ccpp_id, habilitada=True)
    except tbl_CCPP.DoesNotExist:
        messages.error(request, 'CCPP no encontrada o no habilitada.')
        return None

    context = {
        'ccpp': ccpp,
        'meses': MESES_VALIDOS,
        'anios_disponibles': obtener_anios_disponibles(ccpp),
        'inspecciones': [],
        'anio_seleccionado': str(anio_relativo) if anio_relativo is not None else None,
        'mes_seleccionado': mes,
        'detalle_inspeccion': None,
        'notificacion': None,
        'documentos': [],
        'correos_para': [],
        'correos_cc': [],
        'correos_cco': [],
        'inspeccion_seleccionada': None,
        'ficha_asignada': None, 'controles_disponibles': [],
    }

    if anio_relativo is None or not mes:
        return context

    if mes not in MESES_VALIDOS:
        messages.error(request, 'Mes no válido.')
        return context

    try:
        anio_relativo = int(anio_relativo)
    except (TypeError, ValueError):
        messages.error(request, 'El año seleccionado no es válido.')
        return context

    cronogramas = tbl_Cronograma.objects.filter(
        id_ccpp_id=ccpp_id,
        anios=anio_relativo,
    ).select_related('id_unidad')

    inspecciones_lista = []

    for cronograma in cronogramas:
        codigo_raw = getattr(cronograma, mes, None)
        if not codigo_raw:
            continue

        codigo = str(codigo_raw).strip()
        if not codigo:
            continue

        inspeccion = tbl_inspeccion.objects.filter(id=codigo).first()

        notificacion_obj = tbl_Notificacion.objects.filter(
            id_ccpp_id=ccpp_id,
            id_unidad_id=cronograma.id_unidad_id,
            anio=anio_relativo,
            mes=mes,
        ).first()

        notificacion_existe = bool(notificacion_obj)
        correo_enviado = bool(notificacion_obj and notificacion_obj.envio_ejecutado)
        tiene_respuesta = bool(
            notificacion_obj and (
                notificacion_obj.FechaResp
                or notificacion_obj.RespRevision
                or notificacion_obj.RespControlador
                or notificacion_obj.RespVia
                or notificacion_obj.RespObservacion
            )
        )

        key = f"{ccpp_id}_{cronograma.id_unidad_id}_{anio_relativo}_{mes}"

        if inspeccion:
            inspecciones_lista.append({
                'key': key,
                'id_unidad': cronograma.id_unidad_id,
                'inspeccion_id': inspeccion.id,
                'unidad': cronograma.id_unidad.unidad,
                'capitulo': cronograma.id_unidad.capitulo,
                'doc': cronograma.id_unidad.doc or '',
                'codigo_inspeccion': inspeccion.codigo_inspeccion,
                'nombre_inspeccion': inspeccion.nombre_inspeccion,
                'notificacionA_inspeccion': inspeccion.notificacionA_inspeccion,
                'color_inspeccion': inspeccion.color_inspeccion,
                'nota_cronograma': cronograma.nota or '',
                'observacion_unidad': cronograma.id_unidad.observacion,
                'notificada': notificacion_existe,
                'envio_ejecutado': correo_enviado,     # <-- ¡Asegúrate de incluir esta clave!
                'notificacion_enviada': correo_enviado, 
                'notificacion_respuesta': tiene_respuesta,
            })
        else:
            inspecciones_lista.append({
                'key': key,
                'id_unidad': cronograma.id_unidad_id,
                'unidad': cronograma.id_unidad.unidad,
                'capitulo': cronograma.id_unidad.capitulo,
                'doc': cronograma.id_unidad.doc or '',
                'codigo_inspeccion': codigo,
                'nombre_inspeccion': f"Inspección: {codigo} (no encontrada)",
                'color_inspeccion': '#9CA3AF',
                'nota_cronograma': cronograma.nota or '',
                'observacion_unidad': cronograma.id_unidad.observacion,
                'notificada': notificacion_existe,
            })

    context['inspecciones'] = inspecciones_lista

    if not key_seleccionada:
        return context

    context['inspeccion_seleccionada'] = key_seleccionada

    detalle = next(
        (i for i in inspecciones_lista if i['key'] == key_seleccionada),
        None
    )

    if not detalle:
        return context

    context['detalle_inspeccion'] = detalle

    notificacion = tbl_Notificacion.objects.filter(
        id_ccpp_id=ccpp_id,
        id_unidad_id=detalle['id_unidad'],
        anio=anio_relativo,
        mes=mes,
    ).first()

    if notificacion:
        context['notificacion'] = notificacion
        context['documentos'] = (
            tbl_NotificacionDocumento.objects
            .filter(id_notificacion=notificacion)
            .order_by('-fecha_subida')
        )





    relacion_ccpp_unidad = tbl_CCPP_Unidad.objects.filter(
        ccpp_id=ccpp_id, unidad_id=detalle['id_unidad'],
    ).select_related('ficha').first()

    ficha_asignada = relacion_ccpp_unidad.ficha if relacion_ccpp_unidad else None

    context['ficha_asignada'] = ficha_asignada
    context['controles_disponibles'] = (
        tbl_FichaControl.objects
        .filter(id_ficha=ficha_asignada)
        .select_related('id_inspeccion')
        .order_by('codigo_control')
        if ficha_asignada else tbl_FichaControl.objects.none()
    )




    correos_para = (
        extraer_correos(ccpp.administracion_edificio)
        + extraer_correos(ccpp.tecnico_cabecera)
    )
    correos_cc = (
        extraer_correos(ccpp.operario_comunidad)
        + extraer_correos(ccpp.tecnico_especialista)
        + extraer_correos(ccpp.empresa_especializada)
    )

    context['correos_para'] = list(set(correos_para))
    context['correos_cc'] = list(set(correos_cc))
    context['correos_cco'] = list(set(extraer_correos(ccpp.copia_oculta)))

    return context


# ═════════════════════════════════════════════════════════════════════════
# 5. VISTAS PRINCIPALES — GESTIÓN DE NOTIFICACIONES
# ═════════════════════════════════════════════════════════════════════════

def gestion_notificaciones(request, ccpp_id):
    """Vista principal para la gestión de notificaciones."""
    context = _cargar_contexto_notificaciones(
        request, ccpp_id,
        anio_relativo=request.GET.get('anio'),
        mes=request.GET.get('mes'),
        key_seleccionada=request.GET.get('key'),
    )
    if context is None:
        return redirect('/')
    context['modo_inicial'] = 'gestion'
    return render(request, 'gestion_notificaciones.html', context)


def gestion_notificaciones_auto(request, ccpp_id, anio, mes, unidad_id):
    """Redirige a gestion_notificaciones con parámetros preseleccionados."""
    mes_normalizado = (mes or '').lower()

    try:
        anio = int(anio)
        if mes_normalizado not in MESES_VALIDOS:
            messages.error(request, 'Mes no válido.')
            return redirect('gestion_notificaciones', ccpp_id=ccpp_id)

        get_object_or_404(tbl_Unidad, id_unidad=unidad_id)
        key = f"{ccpp_id}_{unidad_id}_{anio}_{mes_normalizado}"
        return redirect(
            f'/notificaciones/{ccpp_id}/?anio={anio}&mes={mes_normalizado}&key={key}'
        )
    except (TypeError, ValueError):
        messages.error(request, 'Parámetros de URL inválidos.')
        return redirect('gestion_notificaciones', ccpp_id=ccpp_id)


@login_required
@validar_permisos
def guardar_notificacion(request, ccpp_id):
    """
    Crea (si no existe) o actualiza la notificación de una inspección.
    Reemplaza a crear_notificacion + actualizar_respuesta: ya no hay botón
    separado para "crear" — el registro se crea de forma transparente
    (get_or_create) la primera vez que se guarda el formulario.
    """
    if request.method != 'POST':
        return redirect(f'/notificaciones/{ccpp_id}/')

    anio = request.POST.get('anio') or ''
    mes = request.POST.get('mes') or ''
    key = request.POST.get('key') or ''
    unidad_id = request.POST.get('unidad')

    if not unidad_id or not str(unidad_id).isdigit():
        messages.error(request, 'Unidad inválida.')
        return redirect(f'/notificaciones/{ccpp_id}/?anio={anio}&mes={mes}&key={key}')

    if mes not in MESES_VALIDOS:
        messages.error(request, 'Mes no válido.')
        return redirect(f'/notificaciones/{ccpp_id}/?anio={anio}&mes={mes}&key={key}')

    try:
        anio_relativo = int(anio)
    except (TypeError, ValueError):
        messages.error(request, 'El año seleccionado no es válido.')
        return redirect(f'/notificaciones/{ccpp_id}/?anio={anio}&mes={mes}&key={key}')

    try:
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)

        notificacion, _creada = tbl_Notificacion.objects.get_or_create(
            id_ccpp_id=ccpp_id,
            id_unidad_id=unidad_id,
            anio=anio_relativo,
            mes=mes,
            defaults={'para': '', 'cc': '', 'cco': ''},
        )

        todos_correos_para = (
            extraer_correos(ccpp.administracion_edificio)
            + extraer_correos(ccpp.tecnico_cabecera)
        )
        todos_correos_cc = (
            extraer_correos(ccpp.operario_comunidad)
            + extraer_correos(ccpp.tecnico_especialista)
            + extraer_correos(ccpp.empresa_especializada)
        )
        todos_correos_cco = extraer_correos(ccpp.copia_oculta)

        correos_para_final = [c for c in set(request.POST.getlist('para')) if c in todos_correos_para]
        correos_cc_final = [c for c in set(request.POST.getlist('cc')) if c in todos_correos_cc]
        correos_cco_final = [c for c in set(request.POST.getlist('cco')) if c in todos_correos_cco]

        notificacion.para = ', '.join(correos_para_final)
        notificacion.cc = ', '.join(correos_cc_final)
        notificacion.cco = ', '.join(correos_cco_final)

        fecha_respuesta = request.POST.get('fecha_respuesta')
        notificacion.FechaResp = fecha_respuesta or None
        notificacion.RespRevision = request.POST.get('revision_respuesta', '')
        notificacion.RespControlador = request.POST.get('controlador_respuesta', '')
        notificacion.RespVia = request.POST.get('via_respuesta', '')
        notificacion.RespObservacion = request.POST.get('observacion_respuesta', '')
        notificacion.RespInspEjecutada = request.POST.get('inspeccion_ejecutada') == 'on'

        control_id = request.POST.get('ficha_control')

        if control_id and not str(control_id).isdigit():
            messages.warning(request, 'El control seleccionado no es válido y fue ignorado.')
            control_id = None

        if control_id:
            control_valido = tbl_FichaControl.objects.filter(
                pk=control_id,
                id_ficha__ccpp_unidades__ccpp_id=ccpp_id,
                id_ficha__ccpp_unidades__unidad_id=notificacion.id_unidad_id,
            ).exists()
            if not control_valido:
                messages.warning(request, 'El control seleccionado no pertenece a esta unidad y fue ignorado.')
                control_id = None

        notificacion.id_ficha_control_id = control_id or None

        notificacion.NotificacionContestada = any([
            notificacion.FechaResp,
            notificacion.RespRevision,
            notificacion.RespControlador,
            notificacion.RespVia,
            notificacion.RespObservacion,
            notificacion.RespInspEjecutada,
        ])

        # IMPORTANTE: aquí NO se toca envio_ejecutado bajo ninguna
        # circunstancia. Guardar correos/respuesta nunca marca "notificado".
        notificacion.save()

        for archivo in request.FILES.getlist('nuevos_archivos'):
            tbl_NotificacionDocumento.objects.create(
                id_notificacion=notificacion,
                archivo=archivo,
                nombre_original=archivo.name,
                tamano=archivo.size,
            )

        fecha_envio_str = request.POST.get('fecha_envio_programado', '').strip()
        cancelar = request.POST.get('cancelar_envio_programado')

        if cancelar:
            _cancelar_tarea_programada(notificacion)
        elif fecha_envio_str:
            if not correos_para_final:
                messages.warning(
                    request,
                    'Para programar el envío automático debes seleccionar '
                    'al menos un correo en el campo "Para".'
                )
            else:
                error_programacion = _programar_envio(request, notificacion, fecha_envio_str)
                if error_programacion:
                    messages.warning(request, f'No se pudo programar el envío: {error_programacion}.')

        messages.success(request, 'Proceso exitoso')

    except Exception as exc:
        logger.error(
            "Error en guardar_notificacion ccpp_id=%s unidad_id=%s: %s",
            ccpp_id, unidad_id, exc
        )
        messages.error(request, f'Error al guardar la notificación: {exc}')

    return redirect(f'/notificaciones/{ccpp_id}/?anio={anio}&mes={mes}&key={key}')





@login_required
@validar_permisos
@require_POST
def eliminar_documento(request, documento_id):
    """Elimina un documento y su archivo físico."""
    try:
        with transaction.atomic():
            documento = get_object_or_404(tbl_NotificacionDocumento, id=documento_id)
            documento.delete()
        return JsonResponse({'success': True})
    except Exception as exc:
        logger.error("Error al eliminar documento %s: %s", documento_id, exc)
        return JsonResponse({
            'success': False,
            'error': 'Ocurrió un error al intentar eliminar el documento.',
        })


@login_required
@validar_permisos
@require_POST
def eliminar_respuesta(request, notificacion_id):
    """Limpia los campos de respuesta y elimina los documentos asociados."""
    try:
        with transaction.atomic():
            notificacion = get_object_or_404(
                tbl_Notificacion.objects.select_for_update(),
                id_notificacion=notificacion_id,
            )
            for doc in tbl_NotificacionDocumento.objects.filter(id_notificacion=notificacion):
                doc.delete()

            notificacion.FechaResp = None
            notificacion.RespRevision = ''
            notificacion.RespControlador = ''
            notificacion.RespVia = ''
            notificacion.RespObservacion = ''
            notificacion.RespInspEjecutada = False
            notificacion.NotificacionContestada = False
            notificacion.save()

        return JsonResponse({'success': True})
    except Exception as exc:
        logger.error("Error al limpiar respuesta notificacion %s: %s", notificacion_id, exc)
        return JsonResponse({
            'success': False,
            'error': 'No se pudo limpiar la respuesta de la notificación.',
        })


@login_required
@validar_permisos
@require_POST
def eliminar_notificacion(request, notificacion_id):
    """Elimina completamente una notificación y todos sus documentos."""
    try:
        with transaction.atomic():
            notificacion = get_object_or_404(tbl_Notificacion, id_notificacion=notificacion_id)
            # Evita tareas programadas huérfanas en django-q2 si la
            # notificación se elimina antes de que se ejecute su envío.
            _cancelar_tarea_programada(notificacion)
            for doc in tbl_NotificacionDocumento.objects.filter(id_notificacion=notificacion):
                doc.delete()
            notificacion.delete()
        return JsonResponse({'success': True})
    except Exception as exc:
        logger.error("Error al eliminar notificacion %s: %s", notificacion_id, exc)
        return JsonResponse({
            'success': False,
            'error': 'No se pudo eliminar la notificación.',
        })


# ═════════════════════════════════════════════════════════════════════════
# 6. VISTAS — CORREO MANUAL (formulario redactar_correo.html)
# ═════════════════════════════════════════════════════════════════════════

def abrir_formulario_correo(request):
    """Devuelve asunto, cuerpo y destinatarios para el modal de correo."""
    id_ccpp = request.GET.get('id_ccpp')
    id_unidad = request.GET.get('id_unidad')
    id_inspeccion = request.GET.get('id_inspeccion')

    try:
        plantilla = tbl_Correo.objects.first()
        if not plantilla:
            return JsonResponse({'success': False, 'error': 'No hay plantilla de correo'})

        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=id_ccpp)
        unidad = get_object_or_404(tbl_Unidad, id_unidad=id_unidad)
        insp = get_object_or_404(tbl_inspeccion, pk=id_inspeccion)

        contexto = {
            'id_ccpp': str(ccpp.id_ccpp),
            'nombre_ccpp': ccpp.nombre,
            'unidad': unidad.unidad,
            'descripcion_unidad': unidad.descripcion,
            'inspeccion': insp.nombre_inspeccion,
            'descripcion_inspeccion': insp.descripcion_inspeccion,
            'notificacion_inspeccion': insp.notificacionA_inspeccion,
        }

        # Resuelve automáticamente qué adjuntar: control específico, ficha
        # completa, o nada — según lo que tenga la unidad y su notificación.
        id_notificacion = request.GET.get('id_notificacion')
        notificacion = (
            tbl_Notificacion.objects.filter(pk=id_notificacion).first()
            if id_notificacion else None
        )
        id_ficha, id_control = _resolver_adjunto_ficha(id_ccpp, id_unidad, notificacion)

        adjunto_auto = None
        if id_ficha:
            pdf_bytes = exportar_ficha_pdf(
                request, id_ficha, id_ccpp, return_buffer=True, id_control=id_control,
            )
            if pdf_bytes:
                adjunto_auto = {
                    'nombre': f"Ficha_Control_{id_control or id_ficha}.pdf",
                    'contenido': base64.b64encode(pdf_bytes).decode('utf-8'),
                    'tipo': 'application/pdf',
                }

        return JsonResponse({
            'success': True,
            'asunto': reemplazar_etiquetas(plantilla.asunto, contexto),
            'cuerpo': reemplazar_etiquetas(plantilla.cuerpo, contexto),
            'destinatarios': {
                'para': ccpp.administracion_edificio or '',
                'cc': f"{ccpp.tecnico_cabecera or ''}, {ccpp.empresa_especializada or ''}",
                'bcc': ccpp.copia_oculta or '',
            },
            'adjunto_auto': adjunto_auto,
        })
    except Exception as exc:
        logger.error(
            "Error en abrir_formulario_correo id_ccpp=%s id_unidad=%s id_inspeccion=%s: %s",
            id_ccpp, id_unidad, id_inspeccion, exc
        )
        return JsonResponse({
            'success': False,
            'error': 'No se pudo preparar el correo. Verifica los datos e inténtalo de nuevo.',
        })



@login_required
@validar_permisos
@require_POST
def enviar_correo(request):
    """Envía un correo manualmente desde el modal y marca la notificación como enviada."""
    if request.method != 'POST':
        return JsonResponse(
            {
                'success': False,
                'error': 'Método HTTP no permitido.'
            },
            status=405
        )

    try:
        # ==============================================================
        # 1. EXTRAER Y LIMPIAR DESTINATARIOS
        # ==============================================================

        to_list = [
            correo.strip()
            for correo in (request.POST.get('to', '') or '').split(',')
            if correo.strip()
        ]

        cc_list = [
            correo.strip()
            for correo in (request.POST.get('cc', '') or '').split(',')
            if correo.strip()
        ]

        bcc_list = [
            correo.strip()
            for correo in (request.POST.get('bcc', '') or '').split(',')
            if correo.strip()
        ]

        if not to_list:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'El campo "Para" es obligatorio.'
                },
                status=400
            )

        # ==============================================================
        # 2. VALIDAR CORREOS
        # ==============================================================

        for direccion_correo in to_list + cc_list + bcc_list:
            try:
                validate_email(direccion_correo)
            except ValidationError:
                return JsonResponse(
                    {
                        'success': False,
                        'error': (
                            f'Dirección de correo inválida: '
                            f'{direccion_correo}'
                        )
                    },
                    status=400
                )

        # ==============================================================
        # 3. OBTENER CONFIGURACIÓN SMTP
        # ==============================================================

        configuracion = ConfiguracionEmail.objects.first()

        if not configuracion:
            logger.error(
                'Envío fallido: no existe configuración SMTP '
                'en la base de datos.'
            )

            return JsonResponse(
                {
                    'success': False,
                    'error': (
                        'El sistema no cuenta con configuración '
                        'SMTP activa.'
                    )
                },
                status=500
            )

        # ==============================================================
        # 4. CREAR CONEXIÓN SMTP
        # ==============================================================

        conexion = get_connection(
            host=configuracion.servidor_smtp,
            port=configuracion.puerto,
            username=configuracion.usuario_email,
            password=configuracion.password_aplicacion,
            use_tls=configuracion.usar_tls,
            fail_silently=False,
        )

        # ==============================================================
        # 5. CREAR CORREO
        # ==============================================================

        correo = EmailMessage(
            subject=request.POST.get('subject', ''),
            body=request.POST.get('body', ''),
            from_email=configuracion.usuario_email,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            connection=conexion,
        )

        # ==============================================================
        # 6. ADJUNTOS MANUALES
        # ==============================================================

        for archivo in request.FILES.getlist('attachments'):
            correo.attach(
                archivo.name,
                archivo.read(),
                archivo.content_type
            )

        # ==============================================================
        # 7. ENVIAR CORREO
        #
        # IMPORTANTE:
        # envio_ejecutado SOLO se modifica después de que
        # correo.send() termine correctamente.
        # ==============================================================

        correo.send()

        # ==============================================================
        # 8. LOCALIZAR LA NOTIFICACIÓN
        #
        # Primero se intenta utilizar notificacion_id.
        # Si no existe, se intenta localizar/crear mediante:
        # CCPP + Unidad + Año + Mes.
        # ==============================================================

        notificacion_id = request.POST.get('notificacion_id')
        id_ccpp = request.POST.get('id_ccpp')
        id_unidad = request.POST.get('id_unidad')
        anio = request.POST.get('anio')
        mes = request.POST.get('mes')

        notificacion = None

        # --------------------------------------------------------------
        # 8.1. Buscar directamente por ID de notificación
        # --------------------------------------------------------------

        if notificacion_id and str(notificacion_id).isdigit():
            notificacion = (
                tbl_Notificacion.objects
                .filter(id_notificacion=notificacion_id)
                .first()
            )

        # --------------------------------------------------------------
        # 8.2. Si no llegó el ID, buscar por CCPP + Unidad + Año + Mes
        # --------------------------------------------------------------

        if notificacion is None:
            try:
                anio_relativo = int(anio)
            except (TypeError, ValueError):
                anio_relativo = None

            if (
                id_ccpp
                and id_unidad
                and anio_relativo is not None
                and mes in MESES_VALIDOS
            ):
                notificacion, _creada = (
                    tbl_Notificacion.objects.get_or_create(
                        id_ccpp_id=id_ccpp,
                        id_unidad_id=id_unidad,
                        anio=anio_relativo,
                        mes=mes,
                        defaults={
                            'para': ', '.join(to_list),
                            'cc': ', '.join(cc_list),
                            'cco': ', '.join(bcc_list),
                        },
                    )
                )

        # ==============================================================
        # 9. MARCAR ENVÍO MANUAL COMO EJECUTADO
        #
        # SOLO se llega aquí si correo.send() fue exitoso.
        #
        # NO se modifica:
        # - fecha_envio_programado
        # - tarea_q_id
        #
        # Esos campos pertenecen a la programación automática.
        # ==============================================================

        if notificacion is not None:
            notificacion.envio_ejecutado = True

            notificacion.save(
                update_fields=['envio_ejecutado']
            )

            logger.info(
                'Envío manual registrado correctamente. '
                'notificacion_id=%s',
                notificacion.id_notificacion
            )

        else:
            logger.warning(
                'El correo manual fue enviado correctamente, '
                'pero no se pudo identificar la notificación para '
                'marcar envio_ejecutado=True. '
                'notificacion_id=%s, id_ccpp=%s, id_unidad=%s, '
                'anio=%s, mes=%s',
                notificacion_id,
                id_ccpp,
                id_unidad,
                anio,
                mes,
            )

        # ==============================================================
        # 10. RESPUESTA EXITOSA
        # ==============================================================

        logger.info(
            'Correo manual enviado exitosamente a: %s | Asunto: %s',
            to_list,
            correo.subject
        )

        return JsonResponse(
            {
                'success': True,
                'envio_ejecutado': (
                    notificacion is not None
                ),
            }
        )

    # ==============================================================
    # 11. ERROR SMTP
    # ==============================================================

    except SMTPException as exc:
        logger.error(
            'Error SMTP al intentar enviar correo: %s',
            exc,
            exc_info=True
        )

        return JsonResponse(
            {
                'success': False,
                'error': (
                    'Fallo al autenticar o comunicar con '
                    'el servidor de correos.'
                )
            },
            status=502
        )

    # ==============================================================
    # 12. ERROR GENERAL
    # ==============================================================

    except Exception as exc:
        logger.error(
            'Error interno crítico en enviar_correo: %s',
            exc,
            exc_info=True
        )

        return JsonResponse(
            {
                'success': False,
                'error': (
                    'Ocurrió un error interno en el servidor.'
                )
            },
            status=500
        )








# ═════════════════════════════════════════════════════════════════════════
# 7. GENERACIÓN DE FICHA PDF — NO MODIFICAR
#    (código sin cambios respecto a la versión original en producción)
# ═════════════════════════════════════════════════════════════════════════

def formatear_documento_seis_digitos(valor):
    try:
        solo_numeros  = ''.join(filter(str.isdigit, str(valor)))
        cadena_rellena = solo_numeros.zfill(6)
        return f"{cadena_rellena[0:2]} {cadena_rellena[2:4]} {cadena_rellena[4:6]}"
    except (ValueError, TypeError):
        return '00 00 00'


def obtener_nombre_tecnico_cabecera(id_ccpp):
    try:
        ccpp = tbl_CCPP.objects.get(id_ccpp=id_ccpp)
        return ccpp.tecnico_cabecera.splitlines()[0] if ccpp.tecnico_cabecera else 'No especificado'
    except Exception:
        return 'No disponible'


def generar_encabezado_seccion(texto_titulo, estilo_parrafo, color_linea):
    tabla = Table(
        [[Paragraph(f"<b>{texto_titulo}</b>", estilo_parrafo)]],
        colWidths=[200 * mm],
    )
    tabla.setStyle(TableStyle([
        ('LINEBELOW',     (0, 0), (-1, 0), 2, color_linea),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return tabla


def _altura_parrafo_mm(parrafo, ancho_mm):
    _, h_pt = parrafo.wrap(ancho_mm * mm, 10_000)
    return h_pt / mm


def _fragmentar_texto_control(
    texto_raw, prefijo_html, estilo_parrafo,
    ancho_desc_mm=140, altura_max_mm=None,
):
    if altura_max_mm is None:
        altura_max_mm = ALTURA_MAX_FILA_MM

    lineas        = texto_raw.splitlines()
    fragmentos    = []
    bloque_actual = []

    def _html_bloque(lineas_bloque, es_primero):
        contenido = '<br/>'.join(lineas_bloque)
        return f"{prefijo_html} {contenido}" if es_primero else contenido

    def _altura_bloque(lineas_bloque, es_primero):
        return _altura_parrafo_mm(
            Paragraph(_html_bloque(lineas_bloque, es_primero), estilo_parrafo),
            ancho_desc_mm,
        )

    es_primer_fragmento = True

    for linea in lineas:
        bloque_prueba = bloque_actual + [linea]
        if _altura_bloque(bloque_prueba, es_primer_fragmento) <= altura_max_mm:
            bloque_actual = bloque_prueba
        else:
            if bloque_actual:
                fragmentos.append(_html_bloque(bloque_actual, es_primer_fragmento))
                es_primer_fragmento = False
                bloque_actual = []

            palabras     = linea.split(' ')
            palabras_acc = []

            for palabra in palabras:
                prueba = palabras_acc + [palabra]
                if _altura_bloque([' '.join(prueba)], es_primer_fragmento) <= altura_max_mm:
                    palabras_acc = prueba
                else:
                    if palabras_acc:
                        fragmentos.append(
                            _html_bloque([' '.join(palabras_acc)], es_primer_fragmento)
                        )
                        es_primer_fragmento = False
                        palabras_acc = [palabra]
                    else:
                        fragmentos.append(_html_bloque([palabra], es_primer_fragmento))
                        es_primer_fragmento = False
                        palabras_acc = []

            if palabras_acc:
                bloque_actual = [' '.join(palabras_acc)]

    if bloque_actual:
        fragmentos.append(_html_bloque(bloque_actual, es_primer_fragmento))

    return fragmentos or [f"{prefijo_html} "]


def _construir_filas_control(
    control, estilo_texto_cuerpo, estilo_titulo_principal,
    gris_opaco_deshabilitado, verde_exito, rojo_alerta,
):
    color_txt = gris_opaco_deshabilitado if control.opacar else '#374151'

    if control.opacar:
        color_prem = gris_opaco_deshabilitado
    else:
        p_u        = control.premisa.upper() if control.premisa else ''
        color_prem = (
            verde_exito
            if ('RECOMENDADO' in p_u or 'RECOMENDABLE' in p_u)
            else rojo_alerta
        )

    col_periodo_html = (
        f'<font color="{color_txt}">{control.periodo}</font><br/>'
        f'<font color="{color_prem}" size="8"><b>{control.premisa or ""}</b></font>'
    )

    insp      = control.id_inspeccion
    color_cod = (
        gris_opaco_deshabilitado if control.opacar
        else (insp.color_inspeccion if insp and insp.color_inspeccion else '#374151')
    )
    color_nom = gris_opaco_deshabilitado if control.opacar else '#374151'

    prefijo_html = (
        f'<font color="{color_cod}"><b>'
        f'{insp.codigo_inspeccion if insp else "N/A"}'
        f'</b></font> - '
        f'<font color="{color_nom}"><u>'
        f'{insp.nombre_inspeccion.upper() if insp else "S/I"}'
        f':</u></font>'
    )

    estilo_fila = ParagraphStyle(
        'EF', parent=estilo_texto_cuerpo,
        textColor=colors.HexColor(color_txt),
    )
    estilo_ok = ParagraphStyle(
        'CS', parent=estilo_titulo_principal,
        fontSize=11,
        textColor=colors.HexColor(color_txt),
    )

    fragmentos = _fragmentar_texto_control(
        control.control or '', prefijo_html, estilo_fila, ancho_desc_mm=140,
    )

    filas = []
    for idx, frag_html in enumerate(fragmentos):
        es_primera = (idx == 0)
        filas.append([
            Paragraph(col_periodo_html if es_primera else '', estilo_fila),
            Paragraph(f'<font color="{color_txt}">{frag_html}</font>', estilo_fila),
            Paragraph(
                f"<b>{'✓' if control.ejecutado else ''}</b>" if es_primera else '',
                estilo_ok,
            ),
        ])
    return filas


def exportar_ficha_pdf(request, ficha_id, ccpp_id, return_buffer=False, descargar_directo='false', id_control=None):
    """Genera el PDF de una ficha. Si return_buffer=True devuelve bytes en vez de FileResponse."""
    debe_descargar = str(descargar_directo).lower() == 'true'

    try:
        ruta_regular = finders.find('fonts/Poppins-Regular.ttf') or os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Regular.ttf')
        ruta_negrita = finders.find('fonts/Poppins-Bold.ttf')    or os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Bold.ttf')
        pdfmetrics.registerFont(TTFont('Poppins',      ruta_regular))
        pdfmetrics.registerFont(TTFont('Poppins-Bold', ruta_negrita))
        fuente_reg, fuente_bold = 'Poppins', 'Poppins-Bold'
    except Exception:
        fuente_reg, fuente_bold = 'Helvetica', 'Helvetica-Bold'

    try:
        objeto_ficha = tbl_Ficha.objects.get(id=ficha_id)

        # Permite pasar el control por query string cuando se accede vía
        # navegador (botón "Ver Ficha"), sin afectar las llamadas internas
        # que ya reciben id_control como argumento directo.
        if id_control is None and request is not None:
            id_control = request.GET.get('control')

        lista_controles = tbl_FichaControl.objects.filter(id_ficha=objeto_ficha)
        if id_control:
            lista_controles = lista_controles.filter(pk=id_control)

        nombre_tecnico     = obtener_nombre_tecnico_cabecera(ccpp_id)
        titulo_archivo_pdf = objeto_ficha.titulo or f"Ficha_{objeto_ficha.id}"
    except tbl_Ficha.DoesNotExist:
        return None if return_buffer else FileResponse(
            io.BytesIO(b'Error: La ficha solicitada no existe.'), content_type='text/plain'
        )
    except Exception as exc:
        return None if return_buffer else FileResponse(
            io.BytesIO(f'Error inesperado: {exc}'.encode()), content_type='text/plain'
        )

    gris_oscuro              = colors.HexColor('#374151')
    gris_suave               = colors.HexColor('#d1d5db')
    gris_opaco_deshabilitado = '#e5e7eb'
    rojo_enfasis             = colors.HexColor('#b91c1c')
    fondo_naranja_claro      = colors.HexColor('#FFE9D7')
    verde_exito              = '#166534'
    rojo_alerta              = '#991b1b'

    estilo_titulo_principal = ParagraphStyle('T1', fontSize=13,  fontName=fuente_bold, alignment=TA_CENTER)
    estilo_subtitulo_rojo   = ParagraphStyle('T2', fontSize=16,  fontName=fuente_bold, textColor=rojo_enfasis, alignment=TA_CENTER, leading=18)
    estilo_capitulo         = ParagraphStyle('T3', fontSize=10,  fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_unidad           = ParagraphStyle('T4', fontSize=8,   fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_titulo_seccion   = ParagraphStyle('S1', fontSize=10,  fontName=fuente_bold, textColor=colors.black)
    estilo_texto_cuerpo     = ParagraphStyle('C1', fontSize=9.5, fontName=fuente_reg,  leading=12, textColor=gris_oscuro)
    estilo_etiqueta_info    = ParagraphStyle('L1', fontSize=8.5, fontName=fuente_reg,  textColor=gris_oscuro)
    estilo_firma_pie        = ParagraphStyle('F1', fontSize=7.5, fontName=fuente_reg,  textColor=colors.HexColor('#94a3b8'), alignment=TA_CENTER)

    def dibujar_elementos_estaticos(canvas_obj, documento_obj):
        canvas_obj.saveState()
        try:
            ruta_logo = finders.find('img/logo.png') or os.path.join(settings.BASE_DIR, 'static/img/logo.png')
            imagen_izq = Image(ruta_logo, width=35*mm, height=13*mm) if os.path.exists(ruta_logo) else ''
            imagen_der = ''
            if objeto_ficha.logo and os.path.exists(objeto_ficha.logo.path):
                imagen_der = Image(objeto_ficha.logo.path, width=15*mm, height=15*mm)
        except Exception:
            imagen_izq = imagen_der = ''

        datos_u    = objeto_ficha.doc_unidad
        codigo_doc = formatear_documento_seis_digitos(datos_u.doc) if datos_u else '00 00 00'

        t_header = Table(
            [[imagen_izq, [
                Paragraph('CONTROL LIBRO DEL EDIFICIO', estilo_titulo_principal),
                Paragraph(codigo_doc, estilo_subtitulo_rojo),
                Paragraph(datos_u.capitulo if datos_u else '', estilo_capitulo),
                Paragraph(datos_u.unidad   if datos_u else '', estilo_unidad),
            ], imagen_der]],
            colWidths=[30*mm, 140*mm, 30*mm],
        )
        t_header.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (0, 0),   'LEFT'),
            ('ALIGN',         (2, 0), (2, 0),   'RIGHT'),
            ('LINEBELOW',     (0, 0), (-1, 0),   2, colors.black),
            ('LEFTPADDING',   (0, 0), (-1, -1),  0),
            ('RIGHTPADDING',  (0, 0), (-1, -1),  0),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  2*mm),
        ]))

        y_base = documento_obj.height + documento_obj.topMargin - 16*mm
        t_header.wrapOn(canvas_obj, documento_obj.width, documento_obj.topMargin)
        t_header.drawOn(canvas_obj, documento_obj.leftMargin, y_base)

        fecha_generacion = datetime.now(ZONA_HORARIA)
        t_meta = Table([[
            Paragraph(f"<b>Técnico Cabecera:</b> {nombre_tecnico}", estilo_etiqueta_info),
            Paragraph(
                f"<b>Fecha:</b> {fecha_generacion.strftime('%d/%m/%Y')}",
                ParagraphStyle('FD', parent=estilo_etiqueta_info, alignment=TA_RIGHT),
            ),
        ]], colWidths=[120*mm, 80*mm])
        t_meta.setStyle(TableStyle([
            ('LEFTPADDING',  (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        t_meta.wrapOn(canvas_obj, 200*mm, 5*mm)
        t_meta.drawOn(canvas_obj, documento_obj.leftMargin, y_base - 7*mm)
        canvas_obj.restoreState()

    buffer_memoria = io.BytesIO()
    doc_pdf = SimpleDocTemplate(
        buffer_memoria,
        pagesize=letter,
        topMargin=35*mm, bottomMargin=15*mm,
        leftMargin=8*mm, rightMargin=8*mm,
        title=titulo_archivo_pdf,
    )

    elementos = []
    elementos.append(generar_encabezado_seccion('✓ CONTROLES', estilo_titulo_seccion, gris_suave))
    elementos.append(Spacer(1, 2*mm))

    filas_controles = [[
        Paragraph('<b>PERIODO</b>',    estilo_texto_cuerpo),
        Paragraph('<b>INSPECCIÓN</b>', estilo_texto_cuerpo),
        Paragraph('<b>OK</b>',         estilo_texto_cuerpo),
    ]]

    for control in lista_controles:
        if not control.ocultar:
            filas_controles.extend(_construir_filas_control(
                control, estilo_texto_cuerpo, estilo_titulo_principal,
                gris_opaco_deshabilitado, verde_exito, rojo_alerta,
            ))

    if len(filas_controles) > 1:
        t_controles = LongTable(
            filas_controles,
            colWidths=[40*mm, 140*mm, 20*mm],
            repeatRows=1, splitByRow=1,
        )
        t_controles.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  fondo_naranja_claro),
            ('GRID',        (0, 0), (-1, 0),  0.5, gris_suave),
            ('LINEBELOW',   (0, 1), (-1, -2), 0.3, gris_suave),
            ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',       (2, 0), (2, -1),  'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',(0, 0), (-1, -1), 3),
        ]))
        elementos.append(t_controles)
    else:
        elementos.append(Paragraph('No hay controles registrados.', estilo_texto_cuerpo))

    for titulo, contenido in [
        ('✓ PRECAUCIONES',   objeto_ficha.precaucion),
        ('✓ PRESCRIPCIONES', objeto_ficha.prescripcion),
        ('✓ PROHIBICIONES',  objeto_ficha.prohibicion),
    ]:
        if contenido:
            elementos.append(KeepTogether([
                Spacer(1, 4*mm),
                generar_encabezado_seccion(titulo, estilo_titulo_seccion, gris_suave),
                Spacer(1, 1*mm),
                Paragraph(contenido.replace('\n', '<br/>'), estilo_texto_cuerpo),
            ]))

    elementos.append(Spacer(1, 6*mm))
    t_firma = Table(
        [
            [
                Paragraph('<b>FECHA INSPECCIÓN</b>', estilo_texto_cuerpo),
                Paragraph('<b>CONTROL</b>',          estilo_texto_cuerpo),
                Paragraph('<b>OBSERVACIONES</b>',    estilo_texto_cuerpo),
            ],
            ['', Paragraph('Firma', estilo_firma_pie), ''],
        ],
        colWidths=[50*mm, 50*mm, 100*mm],
        rowHeights=[None, 24*mm],
    )
    t_firma.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  fondo_naranja_claro),
        ('GRID',          (0, 0), (-1, -1), 0.5, gris_oscuro),
        ('ALIGN',         (1, 1), (1, 1),   'CENTER'),
        ('VALIGN',        (1, 1), (1, 1),   'BOTTOM'),
        ('BOTTOMPADDING', (1, 1), (1, 1),   1.5*mm),
        ('VALIGN',        (0, 0), (-1, 0),  'MIDDLE'),
    ]))
    elementos.append(KeepTogether([t_firma]))

    if objeto_ficha.foto:
        try:
            if os.path.exists(objeto_ficha.foto.path):
                elementos.append(KeepTogether([
                    Spacer(1, 5*mm),
                    generar_encabezado_seccion('✓ ANEXOS', estilo_titulo_seccion, gris_suave),
                    Spacer(1, 3*mm),
                    Image(objeto_ficha.foto.path, width=195*mm, height=80*mm, kind='proportional'),
                ]))
        except Exception:
            pass

    doc_pdf.build(
        elementos,
        onFirstPage=dibujar_elementos_estaticos,
        onLaterPages=dibujar_elementos_estaticos,
    )
    buffer_memoria.seek(0)

    if return_buffer:
        return buffer_memoria.getvalue()
    return FileResponse(
        buffer_memoria,
        as_attachment=debe_descargar,
        filename=f'{titulo_archivo_pdf}.pdf',
    )