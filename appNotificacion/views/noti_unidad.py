"""
Vistas para gestión de notificaciones por unidad-CCPP.

Lista todas las inspecciones programadas para una unidad específica
en todos los períodos disponibles, permitiendo:
    - Gestionar correos (para, cc, cco) para notificaciones automáticas
    - Asignar controles de ficha
    - Programar envíos automáticos
    - Envío manual de correos
    - Asignar ficha a la unidad

Reutiliza funciones auxiliares de noti_periodo.py
"""

import logging
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from appAdministrador.models import (
    tbl_CCPP, tbl_Cronograma, tbl_FichaControl,
    tbl_inspeccion, tbl_Notificacion, tbl_Unidad,
    tbl_CCPP_Unidad, tbl_NotificacionDocumento,
)
from appAdministrador.views.moduloGlobal import validar_permisos

# Agregar al inicio
from django.conf import settings

# Asegurarse de importar MESES_VALIDOS
from appNotificacion.views.noti_periodo import (
    MESES_VALIDOS,
    calcular_anio_real,
    calcular_anio_relativo,
    extraer_correos,
    obtener_anios_disponibles,
    _programar_envio,
    _cancelar_tarea_programada,
)

logger = logging.getLogger(__name__)


def _obtener_correos_ccpp(ccpp):
    """Obtiene las listas de correos disponibles para el CCPP."""
    return {
        'para': list(set(
            extraer_correos(ccpp.administracion_edificio) +
            extraer_correos(ccpp.tecnico_cabecera)
        )),
        'cc': list(set(
            extraer_correos(ccpp.operario_comunidad) +
            extraer_correos(ccpp.tecnico_especialista) +
            extraer_correos(ccpp.empresa_especializada)
        )),
        'cco': list(set(extraer_correos(ccpp.copia_oculta))),
    }

def _obtener_inspecciones_unidad(ccpp_id, unidad_id):
    """
    Obtiene todas las inspecciones programadas para una unidad-CCPP.
    
    Returns:
        list: Lista de diccionarios con la información de cada inspección
    """
    cronogramas = tbl_Cronograma.objects.filter(
        id_ccpp_id=ccpp_id,
        id_unidad_id=unidad_id,
    ).select_related('id_unidad')

    inspecciones = []
    
    for cronograma in cronogramas:
        anio_relativo = cronograma.anios
        
        for mes in MESES_VALIDOS:
            codigo_raw = getattr(cronograma, mes, None)
            if not codigo_raw:
                continue
            
            codigo = str(codigo_raw).strip()
            if not codigo:
                continue
            
            inspeccion = tbl_inspeccion.objects.filter(id=codigo).first()
            
            notificacion = tbl_Notificacion.objects.filter(
                id_ccpp_id=ccpp_id,
                id_unidad_id=unidad_id,
                anio=anio_relativo,
                mes=mes,
            ).first()
            
            ccpp = tbl_CCPP.objects.get(id_ccpp=ccpp_id)
            anio_real = calcular_anio_real(ccpp.fecha_entrega, anio_relativo)
            
            key = f"{ccpp_id}_{unidad_id}_{anio_relativo}_{mes}"
            
            # Determinar estado de la notificación (mismos estados que página de notificaciones)
            notificacion_existe = bool(notificacion)
            correo_enviado = bool(notificacion and notificacion.envio_ejecutado)
            tiene_respuesta = bool(
                notificacion and (
                    notificacion.FechaResp or
                    notificacion.RespRevision or
                    notificacion.RespControlador or
                    notificacion.RespVia or
                    notificacion.RespObservacion or
                    notificacion.RespInspEjecutada
                )
            )
            
            # Determinar estado para mostrar
            if tiene_respuesta:
                estado = 'respuesta'
                estado_label = 'Con respuesta'
                estado_color = '#d946ef'  # fuchsia-500
            elif correo_enviado:
                estado = 'enviado'
                estado_label = 'Notificado'
                estado_color = '#10b981'  # emerald-500
            elif notificacion_existe:
                estado = 'espera'
                estado_label = 'En espera'
                estado_color = '#f59e0b'  # amber-500
            else:
                estado = 'sin_notificar'
                estado_label = 'Sin notificar'
                estado_color = '#94a3b8'  # slate-400
            
            # Obtener listas de correos separadas
            para_list = []
            cc_list = []
            cco_list = []
            
            if notificacion:
                if notificacion.para:
                    para_list = [c.strip() for c in notificacion.para.split(',') if c.strip()]
                if notificacion.cc:
                    cc_list = [c.strip() for c in notificacion.cc.split(',') if c.strip()]
                if notificacion.cco:
                    cco_list = [c.strip() for c in notificacion.cco.split(',') if c.strip()]
            
            inspecciones.append({
                'key': key,
                'anio_relativo': anio_relativo,
                'anio_real': anio_real,
                'mes': mes,
                'id_unidad': unidad_id,
                'inspeccion_id': inspeccion.id if inspeccion else None,
                'codigo_inspeccion': inspeccion.codigo_inspeccion if inspeccion else codigo,
                'nombre_inspeccion': inspeccion.nombre_inspeccion if inspeccion else f"Inspección: {codigo} (no encontrada)",
                'color_inspeccion': inspeccion.color_inspeccion if inspeccion else '#9CA3AF',
                'notificacion_existe': notificacion_existe,
                'notificacion_id': notificacion.id_notificacion if notificacion else None,
                'envio_ejecutado': correo_enviado,
                'fecha_envio_programado': notificacion.fecha_envio_programado if notificacion else None,
                'para': notificacion.para if notificacion else '',
                'cc': notificacion.cc if notificacion else '',
                'cco': notificacion.cco if notificacion else '',
                'para_list': para_list,
                'cc_list': cc_list,
                'cco_list': cco_list,
                'id_ficha_control': notificacion.id_ficha_control_id if notificacion else None,
                'tiene_respuesta': tiene_respuesta,
                'estado': estado,
                'estado_label': estado_label,
                'estado_color': estado_color,
            })
    
    # Ordenar por año relativo descendente y mes
    orden_meses = {mes: idx for idx, mes in enumerate(MESES_VALIDOS)}
    inspecciones.sort(
        key=lambda x: (-x['anio_relativo'], orden_meses[x['mes']])
    )
    
    return inspecciones



