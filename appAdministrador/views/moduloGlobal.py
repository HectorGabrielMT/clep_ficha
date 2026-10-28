from django.shortcuts import redirect
from django.contrib.auth.decorators import user_passes_test



def retroceder(request):
    historial = request.session.get('historial_personalizado', [])
    print("1")
    if len(historial) > 1:
        historial.pop() 
        url_anterior = historial.pop() 
        print("2")
        request.session['historial_personalizado'] = historial
        
        return redirect(url_anterior)
    
    return redirect('panel_principal')








def es_administrador_o_staff(usuario):
    """
    Verifica si el usuario tiene permisos de staff o es superusuario.
    """
    return usuario.is_active and (usuario.is_staff or usuario.is_superuser)

validar_permisos = user_passes_test(
    es_administrador_o_staff, 
    login_url=None
)