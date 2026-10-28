# appFicha/views.py


import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, DatabaseError
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from appAdministrador.models import tbl_Unidad, tbl_Ficha, tbl_FichaControl, tbl_inspeccion, tbl_CCPP
from datetime import date
from appAdministrador.models import ConfiguracionFicha

logger = logging.getLogger(__name__)


@login_required
def vista_panel_fichas(request, unidad_id, ccpp_id, origen):
    """
    Vista para mostrar el panel de fichas de una unidad.
    ccpp_id es ahora un parámetro obligatorio en la URL.
    """
    try:
        # Obtener la unidad y el CCPP
        unidad = get_object_or_404(tbl_Unidad, id_unidad=unidad_id)
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)

    except Exception as e:
        logger.error(f"Error al obtener unidad {unidad_id} o CCPP {ccpp_id}: {str(e)}")
        messages.error(request, "No se pudo cargar la información solicitada.")
        return redirect("panel_principal")

    try:
        # Obtener fichas de la unidad con conteo de controles
        fichas = (
            tbl_Ficha.objects.filter(doc_unidad=unidad.doc)
            .annotate(num_controles=Count("fichacontrol"))
            .order_by("-fecha_creacion")
        )

    except DatabaseError as db_err:
        logger.error(f"Error de base de datos en unidad {unidad_id}: {str(db_err)}")
        fichas = []
        messages.error(request, "Error de base de datos al cargar las fichas.")
    except Exception as e:
        logger.error(f"Error inesperado en unidad {unidad_id}: {str(e)}")
        fichas = []
        messages.error(request, "Ocurrió un error inesperado al cargar las fichas.")

    configuracion = ConfiguracionFicha.obtener_instancia()

    contexto = {
        'config_ficha': configuracion,
        "fichas": fichas,
        "unidad": unidad,
        "ccpp": ccpp,
        "origen":origen
    }

    return render(request, "panel_fichas.html", contexto)







from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


import logging
from datetime import date, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction


logger = logging.getLogger(__name__)