@login_required
@validar_permisos
def gestion_notificaciones_unidad(request, ccpp_id, unidad_id):
    """
    Vista principal para gestión de notificaciones por unidad.
    """
    try:
        ccpp = tbl_CCPP.objects.get(id_ccpp=ccpp_id, habilitada=True)
    except tbl_CCPP.DoesNotExist:
        messages.error(request, 'CCPP no encontrada o no habilitada.')
        return redirect('/')
    
    try:
        unidad = tbl_Unidad.objects.get(id_unidad=unidad_id)
    except tbl_Unidad.DoesNotExist:
        messages.error(request, 'Unidad no encontrada.')
        return redirect('gestion_ccpp', ccpp_id=ccpp_id)
    
    # Verificar que la unidad pertenece al CCPP
    relacion = tbl_CCPP_Unidad.objects.filter(
        ccpp_id=ccpp_id,
        unidad_id=unidad_id,
    ).select_related('ficha').first()
    
    if not relacion:
        messages.error(request, 'La unidad no está asignada a este CCPP.')
        return redirect('gestion_ccpp', ccpp_id=ccpp_id)
    
    # Obtener inspecciones
    inspecciones = _obtener_inspecciones_unidad(ccpp_id, unidad_id)
    
    # Obtener correos disponibles
    correos = _obtener_correos_ccpp(ccpp)
    
    # Obtener ficha asignada y controles
    ficha_asignada = relacion.ficha
    controles_disponibles = []
    
    if ficha_asignada:
        controles_disponibles = tbl_FichaControl.objects.filter(
            id_ficha=ficha_asignada
        ).select_related('id_inspeccion').order_by('codigo_control')
    
    # Obtener selección de correos actual
    seleccion_para = []
    seleccion_cc = []
    seleccion_cco = []
    
    for insp in inspecciones:
        if insp['para']:
            seleccion_para = [c.strip() for c in insp['para'].split(',') if c.strip()]
        if insp['cc']:
            seleccion_cc = [c.strip() for c in insp['cc'].split(',') if c.strip()]
        if insp['cco']:
            seleccion_cco = [c.strip() for c in insp['cco'].split(',') if c.strip()]
    
    # Verificar si hay notificaciones con envío ejecutado
    hay_envios_ejecutados = any(insp['envio_ejecutado'] for insp in inspecciones)

    # Verificar si hay controles de ficha ya asignados en los registros de
    # notificación. Se usa para advertir al usuario, antes de cambiar la
    # ficha de la unidad, que esos controles se perderán (ver
    # tbl_CCPP_Unidad.save(), que los limpia automáticamente al cambiar la
    # ficha vinculada).
    hay_controles_asignados = any(insp['id_ficha_control'] for insp in inspecciones)
    
    # ═══════════════════════════════════════════════════════
    # DATOS PARA EL MODAL DE CRONOGRAMA
    # ═══════════════════════════════════════════════════════
    
    # Catálogo de inspecciones para el dropdown
    inspecciones_catalogo_lista = tbl_inspeccion.objects.all().order_by('codigo_inspeccion')
    
    # Cronogramas de la unidad
    cronogramas = tbl_Cronograma.objects.filter(
        id_ccpp_id=ccpp_id,
        id_unidad_id=unidad_id,
    ).order_by('anios')
    
    cronograma_dict_modal = {c.anios: c for c in cronogramas}
    
    anio_base = ccpp.fecha_entrega.year if ccpp.fecha_entrega else None
    total_anios_ccpp = range((ccpp.cantidad_anios or 0) + 1)
    
    filas_cronograma_modal = []
    
    for anio_idx in total_anios_ccpp:
        cronograma_fila = cronograma_dict_modal.get(anio_idx)
        anio_calendario = (anio_base + anio_idx) if anio_base is not None else None
        
        meses_fila = []
        for mes in MESES_VALIDOS:
            valor_mes = getattr(cronograma_fila, mes, '') if cronograma_fila else ''
            meses_fila.append({
                "mes": mes,
                "valor": valor_mes,
            })
        
        filas_cronograma_modal.append({
            "anio_relativo": anio_idx,
            "anio_calendario": anio_calendario,
            "meses": meses_fila,
            "nota": cronograma_fila.nota if cronograma_fila else "",
        })
    
    context = {
        'ccpp': ccpp,
        'unidad': unidad,
        'ficha_asignada': ficha_asignada,
        'inspecciones': inspecciones,
        'correos_para': correos['para'],
        'correos_cc': correos['cc'],
        'correos_cco': correos['cco'],
        'seleccion_para': seleccion_para,
        'seleccion_cc': seleccion_cc,
        'seleccion_cco': seleccion_cco,
        'controles_disponibles': controles_disponibles,
        'hay_envios_ejecutados': hay_envios_ejecutados,
        'hay_controles_asignados': hay_controles_asignados,
        # Datos para el modal de cronograma
        'filas_cronograma_modal': filas_cronograma_modal,
        'meses_modal': MESES_VALIDOS,
        'inspecciones_catalogo_lista': inspecciones_catalogo_lista,
    }
    
    return render(request, 'gestion_notificaciones_unidad.html', context)











