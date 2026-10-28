"""
Tareas asíncronas de appNotificacion ejecutadas por django-q2.
"""

import logging

logger = logging.getLogger(__name__)


def _generar_pdf_ficha(ficha_id: int, ccpp_id: int, id_control: int = None) -> bytes | None:
    """
    Genera el PDF de una ficha y retorna los bytes en memoria.
    Separado de la vista HTTP para poder invocarse desde tareas asíncronas
    sin depender del objeto request.

    id_control (opcional): si se indica, el PDF incluye ÚNICAMENTE ese
    control en vez de todos los controles de la ficha.
    """
    try:
        from appNotificacion.views.noti_periodo import exportar_ficha_pdf
        return exportar_ficha_pdf(
            None, ficha_id, ccpp_id, return_buffer=True, id_control=id_control,
        )
    except Exception as exc:
        logger.warning(
            "No se pudo generar PDF ficha_id=%s ccpp_id=%s id_control=%s: %s",
            ficha_id, ccpp_id, id_control, exc
        )
        return None


def _reclamar_envio(notificacion_id: int):
    """
    Bloquea la fila de la notificación y la marca como enviada de forma
    atómica ANTES de contactar al servidor SMTP.

    Esto evita que dos ejecuciones concurrentes de la misma tarea (por
    ejemplo, tras un reinicio del qcluster de PythonAnywhere) envíen el
    mismo correo dos veces: la segunda ejecución encontrará
    `envio_ejecutado=True` y se detendrá antes de enviar nada.

    Devuelve una tupla (notificacion, to_list, cc_list, bcc_list) o
    (None, resultado_dict) si no corresponde continuar con el envío.
    """
    from django.db import transaction
    from django.utils import timezone
    from appAdministrador.models import tbl_Notificacion

    def _lista(campo: str) -> list:
        return [c.strip() for c in campo.split(',') if c.strip()] if campo else []

    with transaction.atomic():
        try:
            notificacion = tbl_Notificacion.objects.select_for_update().select_related(
                'id_ccpp', 'id_unidad', 'id_ficha_control', 'id_ficha_control__id_ficha'
            ).get(id_notificacion=notificacion_id)
        except tbl_Notificacion.DoesNotExist:
            logger.error(
                "enviar_correo_notificacion: notificacion_id=%s no existe.",
                notificacion_id
            )
            return None, {'error': f'Notificación {notificacion_id} no encontrada'}

        if notificacion.envio_ejecutado:
            logger.info(
                "enviar_correo_notificacion: notificacion_id=%s ya enviada. Se omite.",
                notificacion_id
            )
            return None, {'omitido': True, 'razon': 'ya enviado'}

        to_list = _lista(notificacion.para)
        cc_list = _lista(notificacion.cc)
        bcc_list = _lista(notificacion.cco)

        if not to_list:
            logger.warning(
                "enviar_correo_notificacion: notificacion_id=%s sin destinatarios. Se omite.",
                notificacion_id
            )
            return None, {'omitido': True, 'razon': 'sin destinatarios'}

        # Reclamo atómico: se marca como enviada dentro del mismo bloqueo
        # de fila, antes de intentar el envío real por SMTP.
        notificacion.envio_ejecutado = True
        notificacion.fecha_envio_programado = timezone.now()
        notificacion.save(update_fields=['envio_ejecutado', 'fecha_envio_programado'])

    return notificacion, {'to_list': to_list, 'cc_list': cc_list, 'bcc_list': bcc_list}


def _liberar_reclamo(notificacion_id: int) -> None:
    """
    Revierte el reclamo de envío (`envio_ejecutado=False`) cuando el envío
    real por SMTP falla, para permitir que la tarea se pueda reintentar.
    """
    from appAdministrador.models import tbl_Notificacion
    tbl_Notificacion.objects.filter(id_notificacion=notificacion_id).update(
        envio_ejecutado=False
    )


