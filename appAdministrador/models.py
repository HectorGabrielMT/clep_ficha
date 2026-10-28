from django.db import models
import logging
logger = logging.getLogger(__name__)
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User






class tbl_inspeccion(models.Model):
    codigo_inspeccion = models.CharField(max_length=100, verbose_name="Código de Inspección", unique=True)
    nombre_inspeccion = models.CharField(max_length=255, verbose_name="Nombre de la Inspección")
    descripcion_inspeccion = models.CharField(max_length=255,verbose_name="Descripción de la Inspección")
    notificacionA_inspeccion = models.CharField(max_length=255, verbose_name="Notificación")
    color_inspeccion = models.CharField(max_length=10, verbose_name="Color de la Inspección", default="#FFFFFF")



class tbl_CCPP(models.Model):

    id_ccpp = models.AutoField(primary_key=True, verbose_name="ID CCPP")

    nombre = models.CharField(max_length=150, verbose_name="CCPP Residencial")
    fecha_entrega = models.DateField(null=True, blank=True, verbose_name="Fecha de Entrega")
    cantidad_anios = models.IntegerField(default=0, verbose_name="Cantidad de Años")
    direccion = models.CharField(max_length=255, verbose_name="Dirección de la CCPP", blank=True, null=True)
    habilitada = models.BooleanField(default=True, verbose_name="CCPP Habilitada")

    operario_comunidad = models.TextField(verbose_name="Operario Comunidad", blank=True)
    empresa_especializada = models.TextField(verbose_name="Empresa Especializada", blank=True)
    administracion_edificio = models.TextField(verbose_name="Administración del Edificio", blank=True)
    tecnico_especialista = models.TextField(verbose_name="Técnico Especialista", blank=True)
    tecnico_cabecera = models.TextField(verbose_name="Técnico de Cabecera", blank=True)
    copia_oculta = models.TextField(verbose_name="Copia Oculta (Contactos)", blank=True)

    clon_ccpp = models.CharField(max_length=150, verbose_name="Clon", blank=True)
    imagen = models.ImageField(upload_to='imagenes/', null=True, blank=True, verbose_name="Imagen de la ccpp")

    fecha_modificacion = models.DateField(auto_now=True, verbose_name="Fecha de Modificación", null=True, blank=True)

    # Columnas de notas de la tabla tbl_pago
    nota_adaptacionLE = models.TextField(verbose_name="Nota Adaptación LE", blank=True, null=True)
    nota_controlVerificacion = models.TextField(verbose_name="Nota Control y Verificación", blank=True, null=True)
    nota_emisionInforme = models.TextField(verbose_name="Nota Emisión de Informe", blank=True, null=True)
    nota_visitaTecnico = models.TextField(verbose_name="Nota Visita Técnico", blank=True, null=True)
    nota_asistenciaReunion = models.TextField(verbose_name="Nota Asistencia a Reunión", blank=True, null=True)
    nota_ampliacionEdificio = models.TextField(verbose_name="Nota Ampliación de Edificio", blank=True, null=True)
    nota_otrosConceptos = models.TextField(verbose_name="Nota Otros Conceptos", blank=True, null=True)

    # Columnas de Pago
    FechaContrato = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Contrato")
    FechaInicioControl = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Inicio de Control")
    CantViviendas = models.IntegerField(default=0, verbose_name="Cantidad de Viviendas", null=True, blank=True)
    LibroEdificio = models.BooleanField(default=False, verbose_name="Libro del Edificio", null=True, blank=True)
    estado = models.BooleanField(default=True, verbose_name="Estado", null=True, blank=True)
    NumeroContrato = models.CharField(max_length=100, verbose_name="Número de Contrato", blank=True, null=True)
    ArchivoContrato = models.FileField(upload_to='contratos/%Y/%m/%d/', null=True, blank=True, verbose_name="Archivo de Contrato")


    class Meta:
        verbose_name = "CCPP"
        verbose_name_plural = "CCPPs"
        ordering = ['id_ccpp']

    def __str__(self):
        return f"CCPP{self.id_ccpp:03d} - {self.nombre}"