@login_required
@validar_permisos
@require_POST
def guardar_notificaciones_unidad___(request, ccpp_id, unidad_id):
    """
    Guarda la configuración de notificaciones para todas las inspecciones
    de una unidad-CCPP de forma masiva.

    IMPORTANTE: la iteración se hace sobre el campo oculto "filas" (uno por
    cada inspección renderizada en la tabla), NO sobre los campos
    "control_<key>". Estos últimos solo existen en el formulario si la
    unidad tiene una ficha asignada, así que depender de ellos dejaba de
    procesar (y por tanto de guardar/eliminar) los correos de cualquier
    unidad sin ficha vinculada.
    """
    import json
    
    try:
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)
        unidad = get_object_or_404(tbl_Unidad, id_unidad=unidad_id)
    except Exception as exc:
        logger.error(f"Error al obtener CCPP/Unidad: {exc}")
        messages.error(request, 'Error al obtener los datos.')
        return redirect('gestion_ccpp', ccpp_id=ccpp_id)
    
    # Verificar si se debe omitir notificaciones enviadas
    omitir_enviadas = request.POST.get('omitir_enviadas') == '1'
    
    # Parsear correos por registro desde el JSON
    correos_por_registro = {}
    correos_json = request.POST.get('correos_seleccionados', '{}')
    try:
        correos_por_registro = json.loads(correos_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("JSON de correos inválido, usando vacío")
    
    # Obtener correos disponibles para validación
    correos_disponibles = _obtener_correos_ccpp(ccpp)
    
    # Todas las filas renderizadas en la tabla, sin importar si la unidad
    # tiene ficha asignada o no.
    claves_filas = request.POST.getlist('filas')
    
    contador_creadas = 0
    contador_actualizadas = 0
    contador_omitidas = 0
    contador_programadas = 0
    contador_canceladas = 0
    
    try:
        with transaction.atomic():
            for key in claves_filas:
                # Parsear la clave para obtener anio y mes
                partes = key.split('_')
                if len(partes) != 4:
                    continue
                
                _, unidad_id_key, anio_str, mes = partes
                
                if unidad_id_key != str(unidad_id):
                    continue
                
                if mes not in MESES_VALIDOS:
                    continue
                
                try:
                    anio_relativo = int(anio_str)
                except (TypeError, ValueError):
                    continue
                
                # Verificar si existe notificación y si está enviada
                notificacion_existente = tbl_Notificacion.objects.filter(
                    id_ccpp_id=ccpp_id,
                    id_unidad_id=unidad_id,
                    anio=anio_relativo,
                    mes=mes,
                ).first()
                
                if omitir_enviadas and notificacion_existente and notificacion_existente.envio_ejecutado:
                    contador_omitidas += 1
                    continue
                
                # Obtener correos para este registro
                correos_registro = correos_por_registro.get(key, {})
                para_list = [c for c in correos_registro.get('para', '').split(',') if c.strip() and c.strip() in correos_disponibles['para']]
                cc_list = [c for c in correos_registro.get('cc', '').split(',') if c.strip() and c.strip() in correos_disponibles['cc']]
                cco_list = [c for c in correos_registro.get('cco', '').split(',') if c.strip() and c.strip() in correos_disponibles['cco']]
                
                para_str = ', '.join(para_list)
                cc_str = ', '.join(cc_list)
                cco_str = ', '.join(cco_list)
                
                # Obtener o crear la notificación
                notificacion, creada = tbl_Notificacion.objects.get_or_create(
                    id_ccpp_id=ccpp_id,
                    id_unidad_id=unidad_id,
                    anio=anio_relativo,
                    mes=mes,
                    defaults={
                        'para': para_str,
                        'cc': cc_str,
                        'cco': cco_str,
                    }
                )
                
                if creada:
                    contador_creadas += 1
                else:
                    contador_actualizadas += 1
                
                # Se sobrescriben siempre los correos con lo que llegó del
                # formulario, así se garantiza que una eliminación (dejar
                # el campo vacío) también se persista.
                notificacion.para = para_str
                notificacion.cc = cc_str
                notificacion.cco = cco_str
                
                # Procesar control de ficha. El campo "control_<key>" solo
                # existe en el POST si la unidad tiene ficha asignada; si no
                # existe, request.POST.get() devuelve None y se limpia.
                control_id = request.POST.get(f'control_{key}')
                if control_id and str(control_id).isdigit():
                    control_valido = tbl_FichaControl.objects.filter(
                        pk=control_id,
                        id_ficha__ccpp_unidades__ccpp_id=ccpp_id,
                        id_ficha__ccpp_unidades__unidad_id=unidad_id,
                    ).exists()
                    
                    notificacion.id_ficha_control_id = int(control_id) if control_valido else None
                else:
                    notificacion.id_ficha_control_id = None
                
                notificacion.save()
                
                # ── Procesar programación de envío ──────────────────────
                fecha_envio_key = f"fecha_envio_{key}"
                fecha_envio_str = request.POST.get(fecha_envio_key, '').strip()
                
                if not para_list:
                    # Sin correos "Para" no puede existir un envío
                    # automático programado ni pendiente: se cancela
                    # cualquier tarea/fecha activa.
                    if notificacion.tarea_q_id or notificacion.fecha_envio_programado:
                        _cancelar_tarea_programada(notificacion)
                        contador_canceladas += 1
                    if fecha_envio_str:
                        messages.warning(
                            request,
                            f'Inspección {notificacion.mes} año {anio_relativo}: '
                            'Para programar el envío automático debes seleccionar '
                            'al menos un correo en el campo "Para".'
                        )
                elif fecha_envio_str:
                    if notificacion.envio_ejecutado:
                        # Ya se había enviado antes: se reabre el registro
                        # para permitir programar un nuevo envío automático,
                        # sin que el campo quede bloqueado en el template.
                        tbl_Notificacion.objects.filter(pk=notificacion.pk).update(
                            envio_ejecutado=False,
                            tarea_q_id=None,
                            fecha_envio_programado=None,
                        )
                        notificacion.envio_ejecutado = False
                        notificacion.tarea_q_id = None
                        notificacion.fecha_envio_programado = None
                    
                    _programar_envio(request, notificacion, fecha_envio_str)
                    contador_programadas += 1
                else:
                    # Hay correos "Para" pero no se definió fecha de envío:
                    # si existía una programación previa activa, se cancela
                    # para reflejar la intención del usuario de retirarla.
                    if not notificacion.envio_ejecutado and (notificacion.tarea_q_id or notificacion.fecha_envio_programado):
                        _cancelar_tarea_programada(notificacion)
                        contador_canceladas += 1
        
        mensaje = f'Proceso completado: {contador_creadas} creadas, {contador_actualizadas} actualizadas'
        if contador_omitidas > 0:
            mensaje += f', {contador_omitidas} omitidas'
        if contador_programadas > 0:
            mensaje += f', {contador_programadas} programadas'
        if contador_canceladas > 0:
            mensaje += f', {contador_canceladas} programaciones canceladas'
        
        messages.success(request, mensaje)
        
    except Exception as exc:
        logger.error(f"Error en guardar_notificaciones_unidad: {exc}")
        messages.error(request, f'Error al guardar las notificaciones: {exc}')
    
    return redirect('gestion_notificaciones_unidad', ccpp_id=ccpp_id, unidad_id=unidad_id)



@login_required
@validar_permisos
@require_POST
def guardar_notificaciones_unidad(request, ccpp_id, unidad_id):
    """
    Guarda la configuración de notificaciones para todas las inspecciones
    de una unidad-CCPP de forma masiva.

    IMPORTANTE: la iteración se hace sobre el campo oculto "filas" (uno por
    cada inspección renderizada en la tabla), NO sobre los campos
    "control_<key>". Estos últimos solo existen en el formulario si la
    unidad tiene una ficha asignada, así que depender de ellos dejaba de
    procesar (y por tanto de guardar/eliminar) los correos de cualquier
    unidad sin ficha vinculada.

    Los avisos de "sin correos Para" y de "fecha no programada" que antes
    se emitían uno por cada registro afectado (pudiendo inundar la pantalla
    con decenas de mensajes) ahora se acumulan durante el recorrido y se
    informan al final como un único mensaje consolidado por tipo de aviso.
    """
    import json

    try:
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)
        unidad = get_object_or_404(tbl_Unidad, id_unidad=unidad_id)
    except Exception as exc:
        logger.error(f"Error al obtener CCPP/Unidad: {exc}")
        messages.error(request, 'Error al obtener los datos.')
        return redirect('gestion_ccpp', ccpp_id=ccpp_id)

    # Verificar si se debe omitir notificaciones enviadas
    omitir_enviadas = request.POST.get('omitir_enviadas') == '1'

    # Parsear correos por registro desde el JSON
    correos_por_registro = {}
    correos_json = request.POST.get('correos_seleccionados', '{}')
    try:
        correos_por_registro = json.loads(correos_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("JSON de correos inválido, usando vacío")

    # Obtener correos disponibles para validación
    correos_disponibles = _obtener_correos_ccpp(ccpp)

    # Todas las filas renderizadas en la tabla, sin importar si la unidad
    # tiene ficha asignada o no.
    claves_filas = request.POST.getlist('filas')

    contador_creadas = 0
    contador_actualizadas = 0
    contador_omitidas = 0
    contador_programadas = 0
    contador_canceladas = 0

    # Avisos consolidados: en vez de emitir un messages.warning() por cada
    # registro afectado, se acumulan aquí y se reportan como un único
    # mensaje por categoría al finalizar el proceso.
    avisos_sin_correo_para = []
    avisos_fecha_no_programada = []

    try:
        with transaction.atomic():
            for key in claves_filas:
                # Parsear la clave para obtener anio y mes
                partes = key.split('_')
                if len(partes) != 4:
                    continue

                _, unidad_id_key, anio_str, mes = partes

                if unidad_id_key != str(unidad_id):
                    continue

                if mes not in MESES_VALIDOS:
                    continue

                try:
                    anio_relativo = int(anio_str)
                except (TypeError, ValueError):
                    continue

                # Verificar si existe notificación y si está enviada
                notificacion_existente = tbl_Notificacion.objects.filter(
                    id_ccpp_id=ccpp_id,
                    id_unidad_id=unidad_id,
                    anio=anio_relativo,
                    mes=mes,
                ).first()

                if omitir_enviadas and notificacion_existente and notificacion_existente.envio_ejecutado:
                    contador_omitidas += 1
                    continue

                # Obtener correos para este registro
                correos_registro = correos_por_registro.get(key, {})
                para_list = [c for c in correos_registro.get('para', '').split(',') if c.strip() and c.strip() in correos_disponibles['para']]
                cc_list = [c for c in correos_registro.get('cc', '').split(',') if c.strip() and c.strip() in correos_disponibles['cc']]
                cco_list = [c for c in correos_registro.get('cco', '').split(',') if c.strip() and c.strip() in correos_disponibles['cco']]

                para_str = ', '.join(para_list)
                cc_str = ', '.join(cc_list)
                cco_str = ', '.join(cco_list)

                # Obtener o crear la notificación
                notificacion, creada = tbl_Notificacion.objects.get_or_create(
                    id_ccpp_id=ccpp_id,
                    id_unidad_id=unidad_id,
                    anio=anio_relativo,
                    mes=mes,
                    defaults={
                        'para': para_str,
                        'cc': cc_str,
                        'cco': cco_str,
                    }
                )

                if creada:
                    contador_creadas += 1
                else:
                    contador_actualizadas += 1

                # Se sobrescriben siempre los correos con lo que llegó del
                # formulario, así se garantiza que una eliminación (dejar
                # el campo vacío) también se persista.
                notificacion.para = para_str
                notificacion.cc = cc_str
                notificacion.cco = cco_str

                # Procesar control de ficha. El campo "control_<key>" solo
                # existe en el POST si la unidad tiene ficha asignada; si no
                # existe, request.POST.get() devuelve None y se limpia.
                control_id = request.POST.get(f'control_{key}')
                if control_id and str(control_id).isdigit():
                    control_valido = tbl_FichaControl.objects.filter(
                        pk=control_id,
                        id_ficha__ccpp_unidades__ccpp_id=ccpp_id,
                        id_ficha__ccpp_unidades__unidad_id=unidad_id,
                    ).exists()

                    notificacion.id_ficha_control_id = int(control_id) if control_valido else None
                else:
                    notificacion.id_ficha_control_id = None

                notificacion.save()

                # ── Procesar programación de envío ──────────────────────
                fecha_envio_key = f"fecha_envio_{key}"
                fecha_envio_str = request.POST.get(fecha_envio_key, '').strip()
                anio_real_registro = calcular_anio_real(ccpp.fecha_entrega, anio_relativo)
                etiqueta_registro = f'{mes.capitalize()} {anio_real_registro}'

                if not para_list:
                    # Sin correos "Para" no puede existir un envío
                    # automático programado ni pendiente: se cancela
                    # cualquier tarea/fecha activa.
                    if notificacion.tarea_q_id or notificacion.fecha_envio_programado:
                        _cancelar_tarea_programada(notificacion)
                        contador_canceladas += 1
                    if fecha_envio_str:
                        avisos_sin_correo_para.append(etiqueta_registro)
                elif fecha_envio_str:
                    if notificacion.envio_ejecutado:
                        # Ya se había enviado antes: se reabre el registro
                        # para permitir programar un nuevo envío automático,
                        # sin que el campo quede bloqueado en el template.
                        tbl_Notificacion.objects.filter(pk=notificacion.pk).update(
                            envio_ejecutado=False,
                            tarea_q_id=None,
                            fecha_envio_programado=None,
                        )
                        notificacion.envio_ejecutado = False
                        notificacion.tarea_q_id = None
                        notificacion.fecha_envio_programado = None

                    error_programacion = _programar_envio(request, notificacion, fecha_envio_str)
                    if error_programacion:
                        avisos_fecha_no_programada.append(
                            f'{etiqueta_registro} ({error_programacion})'
                        )
                    else:
                        contador_programadas += 1
                else:
                    # Hay correos "Para" pero no se definió fecha de envío:
                    # si existía una programación previa activa, se cancela
                    # para reflejar la intención del usuario de retirarla.
                    if not notificacion.envio_ejecutado and (notificacion.tarea_q_id or notificacion.fecha_envio_programado):
                        _cancelar_tarea_programada(notificacion)
                        contador_canceladas += 1

        mensaje = f'Proceso completado: {contador_creadas} creadas, {contador_actualizadas} actualizadas'
        if contador_omitidas > 0:
            mensaje += f', {contador_omitidas} omitidas'
        if contador_programadas > 0:
            mensaje += f', {contador_programadas} programadas'
        if contador_canceladas > 0:
            mensaje += f', {contador_canceladas} programaciones canceladas'

        messages.success(request, mensaje)

        # Avisos consolidados: un único mensaje por categoría, sin importar
        # cuántos registros individuales estén involucrados.
        if avisos_sin_correo_para:
            messages.warning(
                request,
                f'No se programó el envío automático en {len(avisos_sin_correo_para)} '
                f'registro(s) por falta de correos "Para": '
                f'{", ".join(avisos_sin_correo_para)}.'
            )

        if avisos_fecha_no_programada:
            messages.warning(
                request,
                f'No se pudo programar el envío en {len(avisos_fecha_no_programada)} '
                f'registro(s): {", ".join(avisos_fecha_no_programada)}.'
            )

    except Exception as exc:
        logger.error(f"Error en guardar_notificaciones_unidad: {exc}")
        messages.error(request, f'Error al guardar las notificaciones: {exc}')

    return redirect('gestion_notificaciones_unidad', ccpp_id=ccpp_id, unidad_id=unidad_id)



@login_required
@validar_permisos
@require_POST
def eliminar_notificacion_unidad(request, notificacion_id):
    """
    Elimina una notificación específica desde la vista de unidad.
    """
    try:
        with transaction.atomic():
            notificacion = get_object_or_404(
                tbl_Notificacion, 
                id_notificacion=notificacion_id
            )
            
            # Cancelar tareas programadas
            _cancelar_tarea_programada(notificacion)
            
            ccpp_id = notificacion.id_ccpp_id
            unidad_id = notificacion.id_unidad_id
            
            # Eliminar documentos asociados
            for doc in tbl_NotificacionDocumento.objects.filter(id_notificacion=notificacion):
                doc.delete()
            
            notificacion.delete()
        
        return JsonResponse({'success': True})
    except Exception as exc:
        logger.error(f"Error al eliminar notificación {notificacion_id}: {exc}")
        return JsonResponse({
            'success': False,
            'error': 'No se pudo eliminar la notificación.',
        })
    



  