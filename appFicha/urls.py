from django.urls import path
from . import views


from django.contrib.auth.decorators import user_passes_test
solo_superuser = user_passes_test(lambda u: u.is_active and u.is_superuser)
permitir_admin_y_staff = user_passes_test(
    lambda u: u.is_active and (u.is_superuser or u.is_staff)
)
urlpatterns = [



    # ======================== FICHAS ==========================

    path('unidad/<int:ccpp_id>/<int:unidad_id>/<int:origen>/fichas/', views.vista_panel_fichas, name='panel_fichas'),
    path('unidad/<int:unidad_id>/ficha/nueva/<int:ccpp_id>/<int:origen>/', views.gestionar_ficha, name='nueva_ficha'),
    path('ficha/<int:ficha_id>/editar/<int:ccpp_id>/<int:origen>/', views.gestionar_ficha, name='editar_ficha'),
    path('ficha/<int:ficha_id>/eliminar/<int:ccpp_id>/<int:origen>/', views.eliminar_ficha, name='eliminar_ficha'),
    path('ficha/pdf/<int:ficha_id>/<int:ccpp_id>/<str:descargar_directo>/', views.exportar_ficha_pdf, name='exportar_ficha_pdf'),


    path(
        'configuracion-ficha/guardar/', 
        views.guardar_configuracion_ficha, 
        name='guardar_configuracion_ficha'
    ),


]