class tbl_Pago(models.Model):
    id_pago = models.AutoField(primary_key=True, verbose_name="ID Pago")
    id_ccpp = models.ForeignKey(tbl_CCPP, on_delete=models.CASCADE, verbose_name="CCPP")
    anio = models.IntegerField(verbose_name="Año")
    mes = models.CharField(max_length=20, verbose_name="Mes")

    AdaptacionLE = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Adaptacion LE")
    ControlVerificacion = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Control y Verificación")
    EmisionInforme = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Emisión de Informe")
    VisitaTecnico = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Visita Técnico")
    AsistenciaReunion = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Asistencia a Reunión")
    AmpliacionEdificio = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Ampliación de Edificio")
    OtrosConceptos = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Otros Conceptos")

    RefFactura = models.CharField(max_length=100, verbose_name="Referencia de Factura")
    ArchivoFactura = models.FileField(upload_to='facturas/%Y/%m/%d/', null=True, blank=True, verbose_name="Archivo de Factura")

    fecha_pago = models.DateField(verbose_name="Fecha de Pago", null=True, blank=True)




class tbl_Unidad(models.Model):

    id_unidad = models.AutoField(primary_key=True, verbose_name="ID Unidad")
    capitulo = models.CharField(max_length=255, verbose_name="Capitulo")
    unidad = models.CharField(max_length=255, verbose_name="Unidad")
    descripcion = models.CharField(max_length=255, verbose_name="Descripcion")
    observacion = models.CharField(max_length=255, verbose_name="Observacion")
    doc = models.CharField(max_length=255, verbose_name="DOC", unique=True,null=True, blank=True)
    orden = models.IntegerField(verbose_name="Orden", default=0)



