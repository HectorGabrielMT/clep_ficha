import logging
import re
from datetime import date, datetime
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import IntegerField
from django.db.models.functions import Substr, Cast
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.db.models.functions import ExtractYear

# Importaciones locales
from appAdministrador.models import *

# Configuración de logger
logger = logging.getLogger(__name__)



#=================================Función para mostrar el panel de CCPP==========================================
@login_required
def vista_panel_ccpp(request):
    try:
        ccpps = tbl_CCPP.objects.all().select_related()

        valores_id_ccpp = (
            ccpps.values_list("id_ccpp", flat=True).order_by("id_ccpp")
        )

        valores_fecha_entrega = (
            ccpps.exclude(fecha_entrega__isnull=True)
            .annotate(year=ExtractYear("fecha_entrega"))
            .values_list("year", flat=True)
            .distinct()
            .order_by("year")
        )

        valores_cantidad_anios = (
            ccpps.values_list("cantidad_anios", flat=True)
            .distinct()
            .order_by("cantidad_anios")
        )

        contexto = {
            "ccpps": ccpps,
            "valores_id_ccpp": valores_id_ccpp,
            "valores_fecha_entrega": valores_fecha_entrega,
            "valores_cantidad_anios": valores_cantidad_anios,
        }

        logger.info(
            "Panel CCPP cargado correctamente: total=%s",
            ccpps.count()
        )

    except Exception as error:
        logger.exception("Error en vista_panel_ccpp: %s", error)
        messages.error(request, "Error al cargar el panel de CCPP.")
        contexto = {
            "ccpps": [],
            "valores_id_ccpp": [],
            "valores_fecha_entrega": [],
            "valores_cantidad_anios": [],
        }

    return render(request, "dataMaestra/ccpp/panel_ccpp.html", contexto)



import os
import re
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.db import transaction, IntegrityError
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