def gestionar_ficha(request, ccpp_id, unidad_id=None, ficha_id=None, origen=None):
    """
    Gestiona la creación y edición de fichas.
    Garantiza que el código de cada control sea inmutable una vez asignado.
    """
    ficha = None
    edicion = False
    unidad = None
    errores = {}

    # 1. Obtención de objetos base obligatorios
    ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)

    try:
        if ficha_id:
            ficha = get_object_or_404(tbl_Ficha, id=ficha_id)
            unidad = ficha.doc_unidad
            edicion = True
        elif unidad_id:
            unidad = get_object_or_404(tbl_Unidad, id_unidad=unidad_id)
        else:
            messages.error(request, "Referencia de unidad o ficha no encontrada.")
            return redirect("panel_principal")

    except Exception as e:
        logger.error(f"Error al cargar datos base: {str(e)}")
        messages.error(request, "Error al cargar los datos requeridos.")
        return redirect("panel_principal")

    inspecciones = tbl_inspeccion.objects.all().order_by("codigo_inspeccion")

    valores_formulario = {
        "titulo": "",
        "precaucion": "",
        "prescripcion": "",
        "prohibicion": "",
        "fecha_creacion": "",
    }
    if not ficha:
        valores_formulario["fecha_creacion"] = date.today().strftime('%Y-%m-%d')

    if request.method == "POST":
        # Captura de campos de texto
        for campo in ["titulo", "precaucion", "prescripcion", "prohibicion"]:
            valores_formulario[campo] = request.POST.get(campo, "").strip()

        # Captura de fecha
        valores_formulario["fecha_creacion"] = request.POST.get("fecha", "").strip()

        # --- VALIDACIONES DE LA FICHA ---
        if not valores_formulario["titulo"]:
            errores["titulo"] = "El título es requerido."
        else:
            queryset_duplicados = tbl_Ficha.objects.filter(
                titulo=valores_formulario["titulo"],
                doc_unidad=unidad
            )
            if edicion:
                queryset_duplicados = queryset_duplicados.exclude(id=ficha.id)
            if queryset_duplicados.exists():
                errores["titulo"] = "Ya existe una ficha con ese título en esta unidad."

        if not valores_formulario["fecha_creacion"]:
            errores["fecha"] = "La fecha es requerida."
        else:
            try:
                datetime.strptime(valores_formulario["fecha_creacion"], '%Y-%m-%d')
            except ValueError:
                errores["fecha"] = "Formato de fecha inválido. Use AAAA-MM-DD."

        # Validación de archivos
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
        for campo_archivo in ['logo', 'foto']:
            archivo_subido = request.FILES.get(campo_archivo)
            if archivo_subido and archivo_subido.size > MAX_FILE_SIZE:
                errores[campo_archivo] = "El archivo excede el tamaño máximo de 5MB"

        # --- PROCESAR CONTROLES DESDE EL FORMULARIO ---
        indices_controles = sorted(set(
            clave.split('-')[1] for clave in request.POST.keys()
            if clave.startswith('controles-') and '-periodo' in clave
        ))

        controles_data = []
        for indice in indices_controles:
            try:
                inspeccion_id = request.POST.get(f'controles-{indice}-inspeccion')
                objeto_inspeccion = None
                if inspeccion_id:
                    try:
                        objeto_inspeccion = tbl_inspeccion.objects.get(id=inspeccion_id)
                    except tbl_inspeccion.DoesNotExist:
                        pass

                controles_data.append({
                    'id_control': request.POST.get(f'controles-{indice}-id', '').strip(),
                    'periodo': request.POST.get(f'controles-{indice}-periodo', '').strip(),
                    'premisa': request.POST.get(f'controles-{indice}-premisa', '').strip(),
                    'inspeccion': objeto_inspeccion,
                    'control': request.POST.get(f'controles-{indice}-control', '').strip(),
                    'ejecutado': request.POST.get(f'controles-{indice}-ejecutado') == 'on',
                    'opacar': request.POST.get(f'controles-{indice}-opacar') == 'on',
                    'ocultar': request.POST.get(f'controles-{indice}-ocultar') == 'on',
                })

            except Exception as e:
                logger.warning(f"Error procesando control {indice}: {str(e)}")

        # --- GUARDADO TRANSACCIONAL ---
        if not errores:
            try:
                with transaction.atomic():
                    if edicion:
                        for campo, valor in valores_formulario.items():
                            setattr(ficha, campo, valor)
                    else:
                        ficha = tbl_Ficha.objects.create(
                            doc_unidad=unidad,
                            **valores_formulario
                        )

                    # Manejo de archivos
                    for campo_archivo in ['logo', 'foto']:
                        if request.POST.get(f"eliminar_{campo_archivo}") == "true":
                            if edicion and getattr(ficha, campo_archivo):
                                getattr(ficha, campo_archivo).delete(save=False)
                                setattr(ficha, campo_archivo, None)

                        archivo_subido = request.FILES.get(campo_archivo)
                        if archivo_subido:
                            if getattr(ficha, campo_archivo):
                                getattr(ficha, campo_archivo).delete(save=False)
                            setattr(ficha, campo_archivo, archivo_subido)

                    ficha.save()

                    # Guardar / Actualizar controles
                    ids_actualizados = []
                    for datos in controles_data:
                        id_control = datos['id_control']

                        if id_control and str(id_control).isdigit():
                            # EDITAR EXISTENTE: Se actualizan campos descriptivos,
                            # pero el método save() del modelo impedirá modificar el codigo_control original.
                            control_obj = tbl_FichaControl.objects.filter(
                                id_ficha_control=int(id_control),
                                id_ficha=ficha
                            ).first()

                            if control_obj:
                                control_obj.id_inspeccion = datos['inspeccion']
                                control_obj.periodo = datos['periodo']
                                control_obj.premisa = datos['premisa']
                                control_obj.control = datos['control']
                                control_obj.ejecutado = datos['ejecutado']
                                control_obj.opacar = datos['opacar']
                                control_obj.ocultar = datos['ocultar']
                                control_obj.save()
                            else:
                                control_obj = tbl_FichaControl.objects.create(
                                    id_ficha=ficha,
                                    id_inspeccion=datos['inspeccion'],
                                    periodo=datos['periodo'],
                                    premisa=datos['premisa'],
                                    control=datos['control'],
                                    ejecutado=datos['ejecutado'],
                                    opacar=datos['opacar'],
                                    ocultar=datos['ocultar']
                                )
                        else:
                            # CREAR NUEVO: El método save() le asignará el siguiente código correlativo disponible.
                            control_obj = tbl_FichaControl.objects.create(
                                id_ficha=ficha,
                                id_inspeccion=datos['inspeccion'],
                                periodo=datos['periodo'],
                                premisa=datos['premisa'],
                                control=datos['control'],
                                ejecutado=datos['ejecutado'],
                                opacar=datos['opacar'],
                                ocultar=datos['ocultar']
                            )

                        ids_actualizados.append(control_obj.id_ficha_control)

                    # Eliminar únicamente los controles que fueron removidos en la interfaz
                    tbl_FichaControl.objects.filter(id_ficha=ficha).exclude(id_ficha_control__in=ids_actualizados).delete()

                    messages.success(request, "Ficha guardada correctamente.")
                    return redirect("editar_ficha", ccpp_id=ccpp_id, ficha_id=ficha.id, origen=origen)

            except Exception as e:
                logger.error(f"Error al guardar: {str(e)}")
                messages.error(request, "Ocurrió un error al guardar los datos.")

    # Preparación de datos para renderizado
    if not errores and ficha:
        for campo in valores_formulario.keys():
            valores_formulario[campo] = getattr(ficha, campo, "")

    if valores_formulario["fecha_creacion"] and not isinstance(valores_formulario["fecha_creacion"], str):
        valores_formulario["fecha_creacion"] = valores_formulario["fecha_creacion"].strftime('%Y-%m-%d')

    controles_db = tbl_FichaControl.objects.filter(id_ficha=ficha) if ficha else []

    contexto = {
        "unidad": unidad,
        "ficha": ficha,
        "edicion": edicion,
        "ccpp": ccpp,
        "controles": controles_db,
        "inspecciones": inspecciones,
        "origen": origen,
        "errores": errores,
        **{f"{campo}_value": valor for campo, valor in valores_formulario.items()},
    }

    return render(request, "formulario_ficha.html", contexto)





