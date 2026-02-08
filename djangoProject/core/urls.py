from django.urls import path
from . import views
# el from . es para decir que desde la misma carpeta se importa un modulo 

#aqui les doy una url a las funciones/vistas que dejé
urlpatterns = [
    path('', views.index, name='index'),                               # /
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),                 # /cerrar sesión/
    path('register/', views.register, name='register'),                # /register/ (futura plantilla de registro)
    path('carrito/', views.carrito, name='carrito'),                   # /carrito/
   

    path("mis_reservas/", views.mis_reservas, name="mis_reservas"),
    path("mi_perfil/", views.mi_perfil, name="mi_perfil"),
    path("politicas/", views.politicas, name="politicas"),  
    path("contacto/", views.contacto, name="contacto"),     

    # Rutas de administración
    path('panel/', views.admin_index, name='admin-index'),
    path('panel/cabanas/', views.admin_cabanas, name='admin-cabanas'),
    path('panel/reservas/', views.admin_reservas, name='admin-reservas'),
    path('panel/usuarios/', views.admin_usuarios, name='admin-usuarios'),
    path('panel/reportes/', views.admin_reportes, name='admin-reportes'),
    path('panel/historial/', views.admin_historial, name='admin-historial'),

    # Pagos simulados
    path('pago/iniciar/', views.iniciar_pago, name='pago-iniciar'),
    path('pago/simular/<int:pago_id>/', views.pago_simulado, name='pago-simular'),
    path('pago/webhook/', views.pago_webhook, name='pago-webhook'),


    path('panel/usuarios/crear/', views.crear_usuario_admin, name='admin-usuarios-crear'),
    path('panel/reservas/crear/', views.crear_reserva_admin, name='admin-reservas-crear'),
    path('panel/reservas/cabana/<int:cabana_id>/', views.obtener_reservas_cabana, name='admin-reservas-cabana'),

    #Recuperación contraseña
    path('forgot-password/', views.forgot_password, name='forgot-password'),
    path('send-reset-code/', views.send_reset_code, name='send-reset-code'),
    path('verify-reset-code/', views.verify_reset_code, name='verify-reset-code'),
    path('reset-password/', views.reset_password, name='reset-password'),
]