def enviar_correo_notificacion(notificacion_id: int) -> dict:
    """
    Envía el correo de una notificación programada.

    Pasos:
        1. Bloquea la notificación, valida que no se haya enviado ya y que
           tenga destinatarios, y la marca como enviada (reclamo atómico).
        2. Genera el PDF de la ficha (completa o filtrada por control)
           según lo que tenga asignada la unidad-ccpp.
        3. Envía el correo usando ConfiguracionEmail.
        4. Si el envío SMTP falla, revierte el reclamo para permitir un
           reintento posterior.

    Retorna dict con resultado para que django-q2 lo registre en su log.
    """
    from django.core.mail import EmailMessage, get_connection
    from appAdministrador.models import tbl_Correo, ConfiguracionEmail
    from appNotificacion.views.noti_periodo import reemplazar_etiquetas, _resolver_adjunto_ficha

    notificacion, datos = _reclamar_envio(notificacion_id)
    if notificacion is None:
        return datos

    to_list = datos['to_list']
    cc_list = datos['cc_list']
    bcc_list = datos['bcc_list']

    config = ConfiguracionEmail.objects.first()
    if not config:
        _liberar_reclamo(notificacion_id)
        logger.error(
            "enviar_correo_notificacion: sin ConfiguracionEmail. notificacion_id=%s",
            notificacion_id
        )
        return {'error': 'No hay ConfiguracionEmail configurada.'}

    # Asunto y cuerpo desde plantilla existente
    try:
        plantilla = tbl_Correo.objects.first()
        ccpp = notificacion.id_ccpp
        unidad = notificacion.id_unidad
        contexto = {
            'id_ccpp':                 str(ccpp.id_ccpp),
            'nombre_ccpp':             ccpp.nombre,
            'unidad':                  unidad.unidad,
            'descripcion_unidad':      unidad.descripcion,
            'inspeccion':              '',
            'descripcion_inspeccion':  '',
            'notificacion_inspeccion': '',
        }
        asunto = (
            reemplazar_etiquetas(plantilla.asunto, contexto)
            if plantilla else f"Notificación CCPP{ccpp.id_ccpp:03d}"
        )
        cuerpo = reemplazar_etiquetas(plantilla.cuerpo, contexto) if plantilla else ''
    except Exception as exc:
        logger.warning("No se pudo generar asunto/cuerpo desde plantilla: %s", exc)
        asunto = f"Notificación CCPP{notificacion.id_ccpp_id:03d}"
        cuerpo = ''

    # PDF adjunto: control específico, ficha completa, o nada — según lo
    # que tenga asignado la unidad-ccpp y la notificación. Un fallo aquí
    # no cancela el envío, solo se envía sin adjunto.
    adjunto_pdf = None
    id_ficha, id_control = _resolver_adjunto_ficha(
        notificacion.id_ccpp_id, notificacion.id_unidad_id, notificacion,
    )
    if id_ficha:
        pdf_bytes = _generar_pdf_ficha(id_ficha, notificacion.id_ccpp_id, id_control)
        if pdf_bytes:
            nombre_archivo = f"Control_{id_control}.pdf" if id_control else f"Ficha_{id_ficha}.pdf"
            adjunto_pdf = (nombre_archivo, pdf_bytes, 'application/pdf')

    try:
        conexion = get_connection(
            host=config.servidor_smtp,
            port=config.puerto,
            username=config.usuario_email,
            password=config.password_aplicacion,
            use_tls=config.usar_tls,
        )
        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            from_email=config.usuario_email,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            connection=conexion,
        )
        if adjunto_pdf:
            email.attach(*adjunto_pdf)

        email.send()

    except Exception as exc:
        # El envío falló: se libera el reclamo para permitir un reintento
        # (manual, reprogramando, o por una futura ejecución de la tarea).
        _liberar_reclamo(notificacion_id)
        logger.error(
            "Error SMTP notificacion_id=%s: %s",
            notificacion_id, exc
        )
        raise

    logger.info(
        "Correo enviado notificacion_id=%s → %s",
        notificacion_id, to_list
    )
    return {'enviado': True, 'destinatarios': to_list}