@login_required
def eliminar_ficha(request, ficha_id, ccpp_id, origen):
    """
    Elimina una ficha y todos sus controles asociados.

    Args:
        request: Objeto HttpRequest
        ficha_id (int): ID de la ficha a eliminar
        ccpp_id (int): ID del CCPP (Obligatorio)
        origen (str): Origen de la petición

    Returns:
        Redirección a la vista panel_fichas con ccpp_id
    """
    # 1. Ya no lo buscamos en request.GET porque viene como argumento de la URL
    try:
        ficha = get_object_or_404(tbl_Ficha, id=ficha_id)
        id_unidad = ficha.doc_unidad.id_unidad

        # Validamos que el CCPP existe (si es necesario para la integridad)
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)

    except Exception as e:
        logger.error(f"Error al validar datos para eliminación {ficha_id}: {str(e)}")
        messages.error(request, "No se pudo cargar la información necesaria.")
        return redirect("panel_principal")

    if request.method == "POST":
        try:
            with transaction.atomic():
                nombre_ficha = ficha.titulo
                ficha.delete()

                messages.success(
                    request,
                    f"La ficha '{nombre_ficha}' y sus controles han sido eliminados correctamente."
                )

                # Redirección obligatoria con ccpp_id
                return redirect("panel_fichas", unidad_id=id_unidad, ccpp_id=ccpp_id, origen=origen)

        except DatabaseError as db_err:
            logger.error(f"Error de base de datos al eliminar ficha {ficha_id}: {str(db_err)}")
            messages.error(request, "Error de base de datos al eliminar la ficha.")
        except Exception as error:
            logger.error(f"Error inesperado al eliminar ficha {ficha_id}: {str(error)}")
            messages.error(request, "Ocurrió un error inesperado al eliminar la ficha.")

    # Redirección por defecto (para GET o errores de proceso) siempre con ccpp_id
    return redirect("panel_fichas", unidad_id=id_unidad, ccpp_id=ccpp_id, origen=origen)



