from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Prefetch
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.contrib.staticfiles import finders
from django.conf import settings
from io import BytesIO
import datetime
import os
from appAdministrador.models import (
    tbl_CCPP, tbl_Unidad, tbl_Cronograma, tbl_Ficha, 
    tbl_FichaControl, tbl_Notificacion, tbl_inspeccion
)
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph, Spacer, Image, PageBreak, HRFlowable
from reportlab.platypus import Flowable
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY

from reportlab.platypus import Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing, Line
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
import os
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable


def formatear_documento_seis_digitos(valor):
    """
    Formatea el documento a 6 dígitos con espacios: XX XX XX
    """
    try:
        solo_numeros = "".join(filter(str.isdigit, str(valor)))
        cadena_rellena = solo_numeros.zfill(6)
        return f"{cadena_rellena[0:2]} {cadena_rellena[2:4]} {cadena_rellena[4:6]}"
    except (ValueError, TypeError):
        return "00 00 00"


def obtener_nombre_tecnico_cabecera(ccpp):
    """
    Obtiene la primera línea del técnico de cabecera
    """
    try:
        contenido_tecnico = ccpp.tecnico_cabecera
        return contenido_tecnico.splitlines()[0] if contenido_tecnico else "No especificado"
    except Exception:
        return "No disponible"


def generar_encabezado_seccion(texto_titulo, estilo_parrafo, color_linea):
    """
    Genera un encabezado de sección con línea inferior
    """
    tabla_titulo = Table([[Paragraph(texto_titulo, estilo_parrafo)]], colWidths=[200*mm])
    tabla_titulo.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 2, color_linea),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return tabla_titulo



class LineaSeparadora(Flowable):
    def __init__(self, width, color=colors.HexColor("#e5e7eb"), thickness=0.5):
        Flowable.__init__(self)
        self.width = width
        self.color = color
        self.thickness = thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)



