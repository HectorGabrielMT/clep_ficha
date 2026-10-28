from django.urls import path
from appAdministrador.views.dataMaestra import ordenar_capitulos, unidad, CCPP, correo, inspeccion, confi_correo
from appAdministrador.views.gestion import cronograma, pago
from appAdministrador.views.autenticacion import autenticacion, usuarios
from appAdministrador.views.reporte import reporte_noti, reporte_insp, report
import appAdministrador.views.moduloGlobal as views 


from django.contrib.auth.decorators import user_passes_test
solo_superuser = user_passes_test(lambda u: u.is_active and u.is_superuser)
permitir_admin_y_staff = user_passes_test(
    lambda u: u.is_active and (u.is_superuser or u.is_staff)
)
urlpatterns = [

    #====================================================================
    #GESTION
    #====================================================================


    # ======================== REPORTES ==========================

    path('reporte/notificaciones/<int:ccpp_id>/<int:anio_relativo>/<int:mes_inicio>/<int:mes_fin>/<str:mostrar_remitentes>/<str:mostrar_respuesta>/', solo_superuser(reporte_noti.reporte_notificaciones_ccpp_pdf), name='reporte_notificaciones_ccpp'),
    path('reporte/inspecciones/<int:ccpp_id>/<int:anio>/', solo_superuser(reporte_insp.reporte_inspecciones_ccpp_pdf), name='reporte_inspecciones_pdf'),    
    path('reporte/libro-fichas/', solo_superuser(report.generar_pdf_inspecciones), name='reporte_fichas_pdf'),



    #=============================== CRONOGRAMA =================================

    path('cronograma/<int:id_ccpp>/', cronograma.cronograma_ccpp, name='gestion_ccpp'),
    path('cronograma/<int:id_ccpp>/guardar-celda/', cronograma.guardar_celda_cronograma, name='guardar_celda_cronograma'),
    

    # ========================PAGOS==========================

    path('gestion-pagos/<int:id_ccpp>/', solo_superuser(pago.gestion_pagos), name='panel_pagos'),

    # ========================GLOBAl==========================

    path('retroceder/', views.retroceder, name='retroceder'),
    path('', solo_superuser(cronograma.vista_panel_principal) , name='panel_principal'),




    #====================================================================
    #DATA MAESTRA
    #====================================================================



     # ======================== CCPP - UNIDAD ==========================     

    path('ccpp/', solo_superuser(CCPP.vista_panel_ccpp), name='ccpp'),
    path('ccpp/nueva/', solo_superuser(CCPP.nueva_ccpp), name='nueva_ccpp'),
    path('ccpp/editar/<int:ccpp_id>/', solo_superuser(CCPP.editar_ccpp), name='editar_ccpp'),
    path('ccpp/eliminar/<int:ccpp_id>/', solo_superuser(CCPP.eliminar_ccpp), name='eliminar_ccpp'),
    path('ccpp/clonar/<int:ccpp_id>/', solo_superuser(CCPP.clonar_ccpp), name='clonar_ccpp'),
    path('ccpp/unidades/<int:ccpp_id>/', solo_superuser(CCPP.gestionUnidades_ccpp), name='gestionUnidades_ccpvp'),



    path('unidades/<int:id_ccpp>/', solo_superuser(unidad.gestionar_unidades_ccpp), name='gestionUnidades_ccpp'),
    path('unidades/<int:id_ccpp>/<str:modo>/', solo_superuser(unidad.gestionar_unidades_ccpp), name='gestionUnidades_ccpp_modo'),
    path('unidades/nueva/<int:id_ccpp>/', solo_superuser(unidad.nueva_unidad), name='nueva_unidad'),
    path('unidades/editar/<int:unidad_id>/<int:id_ccpp>/', solo_superuser(unidad.editar_unidad), name='editar_unidad'),
    path('unidades/eliminar/<int:unidad_id>/<int:id_ccpp>/', solo_superuser(unidad.eliminar_unidad), name='eliminar_unidad'),     
    # Gestión de Capítulos
    path('capitulos/editar/<int:id_ccpp>/', solo_superuser(unidad.editar_capitulo), name='editar_capitulo'),


    # ========================CORREO==========================

    path('correo/plantilla/', solo_superuser(correo.correo), name='correo'),

    path('configuracion/email/actualizar/', solo_superuser(confi_correo.actualizar_configuracion_email), name='actualizar_configuracion_email'),


    # ========================ORDENAR CAPITULOS==========================

    path('ordenar_capitulos/', solo_superuser(ordenar_capitulos.ordenar_capitulos), name='ordenar_capitulos'),


     # ========================INSPECCIONES==========================
    path('inspecciones/', solo_superuser(inspeccion.vista_inspecciones), name='inspecciones'),
    path('inspecciones/editar/<int:inspeccion_id>/', solo_superuser(inspeccion.editar_inspeccion), name='editar_inspeccion'),


    # ========================AUTENTICACION==========================
    path('autenticacion/', autenticacion.inicio_sesion , name='login'),
    path('cerrar_sesion/',autenticacion.cerrar_sesion, name='cerrar_sesion'),


     # ========================USUARIOS==========================
    path('usuarios/', solo_superuser(usuarios.vista_panel_usuarios), name='panel_usuarios'),
    path('usuarios/crear/', solo_superuser(usuarios.crear_usuario), name='crear_usuario'),
    path('usuarios/editar/<int:usuario_id>/', solo_superuser(usuarios.editar_usuario), name='editar_usuario'),
    path('usuarios/eliminar/<int:usuario_id>/', solo_superuser(usuarios.eliminar_usuario), name='eliminar_usuario'),


     # ========================PAGOS==========================
     
    path('gestion-pagos/<int:id_ccpp>/', solo_superuser(pago.gestion_pagos), name='panel_pagos'),


]