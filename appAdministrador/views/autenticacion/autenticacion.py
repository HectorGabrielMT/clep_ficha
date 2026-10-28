from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.conf import settings





from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from appAdministrador.models import UserProfile


def inicio_sesion(request):
    """
    Vista para manejar el inicio de sesión de usuarios.
    Redirige a los Observadores a su CCPP asignada y a Staff/Admins al panel principal.
    """
    
    # 1. Si el usuario ya está autenticado, redirigir según su rol
    if request.user.is_authenticated:
        if not request.user.is_staff and not request.user.is_superuser:
            try:
                id_ccpp = request.user.profile.ccpp_asignada.id
                return redirect('gestion_ccpp', id_ccpp=id_ccpp)
            except (UserProfile.DoesNotExist, AttributeError):
                return redirect('panel_principal')
        return redirect('panel_principal')

    if request.method == 'POST':
        nombre_usuario = request.POST.get('usuario', '').strip()
        clave = request.POST.get('clave', '').strip()
        recordarme = request.POST.get('recordarme') == 'on'

        # 2. Validar campos vacíos
        if not nombre_usuario or not clave:
            messages.error(request, "Debes completar ambos campos.")
            return render(request, 'autenticacion/inicio_sesion.html', {'usuario_val': nombre_usuario})

        # 3. Autenticar usuario
        usuario_autenticado = authenticate(request, username=nombre_usuario, password=clave)

        if usuario_autenticado is not None:
            login(request, usuario_autenticado)
            messages.success(request, f"Bienvenido, {usuario_autenticado.username}.")

            # 4. Lógica de Redirección por Rol
            # Si NO es staff ni superuser, es un "Observador"
            if not usuario_autenticado.is_superuser:
                try:
                    perfil = usuario_autenticado.profile
                    if perfil.ccpp_asignada:
                        # Redirige a la URL: cronograma/<int:id_ccpp>/
                        return redirect('gestion_ccpp', id_ccpp=perfil.ccpp_asignada.id_ccpp)
                    else:
                        messages.warning(request, "No tienes un CCPP asignado. Contacta al administrador.")
                        return redirect('panel_principal')
                except UserProfile.DoesNotExist:
                    messages.error(request, "El perfil de usuario no existe.")
                    return redirect('panel_principal')

            # Redirección por defecto para Administradores y Supervisores
            return redirect('panel_principal')
        
        else:
            # 5. Manejo de credenciales incorrectas
            messages.error(request, "Usuario o contraseña incorrectos.")
            return render(request, 'autenticacion/inicio_sesion.html', {'usuario_val': nombre_usuario})

    return render(request, 'autenticacion/inicio_sesion.html')







def cerrar_sesion(request):
    """
    Vista para cerrar la sesión del usuario actual.
    
    Realiza logout y muestra mensaje apropiado según el estado de autenticación.
    """
    
    if request.user.is_authenticated:
        nombre_usuario = request.user.username
        logout(request)
        messages.success(
            request,
            f"Hasta pronto, {nombre_usuario}. Has cerrado sesión correctamente."
        )
    else:
        messages.info(request, "No has iniciado sesión.")

    return redirect('login')