def generar_pdf_inspecciones(request):
    """
    Generar PDF con fichas de inspección según parámetros seleccionados
    Optimizado para manejar grandes volúmenes (hasta 700 páginas)
    """
    
    # Obtener parámetros del request
    # Obtener parámetros del request
    id_ccpp = request.GET.get('ccpp')
    anio_relativo = int(request.GET.get('anio', 0)) 
    anio_real = int(request.GET.get('anio_real', datetime.datetime.now().year))
    meses_seleccionados = request.GET.getlist('meses[]')

    try:
        ccpp = tbl_CCPP.objects.get(id_ccpp=id_ccpp)
    except tbl_CCPP.DoesNotExist:
        return JsonResponse({'error': 'CCPP no encontrada'}, status=404)
    
    anio_inicio = ccpp.fecha_entrega.year 
    anio_real = anio_inicio + anio_relativo
    print(ccpp.fecha_entrega.year)
    print(anio_relativo)
    print(anio_real)
    
    # Opciones de configuración del PDF
    incluir_portada = request.GET.get('portada', 'true') == 'true'
    incluir_indice = request.GET.get('indice', 'true') == 'true'
    incluir_anexo = request.GET.get('anexo', 'true') == 'true'
    incluir_firmas_ficha = request.GET.get('firmas_ficha', 'true') == 'true'
    incluir_img_firma = request.GET.get('img_firma', 'true') == 'true'
    incluir_firmas_pie = request.GET.get('firmas_pie', 'true') == 'true'
    incluir_notif_remitente = request.GET.get('notif_remitente', 'false') == 'true'
    incluir_notif_respuesta = request.GET.get('notif_respuesta', 'false') == 'true'
    
    if not id_ccpp or not meses_seleccionados:
        return JsonResponse({'error': 'Faltan parámetros obligatorios'}, status=400)
    

    # Nombres de meses
    nombres_meses = {
        '1': 'enero', '2': 'febrero', '3': 'marzo', '4': 'abril',
        '5': 'mayo', '6': 'junio', '7': 'julio', '8': 'agosto',
        '9': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'
    }
    
    # Obtener cronogramas con inspecciones en los meses seleccionados
    # Optimización: usar select_related y prefetch_related
    cronogramas_query = tbl_Cronograma.objects.filter(
        id_ccpp=ccpp,
        anios=anio_relativo
    ).select_related('id_unidad')
    
    # Filtrar cronogramas que tienen inspección en alguno de los meses seleccionados
    cronogramas_filtrados = []
    for cronograma in cronogramas_query:
        meses_con_inspeccion = []
        for mes_num in meses_seleccionados:
            nombre_mes = nombres_meses[mes_num]
            inspeccion_id = getattr(cronograma, nombre_mes, None)
            if inspeccion_id and inspeccion_id.strip():
                meses_con_inspeccion.append({
                    'numero': mes_num,
                    'nombre': nombre_mes,
                    'inspeccion_id': inspeccion_id
                })
        
        if meses_con_inspeccion:
            cronogramas_filtrados.append({
                'cronograma': cronograma,
                'unidad': cronograma.id_unidad,
                'meses': sorted(meses_con_inspeccion, key=lambda x: int(x['numero']))
            })
    
    if not cronogramas_filtrados:
        return JsonResponse({'error': 'No se encontraron inspecciones para los meses seleccionados'}, status=404)
    
    # Obtener todas las fichas necesarias de una vez (optimización)
    docs_unidades = [item['unidad'].doc for item in cronogramas_filtrados]
    fichas_dict = {}
    fichas_query = tbl_Ficha.objects.filter(
        doc_unidad__doc__in=docs_unidades
    ).prefetch_related(
        Prefetch(
            'fichacontrol',
            queryset=tbl_FichaControl.objects.filter(ocultar=False).select_related('id_inspeccion').order_by('id_ficha_control')
        )
    ).select_related('doc_unidad')
    
    for ficha in fichas_query:
        if ficha.doc_unidad.doc not in fichas_dict:
            fichas_dict[ficha.doc_unidad.doc] = []
        fichas_dict[ficha.doc_unidad.doc].append(ficha)
    
    # Obtener notificaciones si están habilitadas
    notificaciones_dict = {}
    if incluir_notif_remitente or incluir_notif_respuesta:
        notificaciones = tbl_Notificacion.objects.filter(
            id_ccpp=ccpp,
            anio=anio_relativo,
            mes__in=[nombres_meses[m] for m in meses_seleccionados]
        ).select_related('id_unidad', 'id_ficha')
        
        for notif in notificaciones:
            key = f"{notif.id_unidad.doc}_{notif.mes}"
            notificaciones_dict[key] = notif
    
    # Preparar datos para el PDF
    datos_fichas = []
    for item in cronogramas_filtrados:
        unidad = item['unidad']
        fichas_unidad = fichas_dict.get(unidad.doc, [])
        
        for mes_info in item['meses']:
            for ficha in fichas_unidad:
                datos_fichas.append({
                    'unidad': unidad,
                    'ficha': ficha,
                    'mes_numero': mes_info['numero'],
                    'mes_nombre': mes_info['nombre'].capitalize(),
                    'inspeccion_id': mes_info['inspeccion_id'],
                    'notificacion': notificaciones_dict.get(f"{unidad.doc}_{mes_info['nombre']}")
                })
    
    # Ordenar por mes y luego por unidad
    datos_fichas.sort(key=lambda x: (int(x['mes_numero']), x['unidad'].orden))
    
    # Generar PDF
    buffer = BytesIO()
    
    # Cargar fuentes Poppins si están disponibles
    try:
        ruta_fuente_regular = finders.find('fonts/Poppins-Regular.ttf') or \
                             os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Regular.ttf')
        ruta_fuente_negrita = finders.find('fonts/Poppins-Bold.ttf') or \
                             os.path.join(settings.BASE_DIR, 'static/fonts/Poppins-Bold.ttf')
        
        if os.path.exists(ruta_fuente_regular) and os.path.exists(ruta_fuente_negrita):
            pdfmetrics.registerFont(TTFont('Poppins', ruta_fuente_regular))
            pdfmetrics.registerFont(TTFont('Poppins-Bold', ruta_fuente_negrita))
            fuente_reg, fuente_bold = 'Poppins', 'Poppins-Bold'
        else:
            fuente_reg, fuente_bold = 'Helvetica', 'Helvetica-Bold'
    except Exception:
        fuente_reg, fuente_bold = 'Helvetica', 'Helvetica-Bold'
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=8*mm,
        leftMargin=8*mm,
        topMargin=6*mm,
        bottomMargin=15*mm
    )
    
    # Elementos del PDF
    elementos = []
    indice_datos = []  # Para el índice
    pagina_actual = 1
    
    # 1. PORTADA (si está habilitada)
    if incluir_portada:
        elementos_portada = generar_portada(ccpp, anio_real)
        elementos.extend(elementos_portada)
        pagina_actual += len([e for e in elementos_portada if isinstance(e, PageBreak)]) + 1
    
    # 2. ÍNDICE (marcador de posición, se llenará después)
    inicio_indice = len(elementos)
    paginas_indice = 0
    if incluir_indice:
        # Reservar espacio para el índice (se calculará después)
        pass
    
    # 3. FICHAS
    unidades_vistas = set()
    for idx, dato in enumerate(datos_fichas):
        # Agregar al índice solo la primera vez que aparece la unidad
        if dato['unidad'].doc not in unidades_vistas:
            indice_datos.append({
                'unidad': dato['unidad'].unidad,
                'capitulo': dato['unidad'].capitulo,
                'pagina': pagina_actual + paginas_indice
            })
            unidades_vistas.add(dato['unidad'].doc)
        
        # Generar ficha
        elementos_ficha = generar_ficha(
            dato['unidad'],
            dato['ficha'],
            dato['mes_nombre'],
            ccpp,
            incluir_anexo,
            incluir_firmas_ficha,
            incluir_img_firma,
            dato['notificacion'],
            incluir_notif_remitente,
            incluir_notif_respuesta,
            fuente_reg,
            fuente_bold
        )
        elementos.extend(elementos_ficha)
        
        # Calcular páginas (aproximado)
        pagina_actual += 2  # Cada ficha ocupa aproximadamente 2 páginas
        if incluir_anexo:
            pagina_actual += 1
    
    # Generar índice ahora que conocemos las páginas
    if incluir_indice:
        elementos_indice = generar_indice(indice_datos, ccpp)
        # Insertar índice después de la portada
        for elem in reversed(elementos_indice):
            elementos.insert(inicio_indice, elem)
        paginas_indice = len([e for e in elementos_indice if isinstance(e, PageBreak)]) + 1
    
    # 4. PÁGINA FINAL (si está habilitada)
    if incluir_firmas_pie:
        elementos.extend(generar_pagina_final(ccpp,anio_real))
    
    # Construir PDF con numeración de páginas
    doc.build(elementos, canvasmaker=NumeroPaginaCanvas)
    
    # Preparar respuesta HTTP
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    nombre_archivo = f"Reporte_Inspecciones_{ccpp.nombre}_{anio_real}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    return response




