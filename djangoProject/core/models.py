from django.db import models
from django.core.exceptions import ValidationError

class Usuario(models.Model):
    TIPO_CHOICES = [
        ('cliente', 'Cliente'),
        ('admin', 'Admin'),
        ('deshabilitado', 'Deshabilitado'),  # Nueva opción
    ]
    nombre = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    contraseña = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='cliente')  # Aumentamos max_length a 15
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Cabana(models.Model):
    ESTADO_CHOICES = [
        ('disponible', 'Disponible'),
        ('mantenimiento', 'Mantenimiento'),
        ('ocupada', 'Ocupada'),
    ]
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    capacidad = models.IntegerField()
    precio_noche = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='disponible')

    def __str__(self):
        return self.nombre

    def image_count(self):
        return self.images.count()


class CabanaImage(models.Model):
    cabana = models.ForeignKey(Cabana, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='cabanas/images/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.cabana.nombre} - img #{self.order}"

    def clean(self):
        # Si se está creando una nueva imagen, evita exceder 5 por cabaña
        if not self.pk:
            existing = CabanaImage.objects.filter(cabana=self.cabana).count()
            if existing >= 5:
                raise ValidationError("No se pueden agregar más de 5 imágenes a una cabaña.")


class Reserva(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
        ('finalizada', 'Finalizada'),
    ]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    cabana = models.ForeignKey(Cabana, on_delete=models.CASCADE)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    precio_dia = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        days = (self.fecha_fin - self.fecha_inicio).days
        return days * self.precio_dia

    def __str__(self):
        return f"Reserva {self.id} - {self.usuario.nombre} - {self.cabana.nombre}"


class Pago(models.Model):
    METODO_CHOICES = [
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('completado', 'Completado'),
        ('fallido', 'Fallido'),
    ]
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    metodo_pago = models.CharField(max_length=15, choices=METODO_CHOICES)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    estado_pago = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')

    def __str__(self):
        return f"Pago {self.id} - {self.usuario.nombre} ({self.metodo_pago})"


class HistorialAccion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    accion = models.CharField(max_length=255)
    fecha_accion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.fecha_accion} - {self.usuario.nombre}: {self.accion}"