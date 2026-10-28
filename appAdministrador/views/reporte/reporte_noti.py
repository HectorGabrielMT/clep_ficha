'''
 ================= HISTORIAL ================= 
Ultima modificacion:13/02/2026
Funcion: Generar el archivo PDF de las notificaciones de una ccpp en un anio especifico y un rango de meses
Correo:hectormadrizgt@gmail.com

'''

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Line
from datetime import datetime
from django.db.models import Q
from django.conf import settings
import os
import pytz
from django.conf import settings
ZONA_HORARIA = pytz.timezone(getattr(settings, 'ZONA_HORARIA_DEFECTO', 'UTC'))

class NumerosPaginasNotificaciones(canvas.Canvas):
    """Clase para manejar números de página y encabezados/pies personalizados para notificaciones"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self.ccpp = None
        self.anio_real = None
        self.periodo_nombre = None
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
            
            # CCPP - Nombre (Movido a 3.8*cm)
            self.setFont('Helvetica-Bold', 11)
            self.setFillColor(colors.HexColor('#8B0000'))
            ccpp_texto = f"{self.ccpp_formateado} - {self.ccpp.nombre}"
            self.drawString(3.8*cm, letter[1] - 1.6*cm, ccpp_texto)
            
            # Año (Movido a 3.8*cm)
            self.setFont('Helvetica', 10)
            self.setFillColor(colors.black)
            self.drawString(3.8*cm, letter[1] - 2*cm, f"AÑO {self.anio_real}")
            
            # Título "NOTIFICACIONES - PERIODO"
            self.setFont('Helvetica', 11)
            self.setFillColor(colors.HexColor("#636161"))
            modo_texto = f"NOTIFICACIONES - {self.periodo_nombre.upper()}"
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
            self.drawRightString(letter[0] - 1.0*cm, 1*cm, f"pág. {page_num - 1} de {num_pages - 1}")



def reporte_notificaciones_ccpp_pdf(request, ccpp_id, anio_relativo, mes_inicio, mes_fin, mostrar_remitentes, mostrar_respuesta):
    """
    Genera reporte PDF de notificaciones para un CCPP en un rango de meses y año relativo específico
    El PDF se descarga automáticamente
    
    Args:
        ccpp_id: ID del CCPP
        anio_relativo: Año relativo (0,1,2,3,...)
        mes_inicio: Mes de inicio (1-12)
        mes_fin: Mes de fin (1-12)
        mostrar_remitentes: Booleano para mostrar remitentes
        mostrar_respuesta: Booleano para mostrar respuestas
    """
    from appAdministrador.models import tbl_CCPP, tbl_Cronograma, tbl_Unidad, tbl_inspeccion, tbl_Notificacion
    
    try:
        # 1. VALIDACIÓN DE PARÁMETROS
        mostrar_remitentes = str(mostrar_remitentes).lower() == 'true'
        mostrar_respuesta = str(mostrar_respuesta).lower() == 'true'
        
        # Obtener CCPP
        ccpp = get_object_or_404(tbl_CCPP, id_ccpp=ccpp_id)
        
        # Validar año relativo
        try:
            anio_relativo = int(anio_relativo)
            if anio_relativo < 0:
                return HttpResponse("Error: El año relativo no puede ser negativo", status=400)
            if ccpp.cantidad_anios and anio_relativo >= ccpp.cantidad_anios:
                return HttpResponse(
                    f"Error: El año relativo excede la cantidad de años contratados ({ccpp.cantidad_anios})",
                    status=400
                )
        except (ValueError, TypeError):
            return HttpResponse("Error: El año relativo debe ser un número entero", status=400)

        if not ccpp.fecha_entrega:
            return HttpResponse("Error: La CCPP no tiene fecha de entrega definida", status=400)

        anio_real = ccpp.fecha_entrega.year + anio_relativo
        
        # Validar rango de meses
        try:
            mes_inicio = int(mes_inicio)
            mes_fin = int(mes_fin)
            if not (1 <= mes_inicio <= 12 and 1 <= mes_fin <= 12 and mes_inicio <= mes_fin):
                raise ValueError
        except (ValueError, TypeError):
            mes_inicio, mes_fin = 1, 12
        
        # Obtener nombre del periodo
        periodo_nombre = request.GET.get('periodo_nombre', 'ANUAL')
        
        # 2. CONFIGURACIÓN DEL PDF
        response = HttpResponse(content_type='application/pdf')
        nombre_archivo = f"noti_{ccpp_id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        
        # Paths de imágenes
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png')
        img_reporte_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'img_reporte.png')
        
        # Crear documento PDF
        # Crear documento PDF con márgenes reducidos
        doc = SimpleDocTemplate(
            response,
            pagesize=letter,
            topMargin=3.2*cm,
            bottomMargin=1.3*cm,
            leftMargin=1.0*cm,  # Reducido de 1.5cm a 1.0cm
            rightMargin=1.0*cm   # Reducido de 1.5cm a 1.0cm
        )
        
        elementos = []
        estilos = getSampleStyleSheet()
        
        # ==================== PORTADA ====================
        
        # Logo
# Logo
        if os.path.exists(logo_path):
            try:
                logo = RLImage(logo_path, width=4.5*cm, height=4.5*cm, kind='proportional')
                logo.hAlign = 'CENTER'
                elementos.append(Spacer(1, 0.1*cm))
                elementos.append(logo)
                elementos.append(Spacer(1, 0.5*cm))
            except:
                elementos.append(Spacer(1, 3.5*cm))
        else:
            elementos.append(Spacer(1, 5.5*cm))
        
        # Título "CONTROL LIBRO DEL EDIFICIO"
        style_titulo_portada = ParagraphStyle(
            'TituloPortada',
            parent=estilos['Heading1'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        titulo_portada = Paragraph("CONTROL LIBRO DEL EDIFICIO", style_titulo_portada)
        elementos.append(titulo_portada)
        
        # CCPP - Nombre (en vinotinto)
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
        ccpp_texto = Paragraph(f"{ccpp_formateado} - {ccpp.nombre}", style_ccpp)
        elementos.append(ccpp_texto)
        
        # Año
        style_anio = ParagraphStyle(
            'AnioStyle',
            parent=estilos['Normal'],
            fontSize=11,
            textColor=colors.black,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        anio_texto = Paragraph(f"AÑO {anio_real}", style_anio)
        elementos.append(anio_texto)
        
        # Imagen del reporte
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
        
        # Líneas desvanecidas
        color_lineas = colors.HexColor("#E8C898")
        
        d = Drawing(15*cm, 0.5*cm)
        line1 = Line(0, 4*mm, 15*cm, 4*mm, strokeColor=color_lineas, strokeWidth=2)
        line2 = Line(2*cm, 2*mm, 13*cm, 2*mm, strokeColor=color_lineas, strokeWidth=1)
        d.add(line1)
        d.add(line2)
        d.hAlign = 'CENTER'
        elementos.append(d)
        elementos.append(Spacer(1, 0.5*cm))
        
        # Título "NOTIFICACIONES"
        style_notif_portada = ParagraphStyle(
            'NotificacionesPortada',
            parent=estilos['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#E8C898'),
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        notif_titulo = Paragraph("NOTIFICACIONES", style_notif_portada)
        elementos.append(notif_titulo)
        
        elementos.append(PageBreak())
        
        # ==================== CONTENIDO ====================
        
        # 3. PREPARACIÓN DE DATOS
        nombres_meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        
        meses_filtro = nombres_meses[mes_inicio-1:mes_fin]

        filtro_meses = Q()
        for m in meses_filtro:
            filtro_meses |= Q(mes__iexact=m)
        
        # Obtener todas las inspecciones disponibles
        inspecciones = {str(i.id): (i.codigo_inspeccion, i.color_inspeccion) 
                       for i in tbl_inspeccion.objects.all()}
        
        # Obtener notificaciones del año relativo y meses seleccionados
        notificaciones = (tbl_Notificacion.objects
            .filter(
                Q(id_ccpp=ccpp),
                Q(anio=anio_relativo),
                filtro_meses
            )
            .select_related('id_unidad')
            .order_by('id_unidad__orden', 'fecha')
        )
        
        if not notificaciones.exists():
            style_no_data = ParagraphStyle(
                'NoDataStyle',
                parent=estilos['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#ef4444'),
                alignment=TA_CENTER
            )
            no_data = Paragraph("No hay notificaciones registradas para el período seleccionado", style_no_data)
            elementos.append(Spacer(1, 4*cm))
            elementos.append(no_data)
            doc.build(elementos)
            return response
        
        # Obtener IDs de unidades únicas
        unidades_ids = notificaciones.values_list('id_unidad_id', flat=True).distinct()
        
        # Obtener cronogramas para estas unidades en el año relativo
        cronogramas = {
            c.id_unidad_id: c 
            for c in tbl_Cronograma.objects.filter(
                id_ccpp=ccpp,
                id_unidad_id__in=unidades_ids,
                anios=anio_relativo
            ).select_related('id_unidad')
        }
        

        
        # 4. CREAR TABLA DE CONTENIDO
        estilo_celda = ParagraphStyle(
            'CeldaEstilo',
            parent=estilos['Normal'],
            fontSize=8,  # Aumentado de 7 a 8
            leading=9,
            alignment=TA_LEFT
        )
        
        encabezados = ['DOC', 'UNIDAD', 'MES', 'ENVIADO', 'RESPONDIDO', 'INSP.']
        titulos = [Paragraph(f"<b>{h}</b>", estilo_celda) for h in encabezados]
        data_tabla = [titulos]
        
        color_borde = colors.HexColor('#FDEBD0')
        color_lineas = colors.HexColor("#EFCE9D")
        
        estilos_tabla = [
            ('BACKGROUND', (0, 0), (-1, 0), color_borde),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, color_lineas),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (2, 1), (5, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('TOPPADDING', (0, 0), (-1, 0), 1),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, color_lineas),
        ]
        
        # Procesar cada notificación
        for notif in notificaciones:
            unidad = notif.id_unidad
            crono = cronogramas.get(unidad.id_unidad)
            
            # Obtener código de inspección
            codigo_inspeccion = ""
            color_inspeccion = "#000000"
            
            if crono and notif.mes:
                mes_lower = notif.mes.lower()
                valor_mes = getattr(crono, mes_lower, None)
                
                if valor_mes:
                    valor_str = str(valor_mes)
                    if valor_str in inspecciones:
                        codigo_inspeccion, color = inspecciones[valor_str]
                        color_inspeccion = color if color and str(color).startswith('#') else "#000000"
                    else:
                        codigo_inspeccion = valor_str
            
            # Formatear DOC
            doc_formateado = "--"
            if unidad.doc:
                doc_str = str(unidad.doc).zfill(6)
                doc_formateado = f"{doc_str[0:2]} {doc_str[2:4]} {doc_str[4:6]}"

            # Fila principal
            fila = [
                Paragraph(doc_formateado, estilo_celda),
                Paragraph(str(unidad.unidad or "--"), estilo_celda),
                Paragraph(str(notif.mes[:3].upper() if notif.mes else "--"), estilo_celda),
                Paragraph(notif.fecha.strftime('%d-%m-%Y') if notif.fecha else "--", estilo_celda),
                Paragraph(notif.FechaResp.strftime('%d-%m-%Y') if notif.FechaResp else "--", estilo_celda),
                Paragraph(f'<b><font color="{color_inspeccion}">{codigo_inspeccion or "--"}</font></b>', 
                        estilo_celda)
            ]
            data_tabla.append(fila)
            
            # Información adicional según parámetros
            if mostrar_remitentes or mostrar_respuesta:
                detalles = []
                color_detalle = colors.HexColor('#3F51B5')
                
                if mostrar_remitentes:
                    for campo, valor in [('Para', notif.para), ('Cc', notif.cc), ('Cco', notif.cco)]:
                        if valor:
                            detalles.append(f"<b>{campo}:</b> {valor}")
                
                if mostrar_respuesta:
                    for campo, valor in [('Revisión', notif.RespRevision), 
                                       ('Controlador', notif.RespControlador),
                                       ('Vía', notif.RespVia), 
                                       ('Observación', notif.RespObservacion)]:
                        if valor:
                            detalles.append(f"<i>{campo}:</i> {valor}")
                
                if detalles:
                    estilo_detalle = ParagraphStyle(
                        'DetalleEstilo',
                        parent=estilos['Normal'],
                        fontSize=7,
                        textColor=color_detalle,
                        leading=8
                    )
                    
                    texto_detalles = "<br/>".join(detalles)
                    data_tabla.append([Paragraph(texto_detalles, estilo_detalle), '', '', '', '', ''])
                    idx_fila = len(data_tabla) - 1
                    estilos_tabla.extend([
                        ('SPAN', (0, idx_fila), (5, idx_fila)),
                        ('BOTTOMPADDING', (0, idx_fila), (5, idx_fila), 5),
                        ('TOPPADDING', (0, idx_fila), (5, idx_fila), 3),
                        ('BACKGROUND', (0, idx_fila), (5, idx_fila), colors.HexColor('#F9F9F9'))
                    ])
        
        # Crear tabla final
        ancho_columnas = [
            2.1*cm,      # DOC
            9.0*cm,      # UNIDAD
            1.9*cm,      # MES
            2.6*cm,      # ENVIADO
            2.6*cm,      # RESPONDIDO
            1.9*cm       # INSP.
        ]  # Total: 20.1cm (deja solo 0.1cm de margen a cada lado)

        tabla_final = Table(data_tabla, colWidths=ancho_columnas, repeatRows=1)
        tabla_final.setStyle(TableStyle(estilos_tabla))
        elementos.append(tabla_final)

        elementos.append(Spacer(1, 0.5*cm))

        # ==================== LEYENDA ====================
        estilo_celda = ParagraphStyle(
            'LeyendaTexto',
            parent=estilos['Normal'],
            fontSize=8,
            alignment=TA_LEFT
        )

        estilo_celda_centrada = ParagraphStyle(
            'LeyendaLetra',
            parent=estilos['Normal'],
            fontSize=9,
            alignment=TA_CENTER
        )

        # Crear tabla de leyenda con 2 columnas (símbolo y descripción)
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

        # Crear tabla de leyenda
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
        elementos.append(tabla_leyenda)
        
        
        # 5. CONSTRUIR PDF
        pdf_canvas = NumerosPaginasNotificaciones(response)
        pdf_canvas.ccpp = ccpp
        pdf_canvas.anio_real = anio_real
        pdf_canvas.periodo_nombre = periodo_nombre
        pdf_canvas.ccpp_formateado = ccpp_formateado
        pdf_canvas.tecnico_cabecera = ccpp.tecnico_cabecera or ''
        pdf_canvas.logo_path = logo_path
        
        doc.build(elementos, canvasmaker=lambda *args, **kwargs: pdf_canvas)
        return response
        
    except Exception as e:
        import traceback
        print(f"Error en reporte_notificaciones_ccpp_pdf:")
        print(traceback.format_exc())
        return HttpResponse(f"Error al generar el reporte: {str(e)}", status=500)