#=============================================
# GENERAR PORTADA
#=============================================


def generar_portada(ccpp, anio_real):
    elementos = []
    estilos = getSampleStyleSheet()

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
    img_reporte_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'img_reporte.png')

    # ==================== LOGO ====================
    if os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, width=3*cm, height=3*cm)
            logo.hAlign = 'CENTER'
            elementos.append(Spacer(1, 0.1*cm))
            elementos.append(logo)
            elementos.append(Spacer(1, 0.5*cm))
        except:
            elementos.append(Spacer(1, 5.5*cm))
    else:
        elementos.append(Spacer(1, 5.5*cm))

    # ==================== TITULO PRINCIPAL ====================
    style_titulo_portada = ParagraphStyle(
        'TituloPortada',
        parent=estilos['Heading1'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elementos.append(Paragraph("CONTROL LIBRO DEL EDIFICIO", style_titulo_portada))

    # ==================== CCPP ====================
    ccpp_formateado = f"CCPP{ccpp.id_ccpp:03d}"
    style_ccpp = ParagraphStyle(
        'CCPPStyle',
        parent=estilos['Normal'],
        fontSize=13,
        textColor=colors.HexColor('#8B0000'),
        spaceAfter=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elementos.append(Paragraph(f"{ccpp_formateado} - {ccpp.nombre}", style_ccpp))

    # ==================== AÑO ====================
    style_anio = ParagraphStyle(
        'AnioStyle',
        parent=estilos['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    elementos.append(Paragraph(f"AÑO {anio_real}", style_anio))

    # ==================== IMAGEN CENTRAL ====================
    if os.path.exists(img_reporte_path):
        try:
            img_reporte = RLImage(img_reporte_path, width=13.5*cm, height=10*cm)
            img_reporte.hAlign = 'CENTER'
            elementos.append(img_reporte)
            elementos.append(Spacer(1, 1*cm))
        except:
            elementos.append(Spacer(1, 9*cm))
    else:
        elementos.append(Spacer(1, 9*cm))

    # ==================== LINEAS ====================
    color_lineas = colors.HexColor("#E8C898")

    d = Drawing(15*cm, 0.5*cm)
    line1 = Line(0, 4*mm, 15*cm, 4*mm, strokeColor=color_lineas, strokeWidth=2)
    line2 = Line(2*cm, 2*mm, 13*cm, 2*mm, strokeColor=color_lineas, strokeWidth=1)
    d.add(line1)
    d.add(line2)
    d.hAlign = 'CENTER'
    elementos.append(d)
    elementos.append(Spacer(1, 0.5*cm))

    # ==================== TITULO FINAL ====================
    style_portada = ParagraphStyle(
        'InspeccionesPortada',
        parent=estilos['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#E8C898'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elementos.append(Paragraph("REPORTE DE INSPECCIONES", style_portada))

    elementos.append(PageBreak())

    return elementos






#=============================================
# GENERAR INDICE
#=============================================

def generar_indice(indice_datos, ccpp):

    elementos = []
    styles = getSampleStyleSheet()

    # ====== ESTILOS HEADER ======
    estilo_header1 = ParagraphStyle('header1',parent=styles['Heading1'],alignment=TA_CENTER,fontSize=14,textColor=colors.black,spaceAfter=4)
    estilo_header2 = ParagraphStyle('header2',parent=styles['Normal'],fontSize=12,textColor=colors.HexColor("#A52A2A"),alignment=TA_CENTER,fontName='Helvetica-Bold',spaceAfter=2)
    estilo_indice = ParagraphStyle('indice',parent=styles['Normal'],alignment=TA_CENTER,fontSize=10,spaceAfter=6)

    # ====== HEADER ======
    elementos.append(Paragraph("CONTROL LIBRO DEL EDIFICIO", estilo_header1))
    id_formateado = f"CCPP{str(ccpp.id_ccpp).zfill(3)}" 
    elementos.append(Paragraph(f"{id_formateado} - {ccpp.nombre}", estilo_header2))
    elementos.append(Paragraph("INDICE DE UNIDADES", estilo_indice))

    elementos.append(HRFlowable(width="100%",thickness=2,color=colors.black,spaceAfter=12))

    # ====== ESTILOS TABLA ======
    estilo_unidad = ParagraphStyle('EstiloUnidadIndice',parent=styles['Normal'],fontSize=7,textColor=colors.HexColor('#6b7280'),alignment=TA_JUSTIFY,leading=12)
    estilo_pagina = ParagraphStyle('EstiloPaginaIndice',parent=estilo_unidad,alignment=TA_CENTER)

    # ====== DATOS TABLA ======
    datos_tabla = [['Unidad', 'Página']]

    for item in indice_datos:
        datos_tabla.append([
            Paragraph(item['unidad'], estilo_unidad),
            Paragraph(str(item['pagina']), estilo_pagina)
        ])

    tabla_indice = Table(datos_tabla, colWidths=[170*mm, 30*mm])

    tabla_indice.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTSIZE', (0, 0), (-1, 0), 11),

        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),

        ('LINEBELOW', (0, 0), (-1, -1), 0.5,
         colors.HexColor('#d1d5db'), None, (1, 2)),

        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    elementos.append(tabla_indice)
    elementos.append(PageBreak())

    return elementos





#=============================================
# GENERAR FICHA
#=============================================





class NumeroPaginaCanvas(canvas.Canvas):
    """
    Clase personalizada para agregar números de página y encabezados dinámicos
    """
    def __init__(self, *args, **kwargs):
        self.encabezado_handler = kwargs.pop('encabezado_handler', None)
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            
            # Dibujar encabezado si existe
            if self.encabezado_handler:
                self.encabezado_handler.dibujar_encabezado(self, None)
            
            # Dibujar número de página
            self.draw_page_number(num_pages)
            
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        
    def draw_page_number(self, page_count):
        """
        Dibuja el número de página en la parte inferior
        """
        self.setFont("Helvetica", 9)
        page_num = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 8*mm, 10*mm, page_num)








def partir_parrafo_por_altura(texto, estilo, ancho, alto_max=600):
    """
    Divide un texto en múltiples Paragraph que no superen alto_max puntos
    """
    palabras = texto.split(" ")
    partes = []
    actual = ""

    for palabra in palabras:
        prueba = actual + " " + palabra if actual else palabra
        p = Paragraph(prueba, estilo)
        w, h = p.wrap(ancho, 10000)

        if h > alto_max:
            partes.append(actual)
            actual = palabra
        else:
            actual = prueba

    if actual:
        partes.append(actual)

    return partes





def generar_ficha(unidad, ficha, mes, ccpp, incluir_anexo, incluir_firmas, incluir_img_firma, notificacion, incluir_notif_remitente, incluir_notif_respuesta, fuente_reg='Helvetica', fuente_bold='Helvetica-Bold'):
    """
    Genera una ficha individual con el diseño exacto del sistema original
    """
    elementos = []
    
    # Colores del diseño original
    gris_oscuro = colors.HexColor("#374151") 
    gris_suave = colors.HexColor("#d1d5db")
    gris_opaco_deshabilitado = "#e5e7eb"
    rojo_enfasis = colors.HexColor("#b91c1c")
    fondo_naranja_claro = colors.HexColor("#FDEBD0")
    verde_exito = "#166534"
    rojo_alerta = "#991b1b"
    
    # Estilos del diseño original
    estilo_titulo_principal = ParagraphStyle('T1', fontSize=13, fontName=fuente_bold, alignment=TA_CENTER)
    estilo_subtitulo_rojo = ParagraphStyle('T2', fontSize=16, fontName=fuente_bold, textColor=rojo_enfasis, alignment=TA_CENTER, leading=18)
    estilo_capitulo = ParagraphStyle('T3', fontSize=10, fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_unidad = ParagraphStyle('T4', fontSize=8, fontName=fuente_bold, alignment=TA_CENTER, textColor=gris_oscuro)
    estilo_titulo_seccion = ParagraphStyle('S1', fontSize=10, fontName=fuente_reg, textColor=colors.black)
    estilo_texto_cuerpo = ParagraphStyle('C1', fontSize=9.5, fontName=fuente_reg, leading=12, textColor=gris_oscuro, leftIndent=8*mm)
    estilo_etiqueta_info = ParagraphStyle('L1', fontSize=8.5, fontName=fuente_reg, textColor=gris_oscuro)
    estilo_firma_pie = ParagraphStyle('F1', fontSize=7.5, fontName=fuente_reg, textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)
    
    # ENCABEZADO DE LA FICHA
    try:
        ruta_logo_izq = finders.find('img/logo.png') or os.path.join(settings.BASE_DIR, 'static/img/logo.png')
        imagen_izq = Image(ruta_logo_izq, width=22*mm, height=22*mm) if os.path.exists(ruta_logo_izq) else ""
    except Exception:
        imagen_izq = ""
    
    try:
        imagen_der = ""
        if ficha.logo and os.path.exists(ficha.logo.path):
            imagen_der = Image(ficha.logo.path, width=15*mm, height=15*mm)
    except Exception:
        imagen_der = ""
    
    # Código DOC formateado
    codigo_doc = formatear_documento_seis_digitos(unidad.doc) if unidad.doc else "00 00 00"
    
    # Bloque central del encabezado
    bloque_centro = [
        Paragraph("CONTROL LIBRO DEL EDIFICIO", estilo_titulo_principal),
        Paragraph(codigo_doc, estilo_subtitulo_rojo),
        Paragraph(unidad.capitulo if unidad.capitulo else "", estilo_capitulo),
        Paragraph(unidad.unidad if unidad.unidad else "", estilo_unidad)
    ]
    
    # Tabla del encabezado
    t_header = Table([[imagen_izq, bloque_centro, imagen_der]], colWidths=[30*mm, 140*mm, 30*mm])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),   
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),  
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black), 
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
    ]))
    elementos.append(t_header)
    
    # Información de técnico y fecha
    nombre_tecnico = obtener_nombre_tecnico_cabecera(ccpp)
    fecha_formateada = ficha.fecha_creacion.strftime('%d/%m/%Y') if ficha.fecha_creacion else "No especificada"
    
    mes_destacado = f'<font size={10}><u><b>{mes.upper()}</b></u></font>'

    info_meta = [[
        Paragraph(f"<b>Técnico Cabecera:</b> {nombre_tecnico}", estilo_etiqueta_info),
        Paragraph(
            f"<b>Fecha:</b> {fecha_formateada} | {mes_destacado}", 
            ParagraphStyle('FD', parent=estilo_etiqueta_info, alignment=TA_RIGHT)
        )
    ]]
    
    t_meta = Table(info_meta, colWidths=[120*mm, 80*mm])
    t_meta.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), 
        ('RIGHTPADDING', (0, 0), (-1, -1), 0)
    ]))
    elementos.append(t_meta)
    elementos.append(Spacer(1, 2*mm))
    

    # TABLA DE CONTROLES 
    




    lista_controles = ficha.fichacontrol.all()



    # ENCABEZADO VISUAL DE CONTROLES
    estilo_head = ParagraphStyle(
        'head',
        parent=estilo_texto_cuerpo,
        fontName=fuente_reg,
        alignment=TA_LEFT,
        leftIndent=0,
        textColor=colors.black,
        fontSize=9,             
        leading=11,              

    )

    encabezado_controles = Table(
        [[
            Paragraph("<b>PERIODO</b>", estilo_head),
            Paragraph("<b>INSPECCIÓN</b>", estilo_head),
            Paragraph("<b>OK</b>", ParagraphStyle('h_ok', parent=estilo_head, alignment=TA_CENTER))
        ]],
        colWidths=[35*mm, 150*mm, 10*mm]
    )

    encabezado_controles.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FDEBD0')), 
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#A7A095")),  
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.grey),
    ]))

    elementos.append(encabezado_controles)
    elementos.append(Spacer(1, 2*mm))


    for control in lista_controles:
        if not control.ocultar:
            color_txt = gris_opaco_deshabilitado if control.opacar else "#374151"
            insp = control.id_inspeccion

            color_cod = (
                gris_opaco_deshabilitado
                if control.opacar
                else (insp.color_inspeccion if insp and insp.color_inspeccion else "#374151")
            )

            prefijo_html = (
                f'<font color="{color_cod}"><b>{insp.codigo_inspeccion if insp else "N/A"}</b></font> - '
                f'<u>{insp.nombre_inspeccion.upper() if insp else "S/I"}</u>: '
            )

            check = "✓" if control.ejecutado else ""

            estilo_periodo = ParagraphStyle(
                'per',
                parent=estilo_texto_cuerpo,
                leftIndent=0,
                wordWrap='CJK',
                spaceBefore=0,
                spaceAfter=0
            )

            estilo_inspeccion = ParagraphStyle(
                'ins',
                parent=estilo_texto_cuerpo,
                leftIndent=10*mm,
                wordWrap='CJK',
                spaceBefore=0,
                spaceAfter=0
            )

            estilo_ok = ParagraphStyle(
                'ok',
                parent=estilo_texto_cuerpo,
                alignment=TA_CENTER
            )

            # limpiar texto para evitar HTML roto
            import html
            texto_limpio = html.escape(control.control)

            # partir solo el texto plano
            partes = partir_parrafo_por_altura(
                texto_limpio,
                estilo_inspeccion,
                ancho=150*mm,
                alto_max=580
            )

            for i, parte in enumerate(partes):

                if i == 0:
                    texto_final = f'{prefijo_html}<font color="{color_txt}">{parte}</font>'
                else:
                    texto_final = f'<font color="{color_txt}">{parte}</font>'

                col_periodo = Paragraph(
                    f'<b>{control.periodo}</b><br/><font size=8 color="#b91c1c">Obligatorio</font>' if i == 0 else "",
                    estilo_periodo
                )

                col_inspeccion = Paragraph(texto_final, estilo_inspeccion)

                col_ok = Paragraph(check if i == 0 else "", estilo_ok)

                fila = Table(
                    [[col_periodo, col_inspeccion, col_ok]],
                    colWidths=[35*mm, 150*mm, 10*mm]
                )

                fila.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                    ('SPLIT', (0,0), (-1,-1), True),
                ]))

                elementos.append(fila)

            elementos.append(LineaSeparadora(195*mm))
            elementos.append(Spacer(1, 1*mm))







    
    # SECCIONES DE TEXTO (Precauciones, Prescripciones, Prohibiciones)
    for tit, cont in [
        ("✓ PRECAUCIONES", ficha.precaucion), 
        ("✓ PRESCRIPCIONES", ficha.prescripcion), 
        ("✓ PROHIBICIONES", ficha.prohibicion)
    ]:
        if cont:
            elementos.append(KeepTogether([
                Spacer(1, 4*mm),
                generar_encabezado_seccion(tit, estilo_titulo_seccion, gris_suave),
                Spacer(1, 1*mm),
                Paragraph(cont.replace('\n', '<br/>'), estilo_texto_cuerpo)
            ]))
    
    # BLOQUE DE FIRMAS (si está habilitado)
    if incluir_firmas:
        elementos.append(Spacer(1, 6*mm))

        # cargar imagen firma si corresponde
        firma_control = Paragraph('Firma', estilo_firma_pie)

        if incluir_img_firma:
            try:
                ruta_firma = finders.find('img/firma.png') or os.path.join(settings.BASE_DIR, 'static/img/firma.png')
                if os.path.exists(ruta_firma):
                    firma_control = Image(ruta_firma, width=35*mm, height=15*mm)
            except Exception:
                pass

        f_data = [
            [
                Paragraph('<b>FECHA INSPECCIÓN</b>', estilo_texto_cuerpo),
                Paragraph('<b>CONTROL</b>', estilo_texto_cuerpo),
                Paragraph('<b>OBSERVACIONES</b>', estilo_texto_cuerpo)
            ],
            ['', firma_control, '']
        ]

        t_firma = Table(
            f_data,
            colWidths=[50*mm, 50*mm, 100*mm],
            rowHeights=[None, 24*mm]
        )

        t_firma.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), fondo_naranja_claro),
            ('GRID', (0, 0), (-1, -1), 0.5, gris_oscuro),
            ('ALIGN', (1, 1), (1, 1), 'CENTER'),
            ('VALIGN', (1, 1), (1, 1), 'BOTTOM'),
            ('BOTTOMPADDING', (1, 1), (1, 1), 1.5*mm),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ]))

        elementos.append(KeepTogether([t_firma]))

    

    # ANEXO FOTOGRÁFICO (si está habilitado y existe)
    if incluir_anexo and ficha.foto:
        try:
            if os.path.exists(ficha.foto.path):
                elementos.append(KeepTogether([
                    Spacer(1, 5*mm),
                    generar_encabezado_seccion("✓ ANEXOS", estilo_titulo_seccion, gris_suave),
                    Spacer(1, 3*mm),
                    Image(ficha.foto.path, width=195*mm, height=80*mm, kind='proportional')
                ]))
        except Exception as e:
            print(f"Error al cargar imagen de ficha {ficha.titulo}: {e}")
    
    # NOTIFICACIÓN (si existe y está habilitada)
    if notificacion and (incluir_notif_remitente or incluir_notif_respuesta):
        elementos.append(Spacer(1, 5*mm))
        elementos.extend(generar_seccion_notificacion(
            notificacion, 
            estilo_titulo_seccion,
            gris_oscuro
        ))
    
    # Salto de página al final de la ficha
    elementos.append(PageBreak())
    
    return elementos






