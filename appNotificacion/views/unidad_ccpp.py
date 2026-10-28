"""
Vistas para la gestión de la ficha vinculada a una relación CCPP - Unidad.
Usadas por el modal autónomo includes/modal_SeleccionarUnidad.html.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from appAdministrador.models import tbl_CCPP, tbl_CCPP_Unidad, tbl_Ficha, tbl_Unidad

logger = logging.getLogger(__name__)


@login_required
@require_GET
def obtener_fichas_unidad(request):
    """
    Devuelve las fichas disponibles para una unidad y la ficha actualmente
    vinculada (si existe) en tbl_CCPP_Unidad para el CCPP indicado.
    """
    id_ccpp = request.GET.get('id_ccpp')
    id_unidad = request.GET.get('id_unidad')

    if not id_ccpp or not id_unidad:
        return JsonResponse({'success': False, 'error': 'Parámetros incompletos.'}, status=400)

    try:
        unidad = get_object_or_404(tbl_Unidad, id_unidad=id_unidad)

        fichas = tbl_Ficha.objects.filter(
            doc_unidad__id_unidad=unidad.id_unidad
        ).order_by('titulo')

        relacion = tbl_CCPP_Unidad.objects.filter(
            ccpp_id=id_ccpp, unidad_id=id_unidad
        ).select_related('ficha').first()

        ficha_actual_id = relacion.ficha_id if relacion and relacion.ficha_id else None

        return JsonResponse({
            'success': True,
            'unidad': unidad.unidad,
            'fichas': [{'id': f.id, 'titulo': f.titulo} for f in fichas],
            'ficha_actual_id': ficha_actual_id,
        })

    except Exception as exc:
        logger.error(
            "Error al obtener fichas de unidad id_ccpp=%s id_unidad=%s: %s",
            id_ccpp, id_unidad, exc
        )
        return JsonResponse({
            'success': False,
            'error': 'No se pudieron cargar las fichas de la unidad.',
        }, status=500)


@login_required
@require_POST
def asignar_ficha_unidad(request):
    """
    Asigna (o quita) la ficha vinculada a una relación CCPP - Unidad.
    Si la relación no existe todavía, se crea.
    """
    id_ccpp = request.POST.get('id_ccpp')
    id_unidad = request.POST.get('id_unidad')
    id_ficha = request.POST.get('id_ficha') or None

    if not id_ccpp or not id_unidad:
        return JsonResponse({'success': False, 'error': 'Parámetros incompletos.'}, status=400)

    if id_ficha and not str(id_ficha).isdigit():
        return JsonResponse({'success': False, 'error': 'Ficha inválida.'}, status=400)

    try:
        with transaction.atomic():
            ccpp = get_object_or_404(tbl_CCPP, id_ccpp=id_ccpp)
            unidad = get_object_or_404(tbl_Unidad, id_unidad=id_unidad)

            ficha = None
            if id_ficha:
                # Se valida que la ficha realmente pertenezca a esta unidad
                ficha = get_object_or_404(
                    tbl_Ficha, pk=id_ficha, doc_unidad__id_unidad=unidad.id_unidad
                )

            relacion, _creada = tbl_CCPP_Unidad.objects.select_for_update().get_or_create(
                ccpp=ccpp, unidad=unidad,
                defaults={'ficha': ficha},
            )
            relacion.ficha = ficha
            relacion.save(update_fields=['ficha'])

        return JsonResponse({
            'success': True,
            'ficha_id': ficha.id if ficha else None,
            'ficha_titulo': ficha.titulo if ficha else None,
        })

    except Exception as exc:
        logger.error(
            "Error al asignar ficha id_ccpp=%s id_unidad=%s id_ficha=%s: %s",
            id_ccpp, id_unidad, id_ficha, exc
        )
        return JsonResponse({
            'success': False,
            'error': 'No se pudo asignar la ficha a la unidad.',
        }, status=500)