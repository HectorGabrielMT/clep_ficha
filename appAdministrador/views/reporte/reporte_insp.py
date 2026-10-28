'''
 ================= HISTORIAL ================= 
Ultima modificacion:12/02/2026
Funcion: Generar el archivo PDF de las inspecciones de una ccpp en un anio especifico y un rango de meses y unos filtros especificos
Correo:hectormadrizgt@gmail.com

'''

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics import renderPDF
from datetime import datetime
from django.db.models import Q
from django.conf import settings
import os
import pytz
from django.conf import settings
ZONA_HORARIA = pytz.timezone(getattr(settings, 'ZONA_HORARIA_DEFECTO', 'UTC'))
class NumerosPaginas(canvas.Canvas):
    """Clase para manejar números de página y encabezados/pies personalizados"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.ccpp = None
        self.anio_real = None
        self.filtro_nombre = None
        self.ccpp_formateado = None
        self.tecnico_cabecera = None
        self.logo_path = None
        
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        

    def draw_page_decorations(self, num_pages):
        page_num = self._pageNumber
        
        # Solo agregar encabezado y pie si no es la primera página (portada)
        if page_num > 1:
            # ==================== ENCABEZADO ====================
            # Logo alineado exactamente al margen izquierdo (1.0*cm)
            if self.logo_path and os.path.exists(self.logo_path):
                try:
                    self.drawImage(self.logo_path, 1.0*cm, letter[1] - 2.4*cm, 
                                   width=25*mm, height=18*mm, preserveAspectRatio=True, mask='auto')
                except:
                    pass
            
            # Título "CONTROL LIBRO DEL EDIFICIO" (Movido a 3.8*cm para evitar solape)
            self.setFont('Helvetica-Bold', 14)
            self.setFillColor(colors.black)
            self.drawString(3.8*cm, letter[1] - 1.2*cm, "CONTROL LIBRO DEL EDIFICIO")
            
            # CCPP - Nombre (en vinotinto) (Movido a 3.8*cm)
            self.setFont('Helvetica-Bold', 11)
            self.setFillColor(colors.HexColor('#8B0000'))
            ccpp_texto = f"{self.ccpp_formateado} - {self.ccpp.nombre}"
            self.drawString(3.8*cm, letter[1] - 1.6*cm, ccpp_texto)
            
            # Año (Movido a 3.8*cm)
            self.setFont('Helvetica', 10)
            self.setFillColor(colors.black)
            self.drawString(3.8*cm, letter[1] - 2*cm, f"AÑO {self.anio_real}")
            
            # Título "INSPECCIONES - MODO"
            self.setFont('Helvetica', 11)
            self.setFillColor(colors.HexColor("#636161"))
            modo_texto = f"INSPECCIONES - {self.filtro_nombre.upper()}"
            self.drawCentredString(letter[0] / 2, letter[1] - 2.8*cm, modo_texto)
            
            # ==================== PIE DE PÁGINA ====================
            # Técnico de cabecera (lado izquierdo alineado a 1.0*cm)
            if self.tecnico_cabecera:
                lineas = self.tecnico_cabecera.split('\n')
                if len(lineas) > 1:
                    tecnico_texto = lineas[1].strip()
                else:
                    tecnico_texto = self.tecnico_cabecera.strip()
                
                self.setFont('Helvetica', 8)
                self.setFillColor(colors.HexColor('#666666'))
                self.drawString(1.0*cm, 1*cm, tecnico_texto)
            
            # Fecha de emisión (centro)
            fecha_actual = datetime.now(ZONA_HORARIA).strftime('%d.%m.%Y')
            self.setFont('Helvetica', 8)
            self.setFillColor(colors.HexColor('#666666'))
            self.drawCentredString(letter[0] / 2, 1*cm, f"Fecha de emisión: {fecha_actual}")
            
            # Número de página (derecha alineado a 1.0*cm del borde derecho)
            self.setFont('Helvetica', 8)
            self.setFillColor(colors.HexColor('#666666'))
            # page_num - 1 porque la portada es página 1 pero no se cuenta
            self.drawRightString(letter[0] - 1.0*cm, 1*cm, f"pág. {page_num - 1} de {num_pages - 1}")


def reporte_inspecciones_ccpp_pdf(request, ccpp_id, anio):
    """
    Genera un reporte PDF de inspecciones para una CCPP específica con filtros personalizables
    """
    from appAdministrador.models import tbl_CCPP, tbl_Cronograma, tbl_Unidad, tbl_inspeccion, tbl_Notificacion, tbl_CCPP_Unidad
    
    # Obtener parámetros de la URL
    periodo = request.GET.get('periodo', '1-12')
    filtro = request.GET.get('filtro', 'todas')
    periodo_nombre = request.GET.get('periodo_nombre', 'ANUAL')
    
    mes_inicio, mes_fin = map(int, periodo.split('-'))
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    meses_abrev = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 
                   'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
    
    # Obtener CCPP
    ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)
    
    # Calcular año real basado en fecha_entrega y año relativo
    anio_relativo = int(anio)
    if ccpp.fecha_entrega:
        anio_real = ccpp.fecha_entrega.year + anio_relativo
    else:
        anio_real = datetime.now().year + anio_relativo
    
    # Crear respuesta HTTP
    response = HttpResponse(content_type='application/pdf')
    filename = f'reporte_inspecciones_{periodo_nombre.lower()}_{filtro}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Paths de imágenes
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
    img_reporte_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'img_reporte.png')
    
    # Crear documento PDF con canvas personalizado
    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
        topMargin=3.2*cm,
        bottomMargin=1.3*cm,
        leftMargin=1.0*cm,  # Alineado a 1cm
        rightMargin=1.0*cm  # Alineado a 1cm
    )



    
    # Contenedor de elementos
    elements = []
    styles = getSampleStyleSheet()
    
    # ==================== PORTADA ====================
    
    # Logo
    if os.path.exists(logo_path):
        try:
            # Tamaño corporativo a 4.5 cm
            logo = RLImage(logo_path, width=4.5*cm, height=4.5*cm, kind='proportional')
            logo.hAlign = 'CENTER'
            elements.append(Spacer(1, 0.1*cm))
            elements.append(logo)
            elements.append(Spacer(1, 0.5*cm))
        except:
            elements.append(Spacer(1, 5.5*cm))
    else:
        elements.append(Spacer(1, 5.5*cm))
    
    # Título "CONTROL LIBRO DEL EDIFICIO"
    style_titulo_portada = ParagraphStyle(
        'TituloPortada',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.black,
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    titulo_portada = Paragraph("CONTROL LIBRO DEL EDIFICIO", style_titulo_portada)
    elements.append(titulo_portada)
    
    # CCPP - Nombre (en vinotinto)
    ccpp_formateado = f"CCPP{ccpp.id_ccpp:03d}"
    style_ccpp = ParagraphStyle(
        'CCPPStyle',
        parent=styles['Normal'],
        fontSize=13,
        textColor=colors.HexColor('#8B0000'),
        spaceAfter=8,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    ccpp_texto = Paragraph(f"{ccpp_formateado} - {ccpp.nombre}", style_ccpp)
    elements.append(ccpp_texto)
    
    # Año
    style_anio = ParagraphStyle(
        'AnioStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    anio_texto = Paragraph(f"AÑO {anio_real}", style_anio)
    elements.append(anio_texto)
    
    # Imagen del reporte
    if os.path.exists(img_reporte_path):
        try:
            img_reporte = RLImage(img_reporte_path, width=13.5*cm, height=10*cm)
            img_reporte.hAlign = 'CENTER'
            elements.append(img_reporte)
            elements.append(Spacer(1, 1*cm))
        except:
            elements.append(Spacer(1, 9*cm))
    else:
        elements.append(Spacer(1, 9*cm))
    
    # Líneas desvanecidas
    color_lineas = colors.HexColor("#E8C898")
    
    d = Drawing(15*cm, 0.5*cm)
    line1 = Line(0, 4*mm, 15*cm, 4*mm, strokeColor=color_lineas, strokeWidth=2)
    line2 = Line(2*cm, 2*mm, 13*cm, 2*mm, strokeColor=color_lineas, strokeWidth=1)
    d.add(line1)
    d.add(line2)
    d.hAlign = 'CENTER'
    elements.append(d)
    elements.append(Spacer(1, 0.5*cm))
    
    # Título "INSPECCIONES"
    style_insp_portada = ParagraphStyle(
        'InspeccionesPortada',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#E8C898'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    insp_titulo = Paragraph("INSPECCIONES", style_insp_portada)
    elements.append(insp_titulo)
    
    elements.append(PageBreak())
    
    # ==================== CONTENIDO ====================
    
    # Obtener unidades relacionadas con la CCPP
    unidades_ccpp = tbl_CCPP_Unidad.objects.filter(ccpp=ccpp).select_related('unidad')
    unidades_ids = [rel.unidad.id_unidad for rel in unidades_ccpp]
    
    # Obtener cronogramas del año seleccionado
    cronogramas = tbl_Cronograma.objects.filter(
        id_ccpp=ccpp,
        anios=anio_relativo
    ).select_related('id_unidad')
    
    # Crear diccionario de cronogramas por unidad
    cronograma_dict = {}
    for cron in cronogramas:
        cronograma_dict[cron.id_unidad.id_unidad] = cron
    
    # Obtener todas las notificaciones del año
    notificaciones = tbl_Notificacion.objects.filter(
        id_ccpp=ccpp,
        anio=anio_relativo
    ).select_related('id_unidad')
    
    # Crear diccionarios de notificaciones
    notificaciones_dict = {}  # {id_unidad: {mes: notificacion}}
    for notif in notificaciones:
        if notif.id_unidad.id_unidad not in notificaciones_dict:
            notificaciones_dict[notif.id_unidad.id_unidad] = {}
        notificaciones_dict[notif.id_unidad.id_unidad][notif.mes] = notif
    
    # Obtener todas las unidades ordenadas
    unidades = tbl_Unidad.objects.filter(id_unidad__in=unidades_ids).order_by('orden')
    
    # Aplicar filtros
    unidades_filtradas = []
    meses_validos_por_unidad = {}  # ← guardamos qué meses sí cumplen

    for unidad in unidades:
        cron = cronograma_dict.get(unidad.id_unidad)
        meses_validos = []

        if not cron:
            continue

        for i in range(mes_inicio - 1, mes_fin):
            mes_nombre = meses[i]
            valor_mes = getattr(cron, mes_nombre, None)

            if not valor_mes:
                continue  # no hay inspección programada ese mes

            notif_mes = None
            if unidad.id_unidad in notificaciones_dict:
                notif_mes = notificaciones_dict[unidad.id_unidad].get(mes_nombre)

            cumple = False

            if filtro == 'todas':
                cumple = True

            elif filtro == 'con_inspeccion':
                cumple = True

            elif filtro == 'sin_inspeccion':
                cumple = False  # ya sabemos que tiene inspección

            elif filtro == 'con_notificacion':
                cumple = bool(notif_mes)

            elif filtro == 'sin_notificacion':
                cumple = not notif_mes

            elif filtro == 'con_respuesta':
                cumple = bool(notif_mes and notif_mes.NotificacionContestada)

            elif filtro == 'sin_respuesta':
                cumple = bool(notif_mes and not notif_mes.NotificacionContestada)

            if cumple:
                meses_validos.append(mes_nombre)

        if meses_validos:
            unidades_filtradas.append(unidad)
            meses_validos_por_unidad[unidad.id_unidad] = meses_validos

    
    # Determinar nombre del filtro
    filtros_nombres = {
        'todas': 'Todas',
        'con_inspeccion': 'Con Inspección',
        'sin_inspeccion': 'Sin Inspección',
        'con_notificacion': 'Con Notificación',
        'sin_notificacion': 'Sin Notificación',
        'con_respuesta': 'Con Respuesta',
        'sin_respuesta': 'Sin Respuesta'
    }
    filtro_nombre = filtros_nombres.get(filtro, filtro)
    
    # Si no hay unidades que mostrar
    if not unidades_filtradas:
        style_no_data = ParagraphStyle(
            'NoDataStyle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#ef4444'),
            alignment=TA_CENTER
        )
        no_data = Paragraph("No se encontraron unidades con los filtros aplicados", style_no_data)
        elements.append(Spacer(1, 4*cm))
        elements.append(no_data)
    else:
        # Crear tabla de datos
        # Encabezado
        data = [['DOC', 'UNIDAD'] + [meses_abrev[i] for i in range(mes_inicio - 1, mes_fin)]]
        
        # Obtener todas las inspecciones
        inspecciones_dict = {}
        inspecciones_todas = tbl_inspeccion.objects.all()
        for insp in inspecciones_todas:
            inspecciones_dict[insp.id] = insp
        
        # Agregar filas de datos
        for unidad in unidades_filtradas:
            # Formatear DOC como '00 00 00'
            doc_value = unidad.doc or ''
            if doc_value and len(doc_value) >= 6:
                doc_formatted = f"{doc_value[0:2]} {doc_value[2:4]} {doc_value[4:6]}"
            else:
                doc_formatted = doc_value
            
            # Crear párrafo para unidad larga con justificación
            style_unidad = ParagraphStyle(
                'UnidadStyle',
                parent=styles['Normal'],
                fontSize=7,
                alignment=TA_JUSTIFY,
                leading=8
            )
            unidad_paragraph = Paragraph(unidad.unidad or '', style_unidad)
            
            fila = [doc_formatted, unidad_paragraph]
            
            cron = cronograma_dict.get(unidad.id_unidad)



            
            for i in range(mes_inicio - 1, mes_fin):
                mes_nombre = meses[i]
                celda_contenido = ''

                if unidad.id_unidad in meses_validos_por_unidad:
                    if mes_nombre in meses_validos_por_unidad[unidad.id_unidad]:
                        valor_mes = getattr(cron, mes_nombre, None)
                        if valor_mes:
                            try:
                                id_inspeccion = int(valor_mes)
                                if id_inspeccion in inspecciones_dict:
                                    insp = inspecciones_dict[id_inspeccion]
                                    celda_contenido = insp.codigo_inspeccion or ''
                            except (ValueError, TypeError):
                                pass

                fila.append(celda_contenido)





            
            data.append(fila)
        
        # Calcular anchos de columna
        num_meses = mes_fin - mes_inicio + 1
        ancho_doc = 1.8*cm
        ancho_unidad = 8*cm  # Más ancha para descripciones largas
        ancho_mes = 0.8*cm  # Columnas de meses más estrechas (solo 1 letra)
        
        col_widths = [ancho_doc, ancho_unidad] + [ancho_mes] * num_meses
        
        # Crear tabla
        table = Table(data, colWidths=col_widths, repeatRows=1)
        
        # Color de borde y encabezado
        color_borde = colors.HexColor('#FDEBD0')
        color_lineas = colors.HexColor("#EFCE9D")
        # Estilo base de la tabla
        table_style = [
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), color_borde),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('TOPPADDING', (0, 0), (-1, 0), 1),
            
            # Contenido - todas las celdas blancas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (0, -1), 7),  # DOC
            ('FONTSIZE', (1, 1), (1, -1), 7),  # UNIDAD
            ('FONTSIZE', (2, 1), (-1, -1), 8), # Meses
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # DOC centrado
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # UNIDAD alineado izquierda
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'), # Meses centrados
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),   # Alineación vertical superior
            ('TOPPADDING', (0, 0), (-1, 0), 1),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, color_lineas),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, color_lineas),
        ]
        
        # Aplicar colores a las letras de inspección
        for row_idx, unidad in enumerate(unidades_filtradas, start=1):
            cron = cronograma_dict.get(unidad.id_unidad)
            
            if cron:
                for col_idx, i in enumerate(range(mes_inicio - 1, mes_fin), start=2):
                    mes_nombre = meses[i]
                    valor_mes = getattr(cron, mes_nombre, None)
                    
                    if valor_mes:
                        try:
                            id_inspeccion = int(valor_mes)
                            if id_inspeccion in inspecciones_dict:
                                insp = inspecciones_dict[id_inspeccion]
                                
                                # Aplicar color a la letra
                                if insp.color_inspeccion:
                                    try:
                                        color_letra = colors.HexColor(insp.color_inspeccion)
                                        table_style.append(
                                            ('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), color_letra)
                                        )
                                    except:
                                        pass
                                
                                # Aplicar negrita
                                table_style.append(
                                    ('FONTNAME', (col_idx, row_idx), (col_idx, row_idx), 'Helvetica-Bold')
                                )
                        except (ValueError, TypeError):
                            pass
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)

    # --- 6. LEYENDA ---
    elements.append(Spacer(1, 0.8*cm))

    estilo_celda = ParagraphStyle(
        'LeyendaTexto',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_LEFT
    )

    estilo_celda_centrada = ParagraphStyle(
        'LeyendaLetra',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER
    )

    datos_leyenda = [
        [Paragraph('<b><font color="maroon">M</font></b>', estilo_celda_centrada), Paragraph('Operario Mantenimiento-Especialista', estilo_celda)],
        [Paragraph('<b><font color="red">E</font></b>', estilo_celda_centrada), Paragraph('Técnico Cabecera-Operario Especialista', estilo_celda)],
        [Paragraph('<b><font color="orange">O</font></b>', estilo_celda_centrada), Paragraph('Operario', estilo_celda)],
        [Paragraph('<b><font color="green">T</font></b>', estilo_celda_centrada), Paragraph('Técnico Cabecera', estilo_celda)],
        [Paragraph('<b><font color="darkgreen">I</font></b>', estilo_celda_centrada), Paragraph('Inspección Reglamentaria', estilo_celda)],
        [Paragraph('<b><font color="dodgerblue">P</font></b>', estilo_celda_centrada), Paragraph('Prueba Reglamentaria', estilo_celda)],
        [Paragraph('<b><font color="darkblue">C</font></b>', estilo_celda_centrada), Paragraph('Control Obligatorio', estilo_celda)],
        [Paragraph('<b><font color="purple">S</font></b>', estilo_celda_centrada), Paragraph('Sustitución Obligatoria', estilo_celda)]
    ]

    tabla_leyenda = Table(datos_leyenda, colWidths=[1*cm, 7*cm])
    tabla_leyenda.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),  # Borde sutil
    ]))

    elements.append(tabla_leyenda)

    
    # Construir PDF con canvas personalizado
    def on_page(canvas, doc):
        canvas.ccpp = ccpp
        canvas.anio_real = anio_real
        canvas.filtro_nombre = filtro_nombre
        canvas.ccpp_formateado = ccpp_formateado
        canvas.tecnico_cabecera = ccpp.tecnico_cabecera or ''
        canvas.logo_path = logo_path
    
    pdf_canvas = NumerosPaginas(response)
    pdf_canvas.ccpp = ccpp
    pdf_canvas.anio_real = anio_real
    pdf_canvas.filtro_nombre = filtro_nombre
    pdf_canvas.ccpp_formateado = ccpp_formateado
    pdf_canvas.tecnico_cabecera = ccpp.tecnico_cabecera or ''
    pdf_canvas.logo_path = logo_path
    
    doc.build(elements, canvasmaker=lambda *args, **kwargs: pdf_canvas)
    
    return response