#=============================================
# GENERAR SECCION DE NOTIFICACION
#=============================================

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

def generar_seccion_notificacion(notificacion, estilo_titulo_seccion, gris_oscuro):
    """
    Genera la sección de notificación exactamente como la imagen:
    Título con check, línea horizontal y lista de campos.
    """
    elementos = []
    
    # Estilo para las etiquetas (Para, Cc, etc.) en cursiva y gris
    estilo_label = ParagraphStyle(
        'label_notif',
        fontSize=9,
        textColor=colors.HexColor('#666666'), # Gris oscuro
        fontName='Helvetica-Oblique', # Cursiva
        leftIndent=15 # Sangría para alinear con el texto tras el check
    )

    # 1. Título: ✓ NOTIFICACIONES
    elementos.append(Paragraph("✓ NOTIFICACIONES", estilo_titulo_seccion))
    
    # 2. Línea horizontal gris (ajustada al grosor de la imagen)
    elementos.append(HRFlowable(
        width="100%", 
        thickness=1.5, 
        color=colors.grey, 
        spaceBefore=1, 
        spaceAfter=4
    ))

    # 3. Lista de campos (Para, Cc, Cco, Revisión, Controlador, Vía)
    # Formateamos los datos para que la etiqueta sea cursiva y el valor normal
    campos = [
        ("Para", notificacion.para),
        ("Cc", notificacion.cc),
        ("Cco", notificacion.cco),
        ("Revisión", notificacion.RespRevision),
        ("Controlador", notificacion.RespControlador),
        ("Via", notificacion.RespVia)
    ]

    for label, valor in campos:
        texto_valor = valor if valor else "no"
        # Usamos etiquetas HTML simples para el estilo mixto
        texto_p = f"<i>{label}:</i> {texto_valor}"
        elementos.append(Paragraph(texto_p, estilo_label))
        # Espaciado mínimo entre líneas
        elementos.append(Spacer(1, 0.5 * mm))

    return elementos