class tbl_CCPP_Unidad(models.Model):
    id_ccpp_unidad = models.AutoField(primary_key=True, verbose_name="ID CCPP Unidad")
    ccpp = models.ForeignKey(tbl_CCPP, on_delete=models.CASCADE, verbose_name="CCPP")
    unidad = models.ForeignKey(tbl_Unidad, on_delete=models.CASCADE, verbose_name="Unidad")
    ficha = models.ForeignKey('tbl_Ficha', on_delete=models.SET_NULL, null=True, blank=True, related_name='ccpp_unidades', verbose_name="Ficha vinculada")

    class Meta:
        verbose_name = "Relación CCPP - Unidad"
        verbose_name_plural = "Relaciones CCPP - Unidades"
        unique_together = ('ccpp', 'unidad')

    def save(self, *args, **kwargs):
        """
        Si la ficha vinculada cambia (incluyendo desvinculación completa),
        se deben limpiar los controles de ficha ya asignados en las
        notificaciones de esta unidad-ccpp, ya que pertenecen a la ficha
        anterior y dejarían de ser válidos para la nueva situación.
        """
        ficha_anterior_id = None
        if self.pk:
            ficha_anterior_id = (
                tbl_CCPP_Unidad.objects
                .filter(pk=self.pk)
                .values_list('ficha_id', flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if ficha_anterior_id != self.ficha_id:
            tbl_Notificacion.objects.filter(
                id_ccpp_id=self.ccpp_id,
                id_unidad_id=self.unidad_id,
            ).exclude(
                id_ficha_control__id_ficha_id=self.ficha_id
            ).update(id_ficha_control=None)

    def __str__(self):
        return f"{self.ccpp.nombre} - {self.unidad.unidad}"


class tbl_Cronograma(models.Model):

    id_ccpp = models.ForeignKey(tbl_CCPP, on_delete=models.CASCADE, verbose_name="CCPP", db_column='id_ccpp')
    id_unidad = models.ForeignKey(tbl_Unidad, on_delete=models.CASCADE, verbose_name="Unidad", db_column='id_unidad')
    anios = models.IntegerField(verbose_name="Año", db_column='anios')

    nota = models.TextField(verbose_name="Nota", blank=True, null=True)

    enero = models.CharField(max_length=10, null=True, blank=True)
    febrero = models.CharField(max_length=10, null=True, blank=True)
    marzo = models.CharField(max_length=10, null=True, blank=True)
    abril = models.CharField(max_length=10, null=True, blank=True)
    mayo = models.CharField(max_length=10, null=True, blank=True)
    junio = models.CharField(max_length=10, null=True, blank=True)
    julio = models.CharField(max_length=10, null=True, blank=True)
    agosto = models.CharField(max_length=10, null=True, blank=True)
    septiembre = models.CharField(max_length=10, null=True, blank=True)
    octubre = models.CharField(max_length=10, null=True, blank=True)
    noviembre = models.CharField(max_length=10, null=True, blank=True)
    diciembre = models.CharField(max_length=10, null=True, blank=True)



    class Meta:
        verbose_name = "Cronograma"
        verbose_name_plural = "Cronogramas"
        db_table = 'appAdministrador_tbl_cronograma'  # FORZAR NOMBRE DE TABLA
        constraints = [
            models.UniqueConstraint(
                fields=['id_ccpp', 'id_unidad', 'anios'],
                name='unique_cronograma_migracion'
            )
        ]

        indexes = [
            models.Index(fields=['id_ccpp', 'anios'], name='idx_ccpp_anios'),
            models.Index(fields=['id_unidad'], name='idx_cronograma_unidad'),
        ]



class tbl_Ficha(models.Model):

    titulo = models.CharField(max_length=255, verbose_name='Título de la Ficha')
    doc_unidad = models.ForeignKey(tbl_Unidad, to_field='doc', on_delete=models.CASCADE, verbose_name='Unidad Asociada', db_column='doc_unidad')

    precaucion = models.TextField(verbose_name='Precaución')
    prescripcion = models.TextField(verbose_name='Prescripción')
    prohibicion = models.TextField(verbose_name='Prohibición')
    logo = models.ImageField(upload_to='logos_ficha/', null=True, blank=True, verbose_name="Logo")
    foto = models.ImageField(upload_to='imagenes_ficha/', null=True, blank=True, verbose_name="Imagen de anexo")
    fecha_creacion = models.DateField(verbose_name='Fecha', null=True, blank=True)

    ultimo_codigo_control = models.PositiveIntegerField(
        default=0,
        verbose_name='Último código de control'
    )

    class Meta:
        verbose_name = "Ficha"
        verbose_name_plural = "Fichas"
        constraints = [
            models.UniqueConstraint(
                fields=['titulo', 'doc_unidad'],
                name='unique_titulo_unidad'
            )
        ]

    def __str__(self):
        return f"{self.titulo} - {self.doc_unidad}"



from django.db import models, transaction  # asegúrate de tener 'transaction' importado
import logging
logger = logging.getLogger(__name__)


class tbl_FichaControl(models.Model):

    id_ficha_control = models.AutoField(primary_key=True, verbose_name='ID Ficha Control', db_column='id_ficha_control')

    id_ficha = models.ForeignKey(tbl_Ficha, on_delete=models.CASCADE, verbose_name='Ficha Relacionada', db_column='id_ficha', related_name='fichacontrol')
    id_inspeccion = models.ForeignKey(tbl_inspeccion, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Inspección', db_column='id_inspeccion')

    # NUEVO: código correlativo único e inmutable dentro de la ficha (1, 2, 3, ...).
    # No se recicla aunque se elimine un control intermedio.
    codigo_control = models.PositiveIntegerField(
        verbose_name='Código de Control',
        editable=False,   # No aparece en formularios ModelForm, no se puede tocar desde ahí
        null=True,
        blank=True
    )

    periodo = models.CharField(max_length=255, verbose_name='Período Ficha')
    premisa = models.CharField(max_length=255, verbose_name='Premisa Ficha')
    control = models.TextField(verbose_name='Control Ficha')

    ejecutado = models.BooleanField(default=False, verbose_name='Ejecutado')
    opacar = models.BooleanField(default=False, verbose_name='Opacar')
    ocultar = models.BooleanField(default=False, verbose_name='Ocultar')

    documento_temp = models.TextField(
        null=True,
        blank=True,
        verbose_name='Documento temporal borrar'
    )

    class Meta:
        verbose_name = "Ficha Control"
        verbose_name_plural = "Ficha Controles"
        constraints = [
            models.UniqueConstraint(
                fields=['id_ficha', 'codigo_control'],
                name='unique_codigo_control_por_ficha'
            )
        ]

    def save(self, *args, **kwargs):
        """
        Garantiza que codigo_control:
        - Se asigne UNA sola vez, al crear el control (correlativo, nunca se repite).
        - Sea inmutable en ediciones posteriores, sin importar lo que llegue en self.codigo_control.
        """
        if self.pk:
            # EDICIÓN: se blinda el código actual, ignorando cualquier valor externo.
            codigo_actual = (
                tbl_FichaControl.objects
                .filter(pk=self.pk)
                .values_list('codigo_control', flat=True)
                .first()
            )
            self.codigo_control = codigo_actual
            super().save(*args, **kwargs)
        else:
            # CREACIÓN: se toma y actualiza el contador de forma atómica para evitar
            # condiciones de carrera si se crean varios controles al mismo tiempo.
            with transaction.atomic():
                ficha_bloqueada = tbl_Ficha.objects.select_for_update().get(pk=self.id_ficha_id)
                ficha_bloqueada.ultimo_codigo_control += 1
                ficha_bloqueada.save(update_fields=['ultimo_codigo_control'])

                self.codigo_control = ficha_bloqueada.ultimo_codigo_control
                super().save(*args, **kwargs)

    def __str__(self):
        return f"Control #{self.codigo_control} - {self.id_ficha.titulo}"






class ConfiguracionFicha(models.Model):
    """
    Modelo singleton para almacenar un único valor de configuración.
    """
    campo_1 = models.TextField(
        blank=True,
        null=True,
        verbose_name="Campo 1",
        help_text="Valor único de configuración."
    )

    class Meta:
        verbose_name = "Configuración de Ficha"
        verbose_name_plural = "Configuraciones de Ficha"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def obtener_instancia(cls):
        objeto, _ = cls.objects.get_or_create(pk=1, defaults={'campo_1': ''})
        return objeto

    def __str__(self):
        return f"Configuración: {self.campo_1 or 'Vacío'}"





class tbl_Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True, verbose_name="ID Notificación")

    mes = models.CharField(max_length=20, verbose_name="Mes")
    id_ccpp = models.ForeignKey(tbl_CCPP, on_delete=models.CASCADE, verbose_name="CCPP relacionado")
    id_unidad = models.ForeignKey(tbl_Unidad, on_delete=models.CASCADE, verbose_name="Unidad relacionada")
    anio = models.IntegerField(verbose_name="Año relacionado")

    id_ficha_control = models.ForeignKey(
        'tbl_FichaControl',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notificaciones',
        verbose_name="Control de Ficha relacionado",
    )

    fecha = models.DateField(auto_now_add=True, verbose_name="Fecha de Notificación", null=True, blank=True)
    para = models.TextField(verbose_name="Para", blank=True)
    cc = models.TextField(verbose_name="CC", blank=True)
    cco = models.TextField(verbose_name="CCO", blank=True)

    FechaResp = models.DateField(verbose_name="Fecha de Respuesta", null=True, blank=True)
    RespRevision = models.TextField(verbose_name="Revisión de Respuesta", blank=True)
    RespControlador = models.TextField(verbose_name="Controlador de Respuesta", null=True, blank=True)
    RespVia = models.TextField(verbose_name="Via de Respuesta",null=True, blank=True)
    RespObservacion = models.TextField(verbose_name="Observación de Respuesta",null=True, blank=True)
    RespInspEjecutada = models.BooleanField(default=False, verbose_name="Inspección Ejecutada")
    NotificacionContestada = models.BooleanField(default=False, verbose_name="Notificación Contestada")



    fecha_envio_programado = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha y hora de envío programado"
    )
    tarea_q_id = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name="ID de tarea en django-q2"
    )
    envio_ejecutado = models.BooleanField(
        default=False,
        verbose_name="Correo enviado automáticamente"
    )