# ========================== CREAR DOCUMENTO ==========================

import io
import os
from django.conf import settings
from django.http import FileResponse
from django.contrib.staticfiles import finders
from django.core.exceptions import ObjectDoesNotExist

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, Image, KeepTogether, LongTable
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------------------------------------------------------------------
# CONSTANTES DE LAYOUT
# letter height = 279.4 mm  |  topMargin=35mm  bottomMargin=15mm  → ~229 mm útiles
# Usamos el 82 % como límite seguro por fila para absorber padding y cabecera.
# ---------------------------------------------------------------------------
ALTURA_PAGINA_UTIL_MM = (letter[1] / mm) - 35 - 15   # ≈ 229 mm
ALTURA_MAX_FILA_MM    = ALTURA_PAGINA_UTIL_MM * 0.82  # ≈ 188 mm


# ---------------------------------------------------------------------------
# FUNCIONES DE APOYO
# ---------------------------------------------------------------------------

def formatear_documento_seis_digitos(valor):
    try:
        solo_numeros = "".join(filter(str.isdigit, str(valor)))
        cadena_rellena = solo_numeros.zfill(6)
        return f"{cadena_rellena[0:2]} {cadena_rellena[2:4]} {cadena_rellena[4:6]}"
    except (ValueError, TypeError):
        return "00 00 00"


def obtener_nombre_tecnico_cabecera(id_ccpp):
    try:
        registro_ccpp = tbl_CCPP.objects.get(id_ccpp=id_ccpp)
        contenido_tecnico = registro_ccpp.tecnico_cabecera
        return contenido_tecnico.splitlines()[0] if contenido_tecnico else "No especificado"
    except (ObjectDoesNotExist, Exception):
        return "No disponible"