#=============================================
# GENERAR PAGINA FINAL DE FIRMAS
#=============================================

def generar_pagina_final(ccpp, anio):
    """
    Genera la página final del informe idéntica a la imagen proporcionada.
    """
    elementos = []
    styles = getSampleStyleSheet()
    
    # --- ESTILOS ---
    estilo_header1 = ParagraphStyle('header1', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=14, textColor=colors.black, spaceAfter=2)
    estilo_header2 = ParagraphStyle('header2', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor("#A52A2A"), alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=2)
    estilo_anio = ParagraphStyle('anio', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, fontName='Helvetica-Bold', spaceAfter=12)
    
    estilo_cuerpo = ParagraphStyle('cuerpo', parent=styles['Normal'], fontSize=9, leading=12, alignment=TA_LEFT, spaceAfter=12, textColor=colors.grey)
    estilo_firma_label = ParagraphStyle('firma_label', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, fontName='Helvetica-Bold')

    # --- ENCABEZADO ---
    elementos.append(Paragraph("CONTROL LIBRO DEL EDIFICIO", estilo_header1))
    
    id_formateado = f"CCPP{str(ccpp.id_ccpp).zfill(3)}" 
    elementos.append(Paragraph(f"{id_formateado} - {ccpp.nombre.upper()}", estilo_header2))
    
    # Año dinámico
    elementos.append(Paragraph(f"AÑO {anio}", estilo_anio))
    
    # Línea negra gruesa
    elementos.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=30))

    # --- TEXTO INFORMATIVO ---
    textos = [
        "EL PRESENTE DOCUMENTO ES INFORMATIVO EN CUANTO A LAS FICHAS APORTADAS Y QUE CORRESPONDEN CON EL PERIODO INDICADO EN EL INFORME.",
        "ESTÁS REVISIONES HAN PODIDO EFECTUARSE TOTAL O PARCIALMENTE DEPENDIENDO DE LA OBLIGATORIEDAD DE CADA UNA DE ELLAS. ES ACONSEJABLE QUE TODAS Y CADA UNA DE ELLAS SE COMPRUEBE AL MENOS VISUALMENTE Y SI ES POSIBLE APORTAR UN DOCUMENTO FOTOGRÁFICO, ASÍ COMO OBSERVACIONES DE LAS FICHAS.",
        "EL DOCUMENTO VÁLIDO PARA INCLUIRLO EN LA DOCUMENTACIÓN DE MANTENIMIENTO DEL EDIFICIO SERÁ EL RESUMEN ANUAL QUE DEBERÁ SER FIRMADO POR EL TÉCNICO COMPENTENTE, LA ADMINISTRACIÓN Y EL PRESIDENTE DE LA COMUNIDAD. POR LO QUE PASARÁ A SER PARTE DE LA DOCUMENTACIÓN DEL EDIFICIO."
    ]

    for txt in textos:
        elementos.append(Paragraph(txt, estilo_cuerpo))
        elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Spacer(1, 2 * cm))
    elementos.append(Paragraph("ESTE DOCUMENTO SE FIRMA EL __________________________", estilo_cuerpo))
    
    elementos.append(Spacer(1, 3 * cm))
    elementos.append(Paragraph("FIRMAS.", estilo_cuerpo))
    elementos.append(Spacer(1, 1 * cm))

    # --- SECCIÓN DE FIRMAS (Líneas horizontales) ---
    # Usamos una tabla sin bordes, solo con líneas superiores en las celdas de firma
    datos_firmas = [
        ["", "", ""], # Espacio para la firma física
        ["TÉCNICO ASIGNADO", "ADMINISTRACIÓN", "PRESIDENTE CP."]
    ]
    
    # Ajustamos anchos para que ocupen el ancho de la página
    tabla_firmas = Table(datos_firmas, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
    
    tabla_firmas.setStyle(TableStyle([
        # Líneas horizontales sobre los textos (la línea de firma)
        ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),
        ('LINEABOVE', (1, 1), (1, 1), 1, colors.black),
        ('LINEABOVE', (2, 1), (2, 1), 1, colors.black),
        
        # Estilo de los textos
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 20),
        ('TOPPADDING', (0, 1), (-1, 1), 4), # Espacio pequeño entre línea y texto
    ]))
    
    elementos.append(tabla_firmas)
    
    return elementos








