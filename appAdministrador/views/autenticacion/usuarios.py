# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator

# views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from appAdministrador.models import UserProfile, tbl_CCPP



import logging
from django.db import transaction, DatabaseError
from django.contrib import messages

logger = logging.getLogger(__name__)

def es_administrador(user):
    return user.is_superuser


def obtener_o_crear_perfil(usuario):
    try:
        return UserProfile.objects.get(user=usuario)
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=usuario)


@login_required
def crear_usuario(request):
    ccpps = tbl_CCPP.objects.filter(habilitada=True).order_by("nombre")

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()
        rol = request.POST.get("rol", "observador")
        is_active = request.POST.get("is_active") == "on"
        ccpp_id = request.POST.get("ccpp_asignada", "").strip()

        contexto = {
            "editar": False,
            "ccpps": ccpps,
            "usuario": {
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "email": email,
                "is_active": is_active,
                "is_staff": rol in ["supervisor", "admin"],
                "is_superuser": rol == "admin",
            },
            "errores": {},
        }

        if not username:
            contexto["errores"]["username"] = "El nombre de usuario es requerido."
        elif len(username) > 10:
            contexto["errores"]["username"] = "El nombre de usuario no puede tener más de 10 caracteres."
        elif User.objects.filter(username=username).exists():
            contexto["errores"]["username"] = "El nombre de usuario ya existe."

        if not password:
            contexto["errores"]["password"] = "La contraseña es requerida."

        if password and password != confirm_password:
            contexto["errores"]["confirm_password"] = "Las contraseñas no coinciden."

        if contexto["errores"]:
            messages.error(request, "Hay errores en el formulario, por favor corrígelos.")
            return render(request, "autenticacion/usuarios/formulario_usuario.html", contexto)

        try:
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=is_active,
                )

                if rol == "admin":
                    usuario.is_superuser = True
                    usuario.is_staff = True
                elif rol == "supervisor":
                    usuario.is_superuser = False
                    usuario.is_staff = True
                else:
                    usuario.is_superuser = False
                    usuario.is_staff = False

                usuario.save()

                if rol in ["observador", "supervisor"] and ccpp_id:
                    try:
                        ccpp = tbl_CCPP.objects.get(id_ccpp=ccpp_id)
                        perfil = obtener_o_crear_perfil(usuario)
                        perfil.ccpp_asignada = ccpp
                        perfil.save()
                    except tbl_CCPP.DoesNotExist:
                        logger.warning(f"CCPP con id {ccpp_id} no existe.")
                        messages.warning(request, "La CCPP asignada no existe, se omitió la asignación.")

                messages.success(request, f"Usuario '{username}' creado correctamente.")
                return redirect("panel_usuarios")

        except DatabaseError as db_err:
            logger.error(f"Error de base de datos al crear usuario: {db_err}")
            messages.error(request, "Error de base de datos al crear el usuario.")
            return render(request, "autenticacion/usuarios/formulario_usuario.html", contexto)
        except Exception as e:
            logger.error(f"Error inesperado al crear usuario: {e}")
            contexto["errores"]["general"] = f"Ocurrió un error inesperado: {str(e)}"
            messages.error(request, "Ocurrió un error inesperado al crear el usuario.")
            return render(request, "autenticacion/usuarios/formulario_usuario.html", contexto)

    return render(
        request,
        "autenticacion/usuarios/formulario_usuario.html",
        {
            "editar": False,
            "ccpps": ccpps,
            "usuario": {"is_active": True},
            "errores": {},
        },
    )





@login_required
@transaction.atomic
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(User, id=usuario_id)
    ccpps = tbl_CCPP.objects.filter(habilitada=True).order_by("nombre")
    perfil, created = UserProfile.objects.get_or_create(user=usuario)

    if request.method == "POST":
        # CAPTURA DE DATOS - Asegúrate que coincidan con el 'name' del HTML
        username = request.POST.get("username", "").strip() # <--- FALTABA ESTO
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        rol = request.POST.get("rol", "observador")
        is_active = request.POST.get("is_active") == "on"
        new_password = request.POST.get("new_password", "").strip()
        confirm_new_password = request.POST.get("confirm_new_password", "").strip()
        ccpp_id = request.POST.get("ccpp_asignada", "").strip()

        errores = {}

        # Validaciones
        if not username:
            errores["username"] = "El nombre de usuario es obligatorio."
        elif User.objects.filter(username=username).exclude(id=usuario.id).exists():
            errores["username"] = "Este nombre de usuario ya está en uso."

        if email and User.objects.filter(email=email).exclude(id=usuario.id).exists():
            errores["email"] = "El correo electrónico ya está registrado."

        if new_password and new_password != confirm_new_password:
            errores["confirm_new_password"] = "Las contraseñas no coinciden."

        if errores:
            return render(request, "autenticacion/usuarios/formulario_usuario.html", {
                "usuario": usuario, "editar": True, "ccpps": ccpps, "errores": errores
            })

        try:
            # 1. Actualizar objeto User
            usuario.username = username
            usuario.first_name = first_name
            usuario.last_name = last_name
            usuario.email = email
            usuario.is_active = is_active

            # Lógica de Roles
            if rol == "admin":
                usuario.is_superuser = True
                usuario.is_staff = True
            elif rol == "supervisor":
                usuario.is_superuser = False
                usuario.is_staff = True
            else:
                usuario.is_superuser = False
                usuario.is_staff = False

            if new_password:
                usuario.set_password(new_password)
            
            usuario.save()

            # 2. Actualizar Perfil (CCPP)
            if rol in ["observador", "supervisor"] and ccpp_id:
                # Buscamos por id_ccpp porque es lo que envías en el value del HTML
                perfil.ccpp_asignada = tbl_CCPP.objects.filter(id_ccpp=ccpp_id).first()
            else:
                perfil.ccpp_asignada = None
            
            perfil.save()

            messages.success(request, f"Usuario '{usuario.username}' actualizado correctamente.")
            return redirect("panel_usuarios")

        except Exception as e:
            messages.error(request, f"Error al guardar: {str(e)}")

    return render(request, "autenticacion/usuarios/formulario_usuario.html", {
        "usuario": usuario,
        "editar": True,
        "ccpps": ccpps,
        "errores": {}
    })





@login_required
def eliminar_usuario(request, usuario_id):
    """Elimina un usuario con confirmación previa."""
    usuario = get_object_or_404(User, id=usuario_id)
    
    # No permitir eliminarse a sí mismo
    if usuario == request.user:
        return redirect('panel_usuarios')
    
    try:
        # Eliminar perfil si existe
        try:
            perfil = UserProfile.objects.get(user=usuario)
            perfil.delete()
        except UserProfile.DoesNotExist:
            pass
        
        usuario.delete()
        
    except Exception as e:
        pass
    
    return redirect('panel_usuarios')





@login_required
def vista_panel_usuarios(request):
    usuarios = User.objects.all().order_by('date_joined')
    
    total_usuarios = usuarios.count()
    usuarios_activos = usuarios.filter(is_active=True).count()
    
    context = {
        'usuarios': usuarios,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
    }
    return render(request, 'autenticacion/usuarios/lista_usuarios.html', context)