#=================================Función para crear una nueva CCPP==========================================
@login_required
@csrf_protect
def nueva_ccpp(request):
    LIMITE_CARACTERES = 200

    if request.method == "GET":
        hoy = date.today()
        anios_default = 10
        contexto = {
            "es_edicion": False,
            "ccpp_nombre": "",
            "fecha_entrega": hoy.isoformat(),
            "cantidad_anios": anios_default,
            "periodo": f"{hoy.year}-{hoy.year + anios_default}",
            "valor_periodo": f"{hoy.year}-{hoy.year + anios_default}",
            "direccion": "",
            "habilitada": True,
            "operario_comunidad": "",
            "empresa_especializada": "",
            "administracion_edificio": "",
            "tecnico_especialista": "",
            "tecnico_cabecera": "",
            "copia_oculta": "",
        }
        return render(request, "dataMaestra/ccpp/formulario_ccpp.html", contexto)

    datos = request.POST
    archivo_imagen = request.FILES.get("imagen")
    errores = {}

    # Captura de datos
    nombre = datos.get("ccpp_residencial", "").strip()
    fecha_entrega_str = datos.get("fecha_entrega")
    cantidad_anios_str = datos.get("cant_anos", "0").strip()
    direccion = datos.get("direccion", "").strip()
    habilitada = datos.get("habilitada") in ["on", "True"]
    periodo_str = datos.get("periodo", "").strip()

    # Validar período (opcional)
    if periodo_str and not re.match(r'^\d{4}-\d{4}$', periodo_str):
        errores["periodo"] = "Formato de período inválido (debe ser YYYY-YYYY)."

    # Validaciones básicas
    if not nombre:
        errores["ccpp_residencial"] = "El nombre es obligatorio."
    elif len(nombre) > 150:
        errores["ccpp_residencial"] = "Máximo 150 caracteres permitidos."

    # Validar fecha
    fecha_entrega = None
    if fecha_entrega_str:
        try:
            fecha_entrega = datetime.strptime(fecha_entrega_str, "%Y-%m-%d").date()
            if fecha_entrega < date.today():
                messages.warning(request, "La fecha de entrega es anterior a hoy.")
        except ValueError:
            errores["fecha_entrega"] = "Formato de fecha inválido."

    # Validar cantidad de años
    try:
        cantidad_anios = int(cantidad_anios_str)
        if not (0 <= cantidad_anios <= 50):
            errores["cant_anos"] = "Rango permitido: 0 a 50 años."
    except ValueError:
        cantidad_anios = 0
        errores["cant_anos"] = "Ingrese un número entero válido."

    # Validar campos opcionales
    campos_mapeo = {
        "operario_comunidad": datos.get("operario_comunidad", "").strip(),
        "empresa_especializada": datos.get("empresa_especializada", "").strip(),
        "administracion_edificio": datos.get("administracion_edificio", "").strip(),
        "tecnico_especialista": datos.get("tecnico_especialista", "").strip(),
        "tecnico_cabecera": datos.get("tecnico_cabecera", "").strip(),
        "copia_oculta": datos.get("copia_oculta", "").strip(),
    }

    for campo, valor in campos_mapeo.items():
        if len(valor) > LIMITE_CARACTERES:
            errores[campo] = f"Máximo {LIMITE_CARACTERES} caracteres permitidos."

    # Validar imagen
    if archivo_imagen:
        if archivo_imagen.size > 5 * 1024 * 1024:
            errores["imagen"] = "La imagen no debe exceder los 5MB."
        if not archivo_imagen.content_type.startswith("image/"):
            errores["imagen"] = "El archivo debe ser una imagen."

    # Si hay errores, devolver al formulario
    if errores:
        contexto = {
            "es_edicion": False,
            "errores": errores,
            "ccpp_nombre": nombre,
            "fecha_entrega": fecha_entrega_str or "",
            "cantidad_anios": cantidad_anios_str,
            "periodo": periodo_str,
            "valor_periodo": periodo_str,
            "direccion": direccion,
            "habilitada": habilitada,
            **campos_mapeo,
        }
        messages.warning(request, "Por favor corrija los errores del formulario.")
        logger.warning("Errores de validación al crear CCPP: %s", errores)
        return render(request, "dataMaestra/ccpp/formulario_ccpp.html", contexto)

    # Guardado
    try:
        with transaction.atomic():
            nueva_instancia = tbl_CCPP.objects.create(
                nombre=nombre,
                fecha_entrega=fecha_entrega,
                cantidad_anios=cantidad_anios,
                direccion=direccion or None,
                habilitada=habilitada,
                imagen=archivo_imagen,
                **campos_mapeo,
            )
            
            messages.success(
                request,
                f"CCPP creada exitosamente con ID CCPP{nueva_instancia.id_ccpp:03d}.",
            )
            logger.info(
                "CCPP creada exitosamente: id=%s, nombre=%s",
                nueva_instancia.id_ccpp,
                nombre,
            )
            # Redirigir a la misma página de edición
            return redirect(reverse("editar_ccpp", args=[nueva_instancia.id_ccpp]))
    except Exception as error:
        logger.exception("Error al crear CCPP: %s", error)
        messages.error(request, "Error interno al guardar.")
        return redirect(reverse("nueva_ccpp"))