class tbl_NotificacionDocumento(models.Model):
    id_notificacion = models.ForeignKey(tbl_Notificacion, on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to='notificaciones/documentos/%Y/%m/%d/')
    nombre_original = models.CharField(max_length=255)
    fecha_subida = models.DateField(auto_now_add=True)
    tamano = models.BigIntegerField()

    def delete(self, *args, **kwargs):
        """Eliminar el archivo físico al eliminar el documento"""
        try:
            if self.archivo:
                self.archivo.delete(save=False)
        except Exception as e:
            logger.warning(f"Error al eliminar archivo físico del documento {self.id}: {e}")

        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Documento de Notificación"
        verbose_name_plural = "Documentos de Notificaciones"



class tbl_Correo(models.Model):
    asunto = models.CharField(max_length=255, verbose_name="Asunto")
    cuerpo = models.TextField(verbose_name="Cuerpo del Correo")











#FINAL

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    ccpp_asignada = models.ForeignKey(tbl_CCPP, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="CCPP Asignada")

    class Meta:
        # Esto vincula el modelo con el nuevo nombre de la tabla
        db_table = 'appadministrador_UserProfile'

    def __str__(self):
        return f"Perfil de {self.user.username}"





class ConfiguracionEmail(models.Model):
    servidor_smtp = models.CharField(max_length=255, default='smtp.gmail.com')
    puerto = models.IntegerField(default=587)
    usar_tls = models.BooleanField(default=True)
    usuario_email = models.EmailField(max_length=255)
    password_aplicacion = models.CharField(max_length=255, help_text="Usa la contraseña de aplicación, no la personal.")

    class Meta:
        verbose_name = "Configuración de Email"
        verbose_name_plural = "Configuraciones de Email"

    def __str__(self):
        return f"Configuración para {self.usuario_email}"
    