def generar_encabezado_seccion(texto_titulo, estilo_parrafo, color_linea):
    tabla_titulo = Table(
        [[Paragraph(f"<b>{texto_titulo}</b>", estilo_parrafo)]],
        colWidths=[200 * mm]
    )
    tabla_titulo.setStyle(TableStyle([
        ('LINEBELOW',     (0, 0), (-1, 0), 2, color_linea),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return tabla_titulo


# ---------------------------------------------------------------------------
# HELPER: estima la altura (mm) de un Paragraph dentro de un ancho dado.
# Usa wrap() de ReportLab, no necesita canvas real.
# ---------------------------------------------------------------------------
def _altura_parrafo_mm(parrafo, ancho_mm):
    _, h_pt = parrafo.wrap(ancho_mm * mm, 10_000)
    return h_pt / mm


# ---------------------------------------------------------------------------
# HELPER: divide texto_raw en fragmentos que no superen altura_max_mm dentro
# de la celda de descripción (140 mm de ancho por defecto).
# Devuelve lista de strings HTML listos para Paragraph.
# ---------------------------------------------------------------------------
def _fragmentar_texto_control(texto_raw, prefijo_html, estilo_parrafo,
                               ancho_desc_mm=140, altura_max_mm=None):
    if altura_max_mm is None:
        altura_max_mm = ALTURA_MAX_FILA_MM

    lineas = texto_raw.splitlines()

    fragmentos    = []
    bloque_actual = []

    def _html_bloque(lineas_bloque, es_primero):
        contenido = "<br/>".join(lineas_bloque)
        return f"{prefijo_html} {contenido}" if es_primero else contenido

    def _altura_bloque(lineas_bloque, es_primero):
        p = Paragraph(_html_bloque(lineas_bloque, es_primero), estilo_parrafo)
        return _altura_parrafo_mm(p, ancho_desc_mm)

    es_primer_fragmento = True

    for linea in lineas:
        bloque_prueba = bloque_actual + [linea]

        if _altura_bloque(bloque_prueba, es_primer_fragmento) <= altura_max_mm:
            bloque_actual = bloque_prueba
        else:
            # Guardar lo acumulado antes de procesar esta línea
            if bloque_actual:
                fragmentos.append(_html_bloque(bloque_actual, es_primer_fragmento))
                es_primer_fragmento = False
                bloque_actual = []

            # Intentar insertar la línea palabra a palabra
            palabras     = linea.split(" ")
            palabras_acc = []

            for palabra in palabras:
                prueba = palabras_acc + [palabra]
                bloque_test = [" ".join(prueba)]

                if _altura_bloque(bloque_test, es_primer_fragmento) <= altura_max_mm:
                    palabras_acc = prueba
                else:
                    if palabras_acc:
                        fragmentos.append(
                            _html_bloque([" ".join(palabras_acc)], es_primer_fragmento)
                        )
                        es_primer_fragmento = False
                        palabras_acc = [palabra]
                    else:
                        # Palabra sola que ya supera el límite (caso extremo)
                        fragmentos.append(
                            _html_bloque([palabra], es_primer_fragmento)
                        )
                        es_primer_fragmento = False
                        palabras_acc = []

            if palabras_acc:
                bloque_actual = [" ".join(palabras_acc)]

    if bloque_actual:
        fragmentos.append(_html_bloque(bloque_actual, es_primer_fragmento))

    return fragmentos if fragmentos else [f"{prefijo_html} "]


# ---------------------------------------------------------------------------
# HELPER: construye 1..N filas de tabla para un control, dividiendo el texto
# en sub-filas cuando es necesario para evitar el desbordamiento de página.
# ---------------------------------------------------------------------------
def _construir_filas_control(control, estilo_texto_cuerpo, estilo_titulo_principal,
                              gris_opaco_deshabilitado, verde_exito, rojo_alerta):
    color_txt = gris_opaco_deshabilitado if control.opacar else "#374151"

    if control.opacar:
        color_prem = gris_opaco_deshabilitado
    else:
        p_u        = control.premisa.upper() if control.premisa else ""
        color_prem = (
            verde_exito if ("RECOMENDADO" in p_u or "RECOMENDABLE" in p_u)
            else rojo_alerta
        )

    col_periodo_html = (
        f'<font color="{color_txt}">{control.periodo}</font><br/>'
        f'<font color="{color_prem}" size="8"><b>{control.premisa or ""}</b></font>'
    )

    insp      = control.id_inspeccion
    color_cod = (
        gris_opaco_deshabilitado if control.opacar
        else (insp.color_inspeccion if insp and insp.color_inspeccion else "#374151")
    )
    color_nom = gris_opaco_deshabilitado if control.opacar else "#374151"

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
        textColor=colors.HexColor(color_txt)
    )
    estilo_ok = ParagraphStyle(
        'CS', parent=estilo_titulo_principal,
        fontSize=11,
        textColor=colors.HexColor(color_txt)
    )

    texto_raw  = control.control or ""
    fragmentos = _fragmentar_texto_control(
        texto_raw,
        prefijo_html,
        estilo_fila,
        ancho_desc_mm=140,
    )

    filas = []
    for idx, frag_html in enumerate(fragmentos):
        es_primera = (idx == 0)

        celda_periodo = (
            Paragraph(col_periodo_html, estilo_fila)
            if es_primera else Paragraph("", estilo_fila)
        )
        celda_desc = Paragraph(
            f'<font color="{color_txt}">{frag_html}</font>',
            estilo_fila
        )
        celda_ok = (
            Paragraph(f"<b>{'✓' if control.ejecutado else ''}</b>", estilo_ok)
            if es_primera else Paragraph("", estilo_ok)
        )

        filas.append([celda_periodo, celda_desc, celda_ok])

    return filas


# ---------------------------------------------------------------------------
# VISTA DE EXPORTACIÓN
# ---------------------------------------------------------------------------

def exportar_ficha_pdf(request, ficha_id, ccpp_id, descargar_directo='false'):
    debe_descargar = str(descargar_directo).lower() == "true"

    # Fuentes
    try:
        ruta_fuente_regular = finders.find('fonts/Poppins-Regular.ttf') or \
                              os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Regular.ttf')
        ruta_fuente_negrita = finders.find('fonts/Poppins-Bold.ttf') or \
                              os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Bold.ttf')

        pdfmetrics.registerFont(TTFont('Poppins',      ruta_fuente_regular))
        pdfmetrics.registerFont(TTFont('Poppins-Bold', ruta_fuente_negrita))
        fuente_reg, fuente_bold = 'Poppins', 'Poppins-Bold'
    except Exception:
        fuente_reg, fuente_bold = 'Helvetica', 'Helvetica-Bold'

    # Datos
    try:
        objeto_ficha       = tbl_Ficha.objects.get(id=ficha_id)
        lista_controles    = tbl_FichaControl.objects.filter(id_ficha=objeto_ficha)
        nombre_tecnico     = obtener_nombre_tecnico_cabecera(ccpp_id)
        titulo_archivo_pdf = objeto_ficha.titulo if objeto_ficha.titulo else f"Ficha_{objeto_ficha.id}"
    except tbl_Ficha.DoesNotExist:
        return FileResponse(io.BytesIO(b"Error: La ficha solicitada no existe."), content_type='text/plain')
    except Exception as e:
        return FileResponse(io.BytesIO(f"Error inesperado: {str(e)}".encode()), content_type='text/plain')

    # Estilos visuales
    gris_oscuro              = colors.HexColor("#374151")
    gris_suave               = colors.HexColor("#d1d5db")
    gris_opaco_deshabilitado = "#e5e7eb"
    rojo_enfasis             = colors.HexColor("#b91c1c")
    fondo_naranja_claro      = colors.HexColor("#FFE9D7")
    verde_exito              = "#166534"
    rojo_alerta              = "#991b1b"

    estilo_titulo_principal = ParagraphStyle('T1', fontSize=13,  fontName=fuente_bold, alignment=TA_CENTER)
    estilo_subtitulo_rojo   = ParagraphStyle('T2', fontSize=16,  fontName=fuente_bold, textColor=rojo_enfasis, alignment=TA_CENTER, leading=18)
    estilo_capitulo         = ParagraphStyle('T3', fontSize=10,  fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_unidad           = ParagraphStyle('T4', fontSize=8,   fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_titulo_seccion   = ParagraphStyle('S1', fontSize=10,  fontName=fuente_bold, textColor=colors.black)
    estilo_texto_cuerpo     = ParagraphStyle('C1', fontSize=9.5, fontName=fuente_reg,  leading=12, textColor=gris_oscuro)
    estilo_etiqueta_info    = ParagraphStyle('L1', fontSize=8.5, fontName=fuente_reg,  textColor=gris_oscuro)
    estilo_firma_pie        = ParagraphStyle('F1', fontSize=7.5, fontName=fuente_reg,  textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)

    # Cabecera repetida en cada página
    def dibujar_elementos_estaticos(canvas_obj, documento_obj):
        canvas_obj.saveState()
        try:
            ruta_logo_p = finders.find('img/logo.png') or \
                          os.path.join(settings.BASE_DIR, 'static/img/logo.png')
            imagen_izq  = Image(ruta_logo_p, width=35*mm, height=13*mm) \
                          if os.path.exists(ruta_logo_p) else ""
            imagen_der  = ""
            if objeto_ficha.logo and os.path.exists(objeto_ficha.logo.path):
                imagen_der = Image(objeto_ficha.logo.path, width=15*mm, height=15*mm)
        except Exception:
            imagen_izq = imagen_der = ""

        datos_u    = objeto_ficha.doc_unidad
        codigo_doc = formatear_documento_seis_digitos(datos_u.doc) if datos_u else "00 00 00"

        bloque_centro = [
            Paragraph("CONTROL LIBRO DEL EDIFICIO", estilo_titulo_principal),
            Paragraph(codigo_doc, estilo_subtitulo_rojo),
            Paragraph(datos_u.capitulo if datos_u else "", estilo_capitulo),
            Paragraph(datos_u.unidad   if datos_u else "", estilo_unidad),
        ]

        t_header = Table(
            [[imagen_izq, bloque_centro, imagen_der]],
            colWidths=[30*mm, 140*mm, 30*mm]
        )
        t_header.setStyle(TableStyle([
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',        (0, 0), (0, 0),   'LEFT'),
            ('ALIGN',        (2, 0), (2, 0),   'RIGHT'),
            ('LINEBELOW',    (0, 0), (-1, 0),   2, colors.black),
            ('LEFTPADDING',  (0, 0), (-1, -1),  0),
            ('RIGHTPADDING', (0, 0), (-1, -1),  0),
            ('BOTTOMPADDING',(0, 0), (-1, -1),  2*mm),
        ]))

        t_header.wrapOn(canvas_obj, documento_obj.width, documento_obj.topMargin)
        y_base = documento_obj.height + documento_obj.topMargin - 16*mm
        t_header.drawOn(canvas_obj, documento_obj.leftMargin, y_base)

        fecha_formateada = (
            objeto_ficha.fecha_creacion.strftime('%d/%m/%Y')
            if objeto_ficha.fecha_creacion else "No especificada"
        )

        info_meta = [[
            Paragraph(f"<b>Técnico Cabecera:</b> {nombre_tecnico}", estilo_etiqueta_info),
            Paragraph(
                f"<b>Fecha:</b> {fecha_formateada}",
                ParagraphStyle('FD', parent=estilo_etiqueta_info, alignment=TA_RIGHT)
            ),
        ]]

        t_meta = Table(info_meta, colWidths=[120*mm, 80*mm])
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
        title=titulo_archivo_pdf
    )

    elementos_historia = []

    # -----------------------------------------------------------------------
    # Tabla de controles con fragmentación automática de texto largo
    # -----------------------------------------------------------------------
    elementos_historia.append(generar_encabezado_seccion("✓ CONTROLES", estilo_titulo_seccion, gris_suave))
    elementos_historia.append(Spacer(1, 2*mm))

    filas_controles = [[
        Paragraph('<b>PERIODO</b>',    estilo_texto_cuerpo),
        Paragraph('<b>INSPECCIÓN</b>', estilo_texto_cuerpo),
        Paragraph('<b>OK</b>',         estilo_texto_cuerpo),
    ]]

    for control in lista_controles:
        if not control.ocultar:
            nuevas_filas = _construir_filas_control(
                control,
                estilo_texto_cuerpo,
                estilo_titulo_principal,
                gris_opaco_deshabilitado,
                verde_exito,
                rojo_alerta,
            )
            filas_controles.extend(nuevas_filas)

    if len(filas_controles) > 1:
        # LongTable con splitByRow=1 gestiona los saltos de página entre filas
        t_controles = LongTable(
            filas_controles,
            colWidths=[40*mm, 140*mm, 20*mm],
            repeatRows=1,
            splitByRow=1,
        )
        t_controles.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0),  fondo_naranja_claro),
            ('GRID',         (0, 0), (-1, 0),  0.5, gris_suave),
            ('LINEBELOW',    (0, 1), (-1, -2), 0.3, gris_suave),
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',        (2, 0), (2, -1),  'CENTER'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        elementos_historia.append(t_controles)
    else:
        elementos_historia.append(Paragraph("No hay controles registrados.", estilo_texto_cuerpo))

    # Secciones de texto enriquecido
    for tit, cont in [
        ("✓ PRECAUCIONES",   objeto_ficha.precaucion),
        ("✓ PRESCRIPCIONES", objeto_ficha.prescripcion),
        ("✓ PROHIBICIONES",  objeto_ficha.prohibicion),
    ]:
        if cont:
            elementos_historia.append(KeepTogether([
                Spacer(1, 4*mm),
                generar_encabezado_seccion(tit, estilo_titulo_seccion, gris_suave),
                Spacer(1, 1*mm),
                Paragraph(cont.replace('\n', '<br/>'), estilo_texto_cuerpo),
            ]))

    # Bloque de firmas
    elementos_historia.append(Spacer(1, 6*mm))
    f_data = [
        [
            Paragraph('<b>FECHA INSPECCIÓN</b>', estilo_texto_cuerpo),
            Paragraph('<b>CONTROL</b>',          estilo_texto_cuerpo),
            Paragraph('<b>OBSERVACIONES</b>',    estilo_texto_cuerpo),
        ],
        ['', Paragraph('Firma', estilo_firma_pie), ''],
    ]
    t_firma = Table(f_data, colWidths=[50*mm, 50*mm, 100*mm], rowHeights=[None, 24*mm])
    t_firma.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  fondo_naranja_claro),
        ('GRID',          (0, 0), (-1, -1), 0.5, gris_oscuro),
        ('ALIGN',         (1, 1), (1, 1),   'CENTER'),
        ('VALIGN',        (1, 1), (1, 1),   'BOTTOM'),
        ('BOTTOMPADDING', (1, 1), (1, 1),   1.5*mm),
        ('VALIGN',        (0, 0), (-1, 0),  'MIDDLE'),
    ]))
    elementos_historia.append(KeepTogether([t_firma]))

    # Anexos (imagen)
    if objeto_ficha.foto:
        try:
            if os.path.exists(objeto_ficha.foto.path):
                elementos_historia.append(KeepTogether([
                    Spacer(1, 5*mm),
                    generar_encabezado_seccion("✓ ANEXOS", estilo_titulo_seccion, gris_suave),
                    Spacer(1, 3*mm),
                    Image(objeto_ficha.foto.path, width=195*mm, height=80*mm, kind='proportional'),
                ]))
        except (ValueError, Exception):
            pass

    doc_pdf.build(
        elementos_historia,
        onFirstPage=dibujar_elementos_estaticos,
        onLaterPages=dibujar_elementos_estaticos,
    )
    buffer_memoria.seek(0)

    return FileResponse(
        buffer_memoria,
        as_attachment=debe_descargar,
        filename=f'{titulo_archivo_pdf}.pdf',
    )









import logging
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_POST

# Configuración del registro de errores
logger = logging.getLogger(__name__)

@require_POST
def guardar_configuracion_ficha(request):
    """
    Vista que procesa el envío del formulario POST del modal.
    """
    try:
        configuracion = ConfiguracionFicha.obtener_instancia()
        nuevo_valor = request.POST.get('campo_1', '')

        configuracion.campo_1 = nuevo_valor.strip()
        configuracion.save()

        messages.success(request, "Configuración guardada correctamente.")

    except Exception as error:
        logger.error(f"Error al guardar la configuración: {error}")
        messages.error(request, "Ocurrió un error al intentar guardar los cambios.")

    pagina_origen = request.META.get('HTTP_REFERER', '/')
    return redirect(pagina_origen)