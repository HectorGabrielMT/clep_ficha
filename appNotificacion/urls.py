from django.urls import path
from django.contrib.auth.decorators import user_passes_test

from appNotificacion.views import noti_periodo, noti_unidad, unidad_ccpp

from appAdministrador.views.gestion.cronograma import guardar_celda_cronograma


permitir_admin_y_staff = user_passes_test(
    lambda u: u.is_active and (u.is_superuser or u.is_staff)
)
solo_superuser = user_passes_test(
    lambda u: u.is_active and u.is_superuser
)

urlpatterns = [

    # ── Gestión de notificaciones ─────────────────────────────────────────────
    path(
        'notificaciones/<int:ccpp_id>/',
        permitir_admin_y_staff(noti_periodo.gestion_notificaciones),
        name='gestion_notificaciones',
    ),
    path(
        'notificaciones/<int:ccpp_id>/auto/<int:anio>/<str:mes>/<int:unidad_id>/',
        permitir_admin_y_staff(noti_periodo.gestion_notificaciones_auto),
        name='gestion_notificaciones_auto',
    ),
    path('notificaciones/<int:ccpp_id>/guardar/', noti_periodo.guardar_notificacion, name='guardar_notificacion'),

    # ── Eliminaciones ─────────────────────────────────────────────────────────
    path(
        'notificaciones/eliminar-documento/<int:documento_id>/',
        permitir_admin_y_staff(noti_periodo.eliminar_documento),
        name='eliminar_documento',
    ),
    path(
        'notificaciones/eliminar-respuesta/<int:notificacion_id>/',
        permitir_admin_y_staff(noti_periodo.eliminar_respuesta),
        name='eliminar_respuesta',
    ),
    path(
        'notificaciones/eliminar-notificacion/<int:notificacion_id>/',
        permitir_admin_y_staff(noti_periodo.eliminar_notificacion),
        name='eliminar_notificacion',
    ),

    # ── Correo manual ─────────────────────────────────────────────────────────
    path(
        'get-email-template/',
        permitir_admin_y_staff(noti_periodo.abrir_formulario_correo),
        name='get_email_template',
    ),
    path(
        'enviar-correo/',
        permitir_admin_y_staff(noti_periodo.enviar_correo),
        name='enviar_correo',
    ),

    # ── Ficha PDF ─────────────────────────────────────────────────────────────
    path(
        'fichas/<int:ficha_id>/pdf/<int:ccpp_id>/<str:descargar_directo>/',
        permitir_admin_y_staff(noti_periodo.exportar_ficha_pdf),
        name='exportar_ficha_pdf',
    ),


path('ccpp-unidad/fichas/', unidad_ccpp.obtener_fichas_unidad, name='obtener_fichas_unidad'),
path('ccpp-unidad/asignar-ficha/', unidad_ccpp.asignar_ficha_unidad, name='asignar_ficha_unidad'),


    path(
        'notificaciones/unidad/<int:ccpp_id>/<int:unidad_id>/',
        permitir_admin_y_staff(noti_unidad.gestion_notificaciones_unidad),
        name='gestion_notificaciones_unidad',
    ),
    path(
        'notificaciones/unidad/<int:ccpp_id>/<int:unidad_id>/guardar/',
        permitir_admin_y_staff(noti_unidad.guardar_notificaciones_unidad),
        name='guardar_notificaciones_unidad',
    ),
    path(
        'notificaciones/unidad/eliminar/<int:notificacion_id>/',
        permitir_admin_y_staff(noti_unidad.eliminar_notificacion_unidad),
        name='eliminar_notificacion_unidad',
    ),



    path(
        'cronograma-unidad/guardar-celda/<int:id_ccpp>/',
        permitir_admin_y_staff(guardar_celda_cronograma),
        name='',
    ),
]