#=================================Función para editar una CCPP existente==========================================
@login_required
@csrf_protect
def editar_ccpp(request, ccpp_id):
    LIMITE_CARACTERES = 200
    ccpp_actual = get_object_or_404(tbl_CCPP, pk=ccpp_id)

    if request.method == "GET":
        # Calcular período para mostrar
        periodo_display = "-"
        valor_periodo = ""
        if ccpp_actual.fecha_entrega and ccpp_actual.cantidad_anios:
            inicio = ccpp_actual.fecha_entrega.year
            fin = inicio + ccpp_actual.cantidad_anios
            periodo_display = f"{inicio}-{fin}"
            valor_periodo = periodo_display
        
        contexto = {
            "es_edicion": True,
            "ccpp": ccpp_actual,
            "ccpp_id": ccpp_id,
            "ccpp_nombre": ccpp_actual.nombre,
            "fecha_entrega": (
                ccpp_actual.fecha_entrega.strftime("%Y-%m-%d")
                if ccpp_actual.fecha_entrega else ""
            ),
            "cantidad_anios": ccpp_actual.cantidad_anios,
            "periodo": periodo_display,
            "valor_periodo": valor_periodo,
            "direccion": ccpp_actual.direccion or "",
            "habilitada": ccpp_actual.habilitada,
            "operario_comunidad": ccpp_actual.operario_comunidad or "",
            "empresa_especializada": ccpp_actual.empresa_especializada or "",
            "administracion_edificio": ccpp_actual.administracion_edificio or "",
            "tecnico_especialista": ccpp_actual.tecnico_especialista or "",
            "tecnico_cabecera": ccpp_actual.tecnico_cabecera or "",
            "copia_oculta": ccpp_actual.copia_oculta or "",
        }
        return render(request, "dataMaestra/ccpp/formulario_ccpp.html", contexto)

    # Lógica POST
    datos = request.POST
    archivo_imagen = request.FILES.get("imagen")
    remove_image = datos.get("remove_image") == "true"
    errores = {}

    nombre = datos.get("ccpp_residencial", "").strip()
    fecha_entrega_str = datos.get("fecha_entrega")
    cantidad_anios_str = datos.get("cant_anos", "0").strip()
    direccion = datos.get("direccion", "").strip()
    habilitada = datos.get("habilitada") in ["on", "True"]
    periodo_str = datos.get("periodo", "").strip()

    # Validar período
    if periodo_str and not re.match(r'^\d{4}-\d{4}$', periodo_str):
        errores["periodo"] = "Formato de período inválido (debe ser YYYY-YYYY)."

    # Validaciones
    if not nombre:
        errores["ccpp_residencial"] = "El nombre es obligatorio."
    elif len(nombre) > 150:
        errores["ccpp_residencial"] = "Máximo 150 caracteres."

    if direccion and len(direccion) > 255:
        errores["direccion"] = "Máximo 255 caracteres permitidos."

    try:
        nueva_cantidad_anios = int(cantidad_anios_str)
        if not (0 <= nueva_cantidad_anios <= 50):
            errores["cant_anos"] = "Rango permitido: 0 a 50 años."
    except ValueError:
        nueva_cantidad_anios = ccpp_actual.cantidad_anios
        errores["cant_anos"] = "Número inválido."

    # Validar campos largos
    campos_mapeo = {
        "operario_comunidad": datos.get("operario_comunidad", "").strip(),
        "empresa_especializada": datos.get("empresa_especializada", "").strip(),
        "administracion_edificio": datos.get("administracion_edificio", "").strip(),
        "tecnico_especialista": datos.get("tecnico_especialista", "").strip(),
        "tecnico_cabecera": datos.get("tecnico_cabecera", "").strip(),
        "copia_oculta": datos.get("copia_oculta", "").strip(),
    }

    for campo, valor in campos_mapeo.items():
        if len(valor) > LIMITE_CARACTERES:
            errores[campo] = f"Máximo {LIMITE_CARACTERES} caracteres."

    # Validar imagen
    if archivo_imagen:
        if archivo_imagen.size > 5 * 1024 * 1024:
            errores["imagen"] = "La imagen no debe exceder los 5MB."
        if not archivo_imagen.content_type.startswith("image/"):
            errores["imagen"] = "El archivo debe ser una imagen."

    if errores:
        contexto = {
            "es_edicion": True,
            "ccpp": ccpp_actual,
            "ccpp_id": ccpp_id,
            "errores": errores,
            "ccpp_nombre": nombre,
            "fecha_entrega": fecha_entrega_str or "",
            "cantidad_anios": cantidad_anios_str,
            "periodo": periodo_str,
            "valor_periodo": periodo_str,
            "direccion": direccion,
            "habilitada": habilitada,
            **campos_mapeo,
        }
        messages.warning(request, "Por favor corrija los errores del formulario.")
        logger.warning("Errores de validación al editar CCPP %s: %s", ccpp_id, errores)
        return render(request, "dataMaestra/ccpp/formulario_ccpp.html", contexto)

    try:
        with transaction.atomic():
            original_anios = ccpp_actual.cantidad_anios

            # Actualización de campos
            ccpp_actual.nombre = nombre
            ccpp_actual.direccion = direccion or None
            ccpp_actual.habilitada = habilitada
            ccpp_actual.cantidad_anios = nueva_cantidad_anios

            if fecha_entrega_str:
                try:
                    ccpp_actual.fecha_entrega = datetime.strptime(
                        fecha_entrega_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    ccpp_actual.fecha_entrega = None
            else:
                ccpp_actual.fecha_entrega = None

            # Campos extensos
            for campo, valor in campos_mapeo.items():
                setattr(ccpp_actual, campo, valor)

            # Imagen
            if remove_image:
                eliminar_archivo_seguro(ccpp_actual.imagen)
                ccpp_actual.imagen = None
            elif archivo_imagen:
                # Eliminar imagen anterior si existe
                if ccpp_actual.imagen:
                    eliminar_archivo_seguro(ccpp_actual.imagen)
                ccpp_actual.imagen = archivo_imagen

            ccpp_actual.save()

            # Sincronizar cronograma si cambió la cantidad de años
            if nueva_cantidad_anios != original_anios:
                gestionar_sincronizacion_cronograma(
                    ccpp_actual, original_anios, nueva_cantidad_anios
                )
                logger.info(
                    "Cronograma sincronizado para CCPP %s: años de %s a %s",
                    ccpp_id, original_anios, nueva_cantidad_anios
                )

            messages.success(
                request,
                f"CCPP actualizada correctamente (ID CCPP{ccpp_actual.id_ccpp:03d})."
            )
            logger.info("CCPP editada exitosamente: id=%s, nombre=%s", ccpp_id, nombre)
            return redirect(reverse("editar_ccpp", args=[ccpp_id]))

    except Exception as error:
        logger.exception("Error al editar CCPP %s: %s", ccpp_id, error)
        messages.error(request, f"Error al procesar la actualización: {error}")
        return redirect(reverse("editar_ccpp", args=[ccpp_id]))


#=================================Función para eliminar archivos de forma segura==========================================
def eliminar_archivo_seguro(archivo_field):
    """
    Elimina un archivo físico de forma segura.
    Retorna True si fue exitoso o no había archivo, False si falló.
    """
    if not archivo_field:
        return True
    
    try:
        # Verificar si el archivo existe físicamente
        if os.path.isfile(archivo_field.path):
            # Eliminar archivo
            os.remove(archivo_field.path)
            logger.info(f"Archivo eliminado: {archivo_field.path}")
            
            # Intentar eliminar directorio padre si está vacío
            directorio = os.path.dirname(archivo_field.path)
            if os.path.exists(directorio) and not os.listdir(directorio):
                os.rmdir(directorio)
                logger.info(f"Directorio vacío eliminado: {directorio}")
        
        # Limpiar referencia en el campo
        archivo_field.delete(save=False)
        return True
        
    except Exception as e:
        logger.error(f"Error al eliminar archivo {archivo_field.name if archivo_field else 'None'}: {e}")
        return False


#=================================Función para sincronizar cronogramas==========================================
def gestionar_sincronizacion_cronograma(ccpp, original, nuevo):
    """
    Sincroniza los registros de tbl_Cronograma cuando cambia la cantidad de años en una CCPP.
    
    Args:
        ccpp: Instancia de tbl_CCPP
        original: Cantidad de años original (puede ser None)
        nuevo: Nueva cantidad de años
    """
    try:
        # Validar parámetros
        if original is None:
            original = 0
        
        if nuevo < 0:
            raise ValueError(f"Cantidad de años no puede ser negativa: {nuevo}")
        
        with transaction.atomic():
            # Obtener todas las unidades asociadas a esta CCPP
            unidades_ids = tbl_CCPP_Unidad.objects.filter(
                ccpp=ccpp
            ).values_list("unidad_id", flat=True)
            
            # Si no hay unidades, no hay nada que sincronizar
            if not unidades_ids:
                logger.info("No hay unidades asociadas para sincronizar cronogramas")
                return
            
            # Caso 1: Reducción de años (Eliminar los que sobran)
            if nuevo < original:
                # Buscar cronogramas a eliminar
                cronogramas_eliminar = tbl_Cronograma.objects.filter(
                    id_ccpp=ccpp,
                    id_unidad_id__in=unidades_ids,
                    anios__gt=nuevo
                )
                
                eliminados, _ = cronogramas_eliminar.delete()
                
                logger.info(
                    "Cronogramas eliminados para CCPP %s: total=%s (años > %s)",
                    ccpp.id_ccpp, eliminados, nuevo
                )

            # Caso 2: Incremento de años (Crear los faltantes)
            elif nuevo > original:
                nuevos_registros = []

                for u_id in unidades_ids:
                    # Rango: desde el año siguiente al original hasta el nuevo límite
                    for anio in range(original + 1, nuevo + 1):
                        # Verificar si ya existe
                        existe = tbl_Cronograma.objects.filter(
                            id_ccpp=ccpp,
                            id_unidad_id=u_id,
                            anios=anio
                        ).exists()
                        
                        if not existe:
                            nuevos_registros.append(
                                tbl_Cronograma(
                                    id_ccpp=ccpp, 
                                    id_unidad_id=u_id, 
                                    anios=anio
                                )
                            )

                if nuevos_registros:
                    tbl_Cronograma.objects.bulk_create(nuevos_registros)
                    logger.info(
                        "Cronogramas creados para CCPP %s: total=%s (años %s a %s)",
                        ccpp.id_ccpp, len(nuevos_registros), original + 1, nuevo
                    )
            else:
                logger.info("No hay cambios en cantidad de años para sincronizar")
                    
    except Exception as error:
        logger.exception(
            "Error al sincronizar cronogramas de CCPP %s: %s",
            ccpp.id_ccpp, error
        )
        raise error


#=================================Función para eliminar una CCPP==========================================
@login_required
@csrf_protect
def eliminar_ccpp(request, ccpp_id):
    nombre_ruta_listado = "ccpp"

    try:
        with transaction.atomic():
            # 1. Ajuste de selección: Tu modelo usa id_ccpp como primary_key
            ccpp_actual = get_object_or_404(
                tbl_CCPP.objects.select_for_update(), pk=ccpp_id
            )

            # 2. Obtener conteos para mensaje informativo
            cronogramas_count = tbl_Cronograma.objects.filter(id_ccpp=ccpp_actual).count()
            relaciones_count = tbl_CCPP_Unidad.objects.filter(ccpp=ccpp_actual).count()
            notificaciones_count = tbl_Notificacion.objects.filter(id_ccpp=ccpp_actual).count()

            nombre_ccpp = ccpp_actual.nombre

            # 3. Eliminar archivos físicos primero
            archivos_eliminados = True
            
            # Eliminar imagen
            if ccpp_actual.imagen:
                archivos_eliminados = eliminar_archivo_seguro(ccpp_actual.imagen)
            
            # Eliminar archivo de contrato si existe
            if ccpp_actual.ArchivoContrato:
                archivos_eliminados = archivos_eliminados and eliminar_archivo_seguro(ccpp_actual.ArchivoContrato)

            if not archivos_eliminados:
                logger.warning(f"Algunos archivos no pudieron eliminarse para CCPP {ccpp_id}")
                messages.warning(request, "Algunos archivos no pudieron eliminarse completamente.")

            # 4. Eliminar la CCPP (esto eliminará en cascada los registros relacionados)
            ccpp_actual.delete()

            logger.info(
                "CCPP eliminada: ID=%s, Nombre='%s' por usuario %s",
                ccpp_id, nombre_ccpp, request.user.username,
            )

            # 5. Construcción del mensaje de éxito
            mensaje = f"CCPP '{nombre_ccpp}' eliminada exitosamente."
            total_deps = cronogramas_count + relaciones_count + notificaciones_count
            
            if total_deps > 0:
                detalles = []
                if cronogramas_count > 0: 
                    detalles.append(f"{cronogramas_count} cronograma(s)")
                if relaciones_count > 0: 
                    detalles.append(f"{relaciones_count} unidad(es) vinculada(s)")
                if notificaciones_count > 0: 
                    detalles.append(f"{notificaciones_count} notificación(es)")
                mensaje += f" Se eliminaron en cascada: {', '.join(detalles)}."

            messages.success(request, mensaje)
            return redirect(reverse(nombre_ruta_listado))

    except tbl_CCPP.DoesNotExist:
        logger.warning("Intento de eliminar CCPP inexistente: %s", ccpp_id)
        messages.error(request, "La CCPP ya no existe en el sistema.")
        return redirect(reverse(nombre_ruta_listado))

    except Exception as error:
        logger.exception("Error al eliminar CCPP %s: %s", ccpp_id, error)
        messages.error(request, "No se pudo eliminar la CCPP debido a un error de integridad o de base de datos.")
        return redirect(reverse(nombre_ruta_listado))


#=================================Función para clonar una CCPP==========================================
@login_required
@csrf_protect
def clonar_ccpp(request, ccpp_id):
    RUTA_EXITO = 'ccpp'
    
    if request.method != 'POST':
        messages.error(request, "Método no permitido para esta acción.")
        return redirect(reverse(RUTA_EXITO))
    
    try:
        ccpp_original = get_object_or_404(tbl_CCPP, pk=ccpp_id)
    except Exception:
        messages.error(request, "La CCPP original no existe o no se pudo cargar.")
        return redirect(reverse(RUTA_EXITO))
    
    try:
        with transaction.atomic():
            # 1. Obtener relaciones originales
            relaciones_originales = list(tbl_CCPP_Unidad.objects.filter(ccpp=ccpp_original))
            unidades_ids = [rel.unidad_id for rel in relaciones_originales]
            
            # 2. Crear el clon de la CCPP con TODOS los campos
            ccpp_clon = tbl_CCPP.objects.create(
                nombre=f"CLON de {ccpp_original.nombre}",
                fecha_entrega=ccpp_original.fecha_entrega,
                cantidad_anios=ccpp_original.cantidad_anios,
                direccion=ccpp_original.direccion,
                habilitada=ccpp_original.habilitada,
                
                # Campos de contacto
                operario_comunidad=ccpp_original.operario_comunidad,
                empresa_especializada=ccpp_original.empresa_especializada,
                administracion_edificio=ccpp_original.administracion_edificio,
                tecnico_especialista=ccpp_original.tecnico_especialista,
                tecnico_cabecera=ccpp_original.tecnico_cabecera,
                copia_oculta=ccpp_original.copia_oculta,
                
                # Campos de notas (agregados)
                nota_adaptacionLE=ccpp_original.nota_adaptacionLE,
                nota_controlVerificacion=ccpp_original.nota_controlVerificacion,
                nota_emisionInforme=ccpp_original.nota_emisionInforme,
                nota_visitaTecnico=ccpp_original.nota_visitaTecnico,
                nota_asistenciaReunion=ccpp_original.nota_asistenciaReunion,
                nota_ampliacionEdificio=ccpp_original.nota_ampliacionEdificio,
                nota_otrosConceptos=ccpp_original.nota_otrosConceptos,
                
                # Campos de contrato (sin archivo)
                FechaContrato=ccpp_original.FechaContrato,
                FechaInicioControl=ccpp_original.FechaInicioControl,
                CantViviendas=ccpp_original.CantViviendas,
                LibroEdificio=ccpp_original.LibroEdificio,
                estado=ccpp_original.estado,
                NumeroContrato=ccpp_original.NumeroContrato,
                # NO clonamos ArchivoContrato por seguridad
                
                # Referencia de clonación
                clon_ccpp=str(ccpp_original.id_ccpp),
                # NO clonar imagen por defecto
            )
            
            # 3. Copiar relaciones de unidades
            if relaciones_originales:
                nuevas_relaciones = [
                    tbl_CCPP_Unidad(ccpp=ccpp_clon, unidad=relacion.unidad)
                    for relacion in relaciones_originales
                ]
                tbl_CCPP_Unidad.objects.bulk_create(nuevas_relaciones)
                logger.info(f"Copiadas {len(nuevas_relaciones)} relaciones de unidades")
            
            # 4. Crear cronogramas para el clon
            cronogramas_a_crear = []
            if unidades_ids and ccpp_clon.cantidad_anios:
                rango_anios = range(ccpp_clon.cantidad_anios + 1)
                
                for anio in rango_anios:
                    for unidad_id in unidades_ids:
                        cronogramas_a_crear.append(
                            tbl_Cronograma(
                                id_ccpp=ccpp_clon,
                                id_unidad_id=unidad_id,
                                anios=anio
                            )
                        )
                
                if cronogramas_a_crear:
                    tbl_Cronograma.objects.bulk_create(cronogramas_a_crear)
                    logger.info(f"Creados {len(cronogramas_a_crear)} cronogramas")
            
            logger.info(
                f"CCPP clonada exitosamente: {ccpp_original.id_ccpp} -> {ccpp_clon.id_ccpp} - "
                f"Usuario: {request.user.username}"
            )
        
        messages.success(
            request,
            f"CCPP '{ccpp_original.nombre}' clonada exitosamente. "
            f"Nuevo ID: CCPP{ccpp_clon.id_ccpp:03d}"
        )
        
        return redirect('editar_ccpp', ccpp_id=ccpp_clon.pk)
        
    except IntegrityError as e:
        logger.error(f"Error de integridad al clonar CCPP: {e}")
        messages.error(
            request,
            "Error de integridad de datos. La operación fue revertida."
        )
        
    except Exception as error:
        logger.exception(f"Error inesperado al clonar la CCPP: {error}")
        messages.error(
            request,
            "Ocurrió un error inesperado al clonar la CCPP."
        )
    
    return redirect(reverse(RUTA_EXITO))



"""
Gestionar unidades asignadas a una CCPP
"""
@login_required
@csrf_protect
def gestionUnidades_ccpp(request, ccpp_id):
    ccpp = get_object_or_404(tbl_CCPP, pk=ccpp_id)

    if request.method == 'POST':
        try:
            # Obtener IDs seleccionados del formulario
            selected_unit_ids = set()
            raw_selected_ids = request.POST.getlist('selected_units')
            
            for uid in raw_selected_ids:
                try:
                    selected_unit_ids.add(int(uid))
                except ValueError:
                    continue
            
            # Obtener IDs actualmente asignados
            current_unit_ids = set(
                tbl_CCPP_Unidad.objects.filter(ccpp=ccpp).values_list('unidad_id', flat=True)
            )

            # Calcular diferencias
            unidades_a_eliminar = current_unit_ids - selected_unit_ids
            unidades_a_agregar = selected_unit_ids - current_unit_ids

            with transaction.atomic():
                # Eliminar unidades y sus cronogramas
                if unidades_a_eliminar:
                    # Eliminar cronogramas primero
                    tbl_Cronograma.objects.filter(
                        id_ccpp=ccpp,
                        id_unidad_id__in=unidades_a_eliminar
                    ).delete()
                    
                    # Eliminar relaciones
                    tbl_CCPP_Unidad.objects.filter(
                        ccpp=ccpp,
                        unidad_id__in=unidades_a_eliminar
                    ).delete()

                # Agregar nuevas unidades
                if unidades_a_agregar:
                    nuevas_relaciones = []
                    nuevos_cronogramas = []
                    
                    # Verificar que las unidades existan
                    unidades_existentes = tbl_Unidad.objects.filter(id_unidad__in=unidades_a_agregar)
                    
                    # Crear relaciones
                    for unidad in unidades_existentes:
                        nuevas_relaciones.append(
                            tbl_CCPP_Unidad(ccpp=ccpp, unidad=unidad)
                        )
                        
                        # Crear cronogramas para todos los años
                        for anio in range(ccpp.cantidad_anios + 1):
                            nuevos_cronogramas.append(
                                tbl_Cronograma(
                                    id_ccpp=ccpp,
                                    id_unidad=unidad,
                                    anios=anio
                                )
                            )
                    
                    # Guardar en lotes
                    if nuevas_relaciones:
                        tbl_CCPP_Unidad.objects.bulk_create(nuevas_relaciones)
                    
                    if nuevos_cronogramas:
                        tbl_Cronograma.objects.bulk_create(nuevos_cronogramas)

            messages.success(request, f'Unidades actualizadas correctamente para {ccpp.nombre}')
            return redirect('gestionUnidades_ccpp', ccpp_id=ccpp_id)

        except Exception as e:
            logger.exception(f"Error al gestionar unidades de CCPP {ccpp_id}: {e}")
            messages.error(request, f'Error al procesar la solicitud: {str(e)}')

    # GET: Mostrar formulario
    unidades = tbl_Unidad.objects.all().order_by('orden')
    assigned_unit_ids = list(
        tbl_CCPP_Unidad.objects.filter(ccpp=ccpp).values_list('unidad_id', flat=True)
    )

    context = {
        'ccpp': ccpp,
        'unidades': unidades,
        'assigned_unit_ids': assigned_unit_ids,
        'valores_unidad': tbl_Unidad.objects.values_list('unidad', flat=True).distinct().order_by('unidad'),
        'valores_capitulo': tbl_Unidad.objects.values_list('capitulo', flat=True).distinct().order_by('capitulo'),
        'valores_observacion': tbl_Unidad.objects.values_list('observacion', flat=True).distinct().order_by('observacion'),
        'valores_doc': tbl_Unidad.objects.values_list('doc', flat=True).distinct().order_by('doc'),
    }

    return render(request, 'dataMaestra/ccpp/gestionUnidades_ccpp.html', context)









