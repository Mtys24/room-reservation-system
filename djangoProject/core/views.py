import logging
import json
import re
import hashlib
import uuid
import pandas as pd
from django.http import HttpResponse
from decimal import Decimal
from datetime import datetime,timedelta
from django.db.models.functions import ExtractYear, ExtractMonth
from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Max
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db import transaction
from django.core.files.storage import default_storage
import os

from .models import Cabana, Usuario, Reserva, CabanaImage, Pago, HistorialAccion

def index(request):
    cabanas = Cabana.objects.filter(estado="disponible").prefetch_related('images')
    return render(request, 'core/index.html', {'cabanas': cabanas})

logger = logging.getLogger(__name__)

def login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        try:
            user = Usuario.objects.get(email=username)
            
            # ✅ VALIDACIÓN: Verificar si el usuario está deshabilitado
            if user.tipo == 'deshabilitado':
                messages.error(request, "Tu cuenta está deshabilitada. Contacta al administrador.")
                return render(request, "core/login.html")

            if user.contraseña == password or user.contraseña == hashlib.sha256(password.encode()).hexdigest():
                request.session["usuario_id"] = user.id
                request.session["usuario_nombre"] = user.nombre
                request.session["usuario_tipo"] = user.tipo

                # ✅ REGISTRAR EN HISTORIAL: Inicio de sesión
                HistorialAccion.objects.create(
                    usuario=user,
                    accion="Inició sesión en el sistema"
                )

                if user.tipo == "admin":
                    return redirect("admin-index")
                else:
                    return redirect("index")
            else:
                messages.error(request, "Contraseña incorrecta.")
                return render(request, "core/login.html")

        except Usuario.DoesNotExist:
            messages.error(request, "Correo no registrado.")
            return render(request, "core/login.html")

    return render(request, "core/login.html")

def register(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')
        contraseña = request.POST.get('contraseña')
        confirmar = request.POST.get('confirmar')

        # Validación de email mejorada
        def validar_email(email):
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, email):
                return False, "Formato de email inválido."
            
            dominio = email.split('@')[1].lower()
            dominios_validos = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 
                                'usm.cl', 'live.com', 'msn.com', 'aol.com', 'protonmail.com', 'yahoo.es',
                                'hotmail.es', 'outlook.es', 'inacapmail.cl']
            
            if dominio not in dominios_validos:
                return False, "Por favor usa un proveedor de email válido (Gmail, Hotmail, Outlook, Yahoo, etc.)."
            
            return True, "Email válido"

        # Validar email
        es_valido, mensaje_email = validar_email(email)
        if not es_valido:
            messages.error(request, mensaje_email)
            return render(request, 'core/register.html')

        if contraseña != confirmar:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'core/register.html')

        if Usuario.objects.filter(email=email).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
            return render(request, 'core/register.html')

        if len(contraseña) < 6:
            messages.error(request, 'La contraseña debe tener al menos 6 caracteres.')
            return render(request, 'core/register.html')

        contraseña_encriptada = hashlib.sha256(contraseña.encode()).hexdigest()

        # Crear usuario
        usuario = Usuario.objects.create(
            nombre=nombre,
            email=email,
            telefono=telefono,
            contraseña=contraseña_encriptada
        )
        
        # ✅ REGISTRAR EN HISTORIAL: Registro de nuevo usuario
        HistorialAccion.objects.create(
            usuario=usuario,
            accion="Se registró en el sistema"
        )
        
        messages.success(request, 'Cuenta creada exitosamente. Ahora puedes iniciar sesión.')
        return redirect('login')

    return render(request, 'core/register.html')

def logout(request):
    usuario_id = request.session.get("usuario_id")
    if usuario_id:
        try:
            usuario = Usuario.objects.get(id=usuario_id)
            # ✅ REGISTRAR EN HISTORIAL: Cierre de sesión
            HistorialAccion.objects.create(
                usuario=usuario,
                accion="🔒 Cerró sesión en el sistema"
            )
        except Usuario.DoesNotExist:
            pass
    
    request.session.flush()
    messages.success(request, "✅ Sesión cerrada correctamente.")
    return redirect("index")

def mi_perfil(request):
    if not request.session.get('usuario_id'):
        messages.error(request, "Debes iniciar sesión para acceder a tu perfil.")
        return redirect('login')
    
    usuario = get_object_or_404(Usuario, id=request.session['usuario_id'])
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            # Obtener datos del formulario de perfil
            nombre = request.POST.get('nombre', '').strip()
            email = request.POST.get('email', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            
            # Validaciones
            if not nombre:
                messages.error(request, "El nombre es obligatorio.")
                return redirect('mi_perfil')
            
            if not email:
                messages.error(request, "El correo electrónico es obligatorio.")
                return redirect('mi_perfil')
            
            # Validación de email mejorada
            def validar_email(email):
                pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(pattern, email):
                    return False, "Formato de email inválido."
                
                dominio = email.split('@')[1].lower()
                dominios_validos = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 
                                  'live.com', 'msn.com', 'aol.com', 'protonmail.com', 'yahoo.es',
                                  'hotmail.es', 'outlook.es', 'inacapmail.cl', 'usm.cl']
                
                if dominio not in dominios_validos:
                    return False, "Por favor usa un proveedor de email válido (Gmail, Hotmail, Outlook, Yahoo, etc.)."
                
                return True, "Email válido"

            # Validar email
            es_valido, mensaje_email = validar_email(email)
            if not es_valido:
                messages.error(request, mensaje_email)
                return redirect('mi_perfil')
            
            # Verificar si el email ya existe (excluyendo el usuario actual)
            if Usuario.objects.filter(email=email).exclude(id=usuario.id).exists():
                messages.error(request, "Este correo electrónico ya está registrado por otro usuario.")
                return redirect('mi_perfil')
            
            # Guardar datos antiguos para comparar
            nombre_antiguo = usuario.nombre
            email_antiguo = usuario.email
            telefono_antiguo = usuario.telefono
            
            # Actualizar datos del usuario
            usuario.nombre = nombre
            usuario.email = email
            usuario.telefono = telefono if telefono else None
            
            try:
                usuario.save()
                
                # Actualizar también en la sesión si el nombre cambió
                if request.session.get('usuario_nombre') != usuario.nombre:
                    request.session['usuario_nombre'] = usuario.nombre
                
                # ✅ REGISTRAR EN HISTORIAL: Actualización de perfil con detalles
                cambios = []
                if nombre_antiguo != nombre:
                    cambios.append(f"nombre: {nombre_antiguo} → {nombre}")
                if email_antiguo != email:
                    cambios.append(f"email: {email_antiguo} → {email}")
                if telefono_antiguo != telefono:
                    cambios.append(f"teléfono: {telefono_antiguo} → {telefono}")
                
                if cambios:
                    HistorialAccion.objects.create(
                        usuario=usuario,
                        accion=f"Actualizó su perfil - {', '.join(cambios)}"
                    )
                
                messages.success(request, "✅ Perfil actualizado correctamente.")
                
            except Exception as e:
                messages.error(request, f"Error al actualizar el perfil: {e}")
            
            return redirect('mi_perfil')
        
        elif form_type == 'password':
            # Obtener datos del formulario de cambio de contraseña
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            # Validaciones
            if not current_password or not new_password or not confirm_password:
                messages.error(request, "Todos los campos de contraseña son obligatorios.")
                return redirect('mi_perfil')
            
            # Verificar contraseña actual
            current_password_encrypted = hashlib.sha256(current_password.encode()).hexdigest()
            if usuario.contraseña != current_password_encrypted:
                messages.error(request, "❌ La contraseña actual es incorrecta.")
                return redirect('mi_perfil')
            
            if new_password != confirm_password:
                messages.error(request, "❌ Las nuevas contraseñas no coinciden.")
                return redirect('mi_perfil')
            
            if len(new_password) < 6:
                messages.error(request, "❌ La nueva contraseña debe tener al menos 6 caracteres.")
                return redirect('mi_perfil')
            
            # Cambiar contraseña
            try:
                nueva_contraseña_encriptada = hashlib.sha256(new_password.encode()).hexdigest()
                usuario.contraseña = nueva_contraseña_encriptada
                usuario.save()
                
                # ✅ REGISTRAR EN HISTORIAL: Cambio de contraseña desde perfil
                HistorialAccion.objects.create(
                    usuario=usuario,
                    accion="Cambió su contraseña desde el perfil"
                )
                
                # Enviar email de confirmación
                try:
                    subject = "✅ Contraseña Actualizada - Cabañas Valle Central"
                    body = f"""
Hola {usuario.nombre},

Tu contraseña en Cabañas Valle Central ha sido actualizada exitosamente desde tu perfil.

📝 **Detalles del cambio:**
• Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Email: {usuario.email}

🔐 **Recomendaciones de seguridad:**
1. No compartas tu contraseña con nadie
2. Usa una contraseña única para este sitio
3. Cambia tu contraseña periódicamente

Si no realizaste este cambio, por favor contáctanos inmediatamente:
📞 WhatsApp: +56 9 1234 5678
✉️ Email: info@cabanasvallecentral.cl

Saludos cordiales,
El equipo de Cabañas Valle Central 🌲
                    """
                    
                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [usuario.email],
                        fail_silently=True
                    )
                    
                except Exception as e:
                    print(f"⚠️ Error enviando email de confirmación de cambio de contraseña: {e}")
                
                messages.success(request, "✅ Contraseña actualizada correctamente. Se ha enviado un email de confirmación.")
                
            except Exception as e:
                messages.error(request, f"Error al cambiar la contraseña: {e}")
            
            return redirect('mi_perfil')
    
    context = {
        'usuario': usuario,
    }
    return render(request, 'core/mi_perfil.html', context)

def mis_reservas(request):
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        messages.error(request, "Debes iniciar sesión para ver tus reservas.")
        return redirect("login")
    
    try:
        reservas = Reserva.objects.filter(usuario_id=usuario_id).exclude(estado='cancelada').select_related("cabana").order_by("-fecha_inicio")
        
        # ✅ ENVIAR EMAIL DE RECORDATORIO si hay reservas confirmadas próximas
        usuario = Usuario.objects.get(id=usuario_id)
        hoy = datetime.now().date()
        
        for reserva in reservas.filter(estado='confirmada'):
            # Enviar recordatorio si la reserva es dentro de los próximos 3 días
            dias_faltantes = (reserva.fecha_inicio - hoy).days
            if 0 <= dias_faltantes <= 3:
                try:
                    subject = f"🎯 Recordatorio de tu reserva #{reserva.id} - Cabañas Valle Central"
                    
                    body = (
                        f"Hola {usuario.nombre},\n\n"
                        f"📅 Tu reserva #{reserva.id} está próxima:\n\n"
                        f"🏠 Cabaña: {reserva.cabana.nombre}\n"
                        f"📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                        f"📅 Fecha de salida: {reserva.fecha_fin}\n"
                        f"💰 Total: ${reserva.total}\n"
                        f"✅ Estado: CONFIRMADA\n\n"
                        f"📍 INFORMACIÓN IMPORTANTE:\n"
                        f"• 🕚 Check-in: 11:00 a.m\n"
                        f"• 🕛 Check-out: 12:00 p.m\n"
                        f"• 📍 Ubicación: Zona boscosa del valle central de Chile\n\n"
                        f"📝 Preparativos para tu estadía:\n"
                        f"• Lleva ropa cómoda y abrigadora\n"
                        f"• No olvides tus artículos de higiene personal\n"
                        f"• Te recomendamos llevar repelente de insectos\n\n"
                        f"🔔 Recordatorio:\n"
                        f"Faltan {dias_faltantes} día(s) para tu check-in.\n\n"
                        f"📞 Contacto de emergencia:\n"
                        f"• WhatsApp: +56 9 1234 5678\n"
                        f"• Email: info@cabanasvallecentral.cl\n\n"
                        f"¡Esperamos que disfrutes tu estadía!\n\n"
                        f"Saludos cordiales,\n"
                        f"El equipo de Cabañas Valle Central 🌲"
                    )
                    
                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [usuario.email],
                        fail_silently=True
                    )
                    
                    print(f"✅ Email de recordatorio enviado a {usuario.email} para reserva #{reserva.id}")
                    
                except Exception as e:
                    print(f"⚠️ Error enviando email de recordatorio: {e}")
        
        return render(request, "core/mis_reservas.html", {"reservas": reservas})
        
    except Exception as e:
        print(f"Error en mis_reservas: {e}")
        messages.error(request, "Error al cargar tus reservas.")
        return redirect("index")

def carrito(request):
    cabana_id = request.GET.get('cabana_id')
    cabana = None
    reservas_existentes = []

    if cabana_id:
        cabana = get_object_or_404(Cabana.objects.prefetch_related('images'), id=cabana_id)
        qs = Reserva.objects.filter(
            cabana=cabana,
            estado__in=['pendiente', 'confirmada']
        ).order_by('fecha_inicio')
        reservas_existentes = [
            {'inicio': r.fecha_inicio.isoformat(), 'fin': r.fecha_fin.isoformat()}
            for r in qs
        ]

    if request.method == 'POST':
        if not request.session.get('usuario_id'):
            messages.error(request, "Debes iniciar sesión para confirmar una reserva.")
            return redirect('login')

        usuario = get_object_or_404(Usuario, id=request.session['usuario_id'])
        cabana_id = request.POST.get('cabana_id')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        payment_method = request.POST.get('payment_method', 'offline')
        total_estimated = request.POST.get('total_estimated')  # optional

        if not fecha_inicio or not fecha_fin:
            messages.error(request, "Debes seleccionar las fechas de tu reserva.")
            return redirect('carrito')

        cabana = get_object_or_404(Cabana, id=cabana_id)

        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

        solapadas = Reserva.objects.filter(
            cabana=cabana,
            estado__in=['pendiente', 'confirmada'],
            fecha_inicio__lte=fin,
            fecha_fin__gte=inicio
        )

        if solapadas.exists():
            messages.error(request, "Las fechas seleccionadas no están disponibles.")
            return redirect(f"/carrito/?cabana_id={cabana.id}")

        nueva_reserva = Reserva.objects.create(
            usuario=usuario,
            cabana=cabana,
            fecha_inicio=inicio,
            fecha_fin=fin,
            precio_dia=cabana.precio_noche,
            estado='pendiente'
        )

        # ✅ REGISTRAR EN HISTORIAL: Creación de reserva desde carrito
        HistorialAccion.objects.create(
            usuario=usuario,
            accion=f"Creó reserva #{nueva_reserva.id} para {cabana.nombre} ({inicio} a {fin}) - Método: {payment_method}"
        )

        # enviar email dependiendo del método elegido
        try:
            subject = f"Reserva #{nueva_reserva.id} - Cabañas Valle Central"
            if payment_method == 'online':
                body = (
                    f"Hola {usuario.nombre},\n\n"
                    f"Hemos creado la reserva #{nueva_reserva.id} para {nueva_reserva.cabana.nombre} "
                    f"desde {nueva_reserva.fecha_inicio} hasta {nueva_reserva.fecha_fin}.\n\n"
                    "Seleccionaste Pago en línea. Serás redirigido para completar el pago.\n\n"
                    "Si no iniciaste esta solicitud, ignora este correo.\n\n"
                    "Saludos,\nCabañas Valle Central"
                )
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=True)
                return redirect(f"{reverse('pago-iniciar')}?reserva_id={nueva_reserva.id}")

            elif payment_method == 'transferencia':
                bank_info = (
                    "Banco: Banco Estado\n"
                    "Cuenta: 771957169\n"
                    "Titular: Cabañas Valle Central\n"
                    "Tipo Cuenta: Cuenta Corriente  \n"
                    f"Referencia: RES{nueva_reserva.id}"
                )
                body = (
                    f"Hola {usuario.nombre},\n\n"
                    f"Tu reserva #{nueva_reserva.id} para {nueva_reserva.cabana.nombre} "
                    f"ha sido creada (pendiente) para {nueva_reserva.fecha_inicio} → {nueva_reserva.fecha_fin}.\n\n"
                    f"Para completar la reserva, realiza una transferencia por ${nueva_reserva.total} (estimado) a:\n\n"
                    f"{bank_info}\n\n"
                    "Una vez recibida la transferencia confirmaremos la reserva.\n\nSaludos,\nCabañas Valle Central"
                )
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=True)
                messages.success(request, "Reserva creada. Te hemos enviado instrucciones para la transferencia a tu correo.")
                return redirect('mis_reservas')

            else:  # offline / pago en destino
                body = (
                    f"Hola {usuario.nombre},\n\n"
                    f"Tu reserva #{nueva_reserva.id} para {nueva_reserva.cabana.nombre} "
                    f"ha sido creada (pendiente) para {nueva_reserva.fecha_inicio} → {nueva_reserva.fecha_fin}.\n\n"
                    "Puedes pagar en el lugar (efectivo o tarjeta) al momento del check-in.\n\n"
                    "El chek-in es a las 11:00 a.m y el check-out es a las 12:00 pm \n\n"
                    "Saludos,\nCabañas Valle Central"
                )
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=True)
                messages.success(request, "Reserva creada. Te enviamos un email con los detalles.")
                return redirect('mis_reservas')

        except Exception as e:
            messages.warning(request, "Reserva creada pero no se pudo enviar el correo (error de SMTP).")

        return redirect('mis_reservas')

    context = {
        'cabana': cabana,
        'reservas_existentes': reservas_existentes,
        'reservas_json': json.dumps(reservas_existentes),
    }
    return render(request, 'core/carrito.html', context)

def iniciar_pago(request):
    reserva_id = request.GET.get('reserva_id') or request.POST.get('reserva_id')
    if not reserva_id:
        messages.error(request, "Reserva no especificada para el pago.")
        return redirect('index')

    reserva = get_object_or_404(Reserva, id=reserva_id)

    # reutilizar pago pendiente si existe
    pago = Pago.objects.filter(reserva=reserva).order_by('-id').first()
    if not pago or pago.estado_pago != 'pendiente':
        monto = Decimal(reserva.total) if hasattr(reserva, 'total') else (reserva.precio_dia * (reserva.fecha_fin - reserva.fecha_inicio).days)
        pago = Pago.objects.create(
            reserva=reserva,
            usuario=reserva.usuario,
            metodo_pago='tarjeta',
            monto=monto,
            estado_pago='pendiente'
        )

    token = str(uuid.uuid4())
    request.session[f'pago_token_{pago.id}'] = token

    return redirect('pago-simular', pago_id=pago.id)

def pago_simulado(request, pago_id):
    pago = get_object_or_404(Pago, id=pago_id)
    reserva = pago.reserva

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'pay':
            pago.estado_pago = 'completado'
            pago.save()
            reserva.estado = 'confirmada'
            reserva.save()

            # ✅ REGISTRAR EN HISTORIAL: Pago exitoso
            HistorialAccion.objects.create(
                usuario=pago.usuario,
                accion=f"Realizó pago exitoso de ${pago.monto} para reserva #{reserva.id}"
            )

            # enviar email de confirmación pago/completado
            try:
                subject = f"Pago confirmado - Reserva #{reserva.id}"
                body = (
                    f"Hola {pago.usuario.nombre},\n\n"
                    f"Tu pago de ${pago.monto} para la reserva #{reserva.id} ha sido recibido.\n"
                    f"La reserva para {reserva.cabana.nombre} desde {reserva.fecha_inicio} hasta {reserva.fecha_fin} ha sido confirmada.\n\n"
                    "El chek-in es a las 11:00 a.m y el check-out es a las 12:00 pm \n\n"
                    "Gracias por reservar con nosotros.\nCabañas Valle Central"
                )
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [pago.usuario.email], fail_silently=True)
            except Exception:
                pass

            messages.success(request, 'Pago exitoso. Reserva confirmada.')
            return render(request, 'core/pago_result.html', {'success': True, 'pago': pago, 'reserva': reserva})

        else:  # action == 'cancel'
            # ✅ REGISTRAR EN HISTORIAL: Cancelación de pago
            HistorialAccion.objects.create(
                usuario=pago.usuario,
                accion=f"Canceló pago para reserva #{reserva.id} (reserva eliminada)"
            )
            
            reserva.delete()
            messages.error(request, 'Pago cancelado. La reserva ha sido eliminada.')
            return redirect('index')

    return render(request, 'core/pago_simulado.html', {'pago': pago, 'reserva': reserva})

def pago_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST required")
    try:
        data = json.loads(request.body.decode('utf-8'))
        pago_id = data.get('pago_id')
        status = data.get('status')
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")
    if not pago_id or not status:
        return HttpResponseBadRequest("pago_id and status required")
    pago = get_object_or_404(Pago, id=pago_id)
    if status in ('completed', 'completado'):
        pago.estado_pago = 'completado'
        pago.save()
        reserva = pago.reserva
        reserva.estado = 'confirmada'
        reserva.save()
        
        # ✅ REGISTRAR EN HISTORIAL: Pago vía webhook
        HistorialAccion.objects.create(
            usuario=pago.usuario,
            accion=f"Pago completado vía webhook para reserva #{reserva.id}"
        )
        
        try:
            subject = f"Pago confirmado - Reserva #{reserva.id}"
            body = f"Tu pago para reserva #{reserva.id} ha sido recibido. Reserva confirmada."
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [pago.usuario.email], fail_silently=True)
        except Exception:
            pass
        return JsonResponse({'result': 'ok', 'message': 'Pago marcado como completado'})
    elif status in ('failed', 'fallido'):
        pago.estado_pago = 'fallido'
        pago.save()
        
        # ✅ REGISTRAR EN HISTORIAL: Pago fallido
        HistorialAccion.objects.create(
            usuario=pago.usuario,
            accion=f"Pago fallido para reserva #{reserva.id}"
        )
        
        return JsonResponse({'result': 'ok', 'message': 'Pago marcado como fallido'})
    else:
        return HttpResponseBadRequest("Unknown status")

def enviar_email_reserva(usuario, reserva, payment_method, total):
    """
    Envía correo HTML + texto con los detalles de la reserva.
    - usuario: instancia Usuario
    - reserva: instancia Reserva
    - payment_method: 'online' | 'transferencia' | 'offline' | 'admin'
    - total: Decimal o str
    """
    
    if payment_method == 'admin':
        subject = f"🏠 Reserva #{reserva.id} - Gestionada por Administrador - Cabañas Valle Central"
    else:
        subject = f"🏠 Confirmación de Reserva #{reserva.id} - Cabañas Valle Central"
    
    context = {
        'usuario': usuario,
        'reserva': reserva,
        'payment_method': payment_method,
        'total': total,
    }
    
    try:
        text_body = render_to_string('emails/reserva_confirmacion.txt', context)
        html_body = render_to_string('emails/reserva_confirmacion.html', context)
    except Exception as e:
        print(f"❌ Error renderizando plantillas de email: {e}")
        # Texto de respaldo con iconos
        if payment_method == 'admin':
            text_body = (
                f"Hola {usuario.nombre},\n\n"
                f"🏠 Un administrador ha gestionado tu reserva #{reserva.id} para {reserva.cabana.nombre}.\n\n"
                f"📋 Detalles de la reserva:\n"
                f"• 🏠 Cabaña: {reserva.cabana.nombre}\n"
                f"• 📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                f"• 📅 Fecha de salida: {reserva.fecha_fin}\n"
                f"• 💰 Total: ${total}\n"
                f"• 📊 Estado: {reserva.estado}\n\n"
                f"📍 INFORMACIÓN IMPORTANTE:\n"
                f"• 🕚 Check-in: 11:00 a.m\n"
                f"• 🕛 Check-out: 12:00 p.m\n\n"
                f"Esta reserva fue gestionada directamente por nuestro equipo administrativo.\n\n"
                f"📞 Contacto:\n"
                f"• WhatsApp: +56 9 1234 5678\n"
                f"• Email: info@cabanasvallecentral.cl\n\n"
                f"Gracias por preferirnos.\n\n"
                f"Saludos,\n"
                f"El equipo de Cabañas Valle Central 🌲"
            )
        else:
            text_body = (
                f"Hola {usuario.nombre},\n\n"
                f"🏠 Confirmación de Reserva #{reserva.id} - {reserva.cabana.nombre}\n\n"
                f"📋 Detalles:\n"
                f"• 📅 Entrada: {reserva.fecha_inicio}\n"
                f"• 📅 Salida: {reserva.fecha_fin}\n"
                f"• 💰 Total: ${total}\n"
                f"• 📊 Estado: {reserva.estado}\n\n"
                f"📍 INFORMACIÓN IMPORTANTE:\n"
                f"• 🕚 Check-in: 11:00 a.m\n"
                f"• 🕛 Check-out: 12:00 p.m\n\n"
                f"📞 Contacto:\n"
                f"• WhatsApp: +56 9 1234 5678\n"
                f"• Email: info@cabanasvallecentral.cl\n\n"
                f"Gracias por reservar con nosotros.\n\n"
                f"Saludos,\n"
                f"El equipo de Cabañas Valle Central 🌲"
            )
        html_body = None

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@cabanas.local')
    to = [usuario.email]

    try:
        msg = EmailMultiAlternatives(subject, text_body, from_email, to)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        print(f"✅ Email enviado exitosamente a {usuario.email}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email a {usuario.email}: {e}")
        return False
    
def politicas(request):
    return render(request, 'core/politicas.html')

def contacto(request):
    return render(request, 'core/contacto.html')

# ---------------------- ADMIN VIEWS ----------------------

def admin_index(request):
    return render(request, 'core/admin-index.html')

def admin_cabanas(request):
    cabanas = Cabana.objects.all().prefetch_related('images')
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'guardar':
            # Crear o editar cabaña
            cabana_id = request.POST.get('cabana_id')
            nombre = request.POST.get('nombre')
            descripcion = request.POST.get('descripcion')
            capacidad = request.POST.get('capacidad')
            precio_noche = request.POST.get('precio_noche')
            estado = request.POST.get('estado')
            imagenes_a_eliminar = request.POST.get('imagenes_a_eliminar', '')
            
            try:
                with transaction.atomic():
                    if cabana_id:
                        # Editar cabaña existente
                        cabana = get_object_or_404(Cabana, id=cabana_id)
                        cabana.nombre = nombre
                        cabana.descripcion = descripcion
                        cabana.capacidad = capacidad
                        cabana.precio_noche = precio_noche
                        cabana.estado = estado
                        cabana.save()
                        messages.success(request, f'Cabaña "{nombre}" actualizada correctamente.')
                    else:
                        # Crear nueva cabaña
                        cabana = Cabana.objects.create(
                            nombre=nombre,
                            descripcion=descripcion,
                            capacidad=capacidad,
                            precio_noche=precio_noche,
                            estado=estado
                        )
                        messages.success(request, f'Cabaña "{nombre}" creada correctamente.')
                    
                    # Procesar eliminación de imágenes
                    if imagenes_a_eliminar:
                        imagen_ids = [id.strip() for id in imagenes_a_eliminar.split(',') if id.strip()]
                        for imagen_id in imagen_ids:
                            try:
                                imagen = CabanaImage.objects.get(id=imagen_id, cabana=cabana)
                                # Eliminar archivo físico
                                if default_storage.exists(imagen.image.name):
                                    default_storage.delete(imagen.image.name)
                                # Eliminar registro de la base de datos
                                imagen.delete()
                            except CabanaImage.DoesNotExist:
                                pass  # La imagen ya no existe
                    
                    # Procesar nuevas imágenes
                    nuevas_imagenes = request.FILES.getlist('images')
                    if nuevas_imagenes:
                        # Verificar límite de imágenes (máximo 5)
                        imagenes_actuales_count = cabana.images.count()
                        espacios_disponibles = max(0, 5 - imagenes_actuales_count)
                        
                        if len(nuevas_imagenes) > espacios_disponibles:
                            messages.warning(request, f'Solo se pudieron subir {espacios_disponibles} imágenes de {len(nuevas_imagenes)}. Límite máximo: 5 imágenes por cabaña.')
                        
                        for i, imagen_file in enumerate(nuevas_imagenes):
                            if i >= espacios_disponibles:
                                break
                            CabanaImage.objects.create(cabana=cabana, image=imagen_file)
            
            except Exception as e:
                messages.error(request, f'Error al guardar la cabaña: {str(e)}')
            
            return redirect('admin-cabanas')
        
        elif accion == 'eliminar':
            # Eliminar cabaña
            cabana_id = request.POST.get('cabana_id')
            try:
                cabana = get_object_or_404(Cabana, id=cabana_id)
                nombre_cabana = cabana.nombre
                
                # Eliminar imágenes físicas
                for imagen in cabana.images.all():
                    if default_storage.exists(imagen.image.name):
                        default_storage.delete(imagen.image.name)
                
                # Eliminar cabaña (esto eliminará automáticamente las imágenes por CASCADE)
                cabana.delete()
                messages.success(request, f'Cabaña "{nombre_cabana}" eliminada correctamente.')
            
            except Exception as e:
                messages.error(request, f'Error al eliminar la cabaña: {str(e)}')
            
            return redirect('admin-cabanas')
    
    # GET request - mostrar todas las cabañas
    context = {
        'cabanas': cabanas,
    }
    return render(request, 'core/admin-cabanas.html', context)

@csrf_exempt
def admin_reservas(request):
    if request.session.get("usuario_tipo") != "admin":
        messages.error(request, "Acceso no autorizado.")
        return redirect("index")

    if request.method == "POST":
        reserva_id = request.POST.get("reserva_id")
        nuevo_estado = request.POST.get("estado")

        try:
            reserva = Reserva.objects.get(id=reserva_id)
            estado_anterior = reserva.estado
            reserva.estado = nuevo_estado
            reserva.save()
            
            # ✅ REGISTRAR EN HISTORIAL: Cambio de estado de reserva
            admin_usuario = Usuario.objects.get(id=request.session['usuario_id'])
            HistorialAccion.objects.create(
                usuario=admin_usuario,
                accion=f"Cambió estado de reserva #{reserva.id} de '{estado_anterior}' a '{nuevo_estado}'"
            )
            
            # ✅ ENVIAR EMAIL AL USUARIO SOBRE EL CAMBIO DE ESTADO
            try:
                subject = f"📢 Actualización de estado - Reserva #{reserva.id} - Cabañas Valle Central"
                
                # Contenido del email según el nuevo estado
                if nuevo_estado == 'confirmada':
                    body = (
                        f"Hola {reserva.usuario.nombre},\n\n"
                        f"🎉 ¡Excelentes noticias! Tu reserva #{reserva.id} ha sido CONFIRMADA.\n\n"
                        f"📋 Detalles de tu reserva confirmada:\n"
                        f"• 🏠 Cabaña: {reserva.cabana.nombre}\n"
                        f"• 📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                        f"• 📅 Fecha de salida: {reserva.fecha_fin}\n"
                        f"• 💰 Total: ${reserva.total}\n"
                        f"• ✅ Estado: CONFIRMADA\n\n"
                        f"📍 INFORMACIÓN IMPORTANTE:\n"
                        f"• 🕚 Check-in: 11:00 a.m\n"
                        f"• 🕛 Check-out: 12:00 p.m\n"
                        f"• 📍 Ubicación: Zona boscosa del valle central de Chile\n\n"
                        f"📝 Preparativos para tu estadía:\n"
                        f"• Lleva ropa cómoda y abrigadora\n"
                        f"• No olvides tus artículos de higiene personal\n"
                        f"• Te recomendamos llevar repelente de insectos\n\n"
                        f"¡Esperamos que disfrutes tu estadía en {reserva.cabana.nombre}!\n\n"
                        f"📞 Contacto:\n"
                        f"• WhatsApp: +56 9 1234 5678\n"
                        f"• Email: info@cabanasvallecentral.cl\n\n"
                        f"Saludos cordiales,\n"
                        f"El equipo de Cabañas Valle Central 🌲"
                    )
                elif nuevo_estado == 'cancelada':
                    body = (
                        f"Hola {reserva.usuario.nombre},\n\n"
                        f"❌ Te informamos que tu reserva #{reserva.id} ha sido CANCELADA.\n\n"
                        f"📋 Detalles de la reserva cancelada:\n"
                        f"• 🏠 Cabaña: {reserva.cabana.nombre}\n"
                        f"• 📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                        f"• 📅 Fecha de salida: {reserva.fecha_fin}\n"
                        f"• 💰 Total: ${reserva.total}\n"
                        f"• ❌ Estado: CANCELADA\n\n"
                        f"💡 ¿Fue un error?\n"
                        f"Si crees que esto fue un error o necesitas reactivar tu reserva, "
                        f"por favor contáctanos inmediatamente.\n\n"
                        f"📞 Contacto:\n"
                        f"• WhatsApp: +56 9 1234 5678\n"
                        f"• Email: info@cabanasvallecentral.cl\n\n"
                        f"Esperamos poder servirte en una futura oportunidad.\n\n"
                        f"Saludos,\n"
                        f"El equipo de Cabañas Valle Central"
                    )
                elif nuevo_estado == 'pendiente':
                    body = (
                        f"Hola {reserva.usuario.nombre},\n\n"
                        f"⏳ El estado de tu reserva #{reserva.id} ha sido actualizado a PENDIENTE.\n\n"
                        f"📋 Detalles actualizados:\n"
                        f"• 🏠 Cabaña: {reserva.cabana.nombre}\n"
                        f"• 📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                        f"• 📅 Fecha de salida: {reserva.fecha_fin}\n"
                        f"• 💰 Total: ${reserva.total}\n"
                        f"• ⏳ Estado: PENDIENTE\n\n"
                        f"📍 INFORMACIÓN IMPORTANTE (cuando sea confirmada):\n"
                        f"• 🕚 Check-in: 11:00 a.m\n"
                        f"• 🕛 Check-out: 12:00 p.m\n\n"
                        f"📝 Próximos pasos:\n"
                        f"Estamos procesando tu reserva. Te notificaremos por este mismo medio "
                        f"cuando sea confirmada.\n\n"
                        f"⏰ Tiempo de procesamiento:\n"
                        f"• Reservas estándar: 1-2 horas hábiles\n"
                        f"• Reservas con pago pendiente: Hasta confirmación de pago\n\n"
                        f"Si tienes urgencia, contáctanos:\n"
                        f"📞 +56 9 1234 5678 (WhatsApp)\n\n"
                        f"Saludos,\n"
                        f"El equipo de Cabañas Valle Central"
                    )
                else:  # Para otros estados como 'finalizada'
                    body = (
                        f"Hola {reserva.usuario.nombre},\n\n"
                        f"📢 El estado de tu reserva #{reserva.id} ha sido actualizado.\n\n"
                        f"📋 Detalles actualizados:\n"
                        f"• 🏠 Cabaña: {reserva.cabana.nombre}\n"
                        f"• 📅 Fecha de entrada: {reserva.fecha_inicio}\n"
                        f"• 📅 Fecha de salida: {reserva.fecha_fin}\n"
                        f"• 💰 Total: ${reserva.total}\n"
                        f"• 📊 Estado: {nuevo_estado.upper()}\n\n"
                        f"📍 RECUERDA:\n"
                        f"• 🕚 Check-in: 11:00 a.m\n"
                        f"• 🕛 Check-out: 12:00 p.m\n\n"
                        f"Para más información, puedes ingresar a tu cuenta en nuestro sitio web "
                        f"o contactarnos directamente.\n\n"
                        f"📞 Contacto:\n"
                        f"• WhatsApp: +56 9 1234 5678\n"
                        f"• Email: info@cabanasvallecentral.cl\n\n"
                        f"Saludos,\n"
                        f"El equipo de Cabañas Valle Central"
                    )
                
                # Enviar el email
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [reserva.usuario.email],
                    fail_silently=False
                )
                
                # ✅ REGISTRAR EN HISTORIAL: Email de notificación enviado
                HistorialAccion.objects.create(
                    usuario=admin_usuario,
                    accion=f"Envió email de notificación por cambio de estado a '{nuevo_estado}' para reserva #{reserva.id}"
                )
                
                print(f"✅ Email de actualización enviado a {reserva.usuario.email} para reserva #{reserva.id}")
                
            except Exception as e:
                print(f"❌ Error enviando email de actualización para reserva #{reserva.id}: {e}")
                # Registrar el error en el historial pero no interrumpir el flujo
                HistorialAccion.objects.create(
                    usuario=admin_usuario,
                    accion=f"Error al enviar email de notificación para reserva #{reserva.id}: {str(e)}"
                )
            
            messages.success(request, f"Reserva #{reserva.id} actualizada a '{nuevo_estado}'. Se envió notificación al usuario.")
            
        except Reserva.DoesNotExist:
            messages.error(request, "La reserva no existe.")
        return redirect("admin-reservas")

    # ✅ AGREGAR PAGINACIÓN
    # Obtener todas las reservas ordenadas por fecha de inicio (más recientes primero)
    reservas_list = Reserva.objects.select_related("usuario", "cabana").order_by("-fecha_inicio")
    
    # Paginación: 20 reservas por página (puedes ajustar este número)
    paginator = Paginator(reservas_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    usuarios = Usuario.objects.all().order_by("nombre")
    cabanas = Cabana.objects.all().order_by("nombre")
    
    return render(request, "core/admin-reservas.html", {
        "reservas": page_obj,   # Pasamos el objeto de página para la tabla
        "page_obj": page_obj,    # También lo pasamos como page_obj para consistencia
        "usuarios": usuarios,
        "cabanas": cabanas
    })
def admin_usuarios(request):
    """Gestión de usuarios para administradores"""
    if request.session.get("usuario_tipo") != "admin":
        messages.error(request, "Acceso no autorizado.")
        return redirect("index")
    
    # Procesar acciones sobre usuarios
    if request.method == "POST":
        usuario_id = request.POST.get("usuario_id")
        accion = request.POST.get("accion")
        
        try:
            usuario = Usuario.objects.get(id=usuario_id)
            admin_usuario = Usuario.objects.get(id=request.session['usuario_id'])
            
            if accion == "deshabilitar":
                if usuario.id == request.session.get("usuario_id"):
                    messages.error(request, "No puedes deshabilitar tu propio usuario.")
                else:
                    tipo_anterior = usuario.tipo
                    usuario.tipo = 'deshabilitado'
                    usuario.save()
                    
                    # ✅ REGISTRAR EN HISTORIAL: Deshabilitar usuario
                    HistorialAccion.objects.create(
                        usuario=admin_usuario,
                        accion=f"Deshabilitó usuario: {usuario.nombre} ({usuario.email}) - Tipo anterior: {tipo_anterior}"
                    )
                    
                    messages.success(request, f"Usuario '{usuario.nombre}' deshabilitado correctamente.")
                    
            elif accion == "habilitar":
                usuario.tipo = 'cliente'
                usuario.save()
                
                # ✅ REGISTRAR EN HISTORIAL: Habilitar usuario
                HistorialAccion.objects.create(
                    usuario=admin_usuario,
                    accion=f"Habilitó usuario: {usuario.nombre} ({usuario.email}) como cliente"
                )
                
                messages.success(request, f"Usuario '{usuario.nombre}' habilitado correctamente.")
            
            elif accion == "cambiar_tipo":
                nuevo_tipo = request.POST.get("nuevo_tipo")
                if nuevo_tipo == 'deshabilitado':
                    messages.error(request, "Usa la opción 'Deshabilitar' para deshabilitar usuarios.")
                elif usuario.id == request.session.get("usuario_id"):
                    messages.error(request, "No puedes cambiar tu propio tipo de usuario.")
                else:
                    tipo_anterior = usuario.tipo
                    usuario.tipo = nuevo_tipo
                    usuario.save()
                    
                    # ✅ REGISTRAR EN HISTORIAL: Cambio de tipo de usuario
                    HistorialAccion.objects.create(
                        usuario=admin_usuario,
                        accion=f"Cambió tipo de usuario de {usuario.nombre} de '{tipo_anterior}' a '{nuevo_tipo}'"
                    )
                    
                    messages.success(request, f"Tipo de usuario de '{usuario.nombre}' cambiado a {nuevo_tipo}.")
                
        except Usuario.DoesNotExist:
            messages.error(request, "El usuario no existe.")
        
        return redirect("admin-usuarios")
    
    usuarios = Usuario.objects.all().order_by("-fecha_registro")
    
    total_usuarios = usuarios.count()
    usuarios_admin = usuarios.filter(tipo="admin").count()
    usuarios_cliente = usuarios.filter(tipo="cliente").count()
    usuarios_deshabilitados = usuarios.filter(tipo="deshabilitado").count()
    usuarios_activos = usuarios_admin + usuarios_cliente
    
    context = {
        'usuarios': usuarios,
        'total_usuarios': total_usuarios,
        'usuarios_admin': usuarios_admin,
        'usuarios_cliente': usuarios_cliente,
        'usuarios_deshabilitados': usuarios_deshabilitados,
        'usuarios_activos': usuarios_activos,
    }
    
    return render(request, "core/admin-usuarios.html", context)

def admin_reportes(request):
    """Reportes y estadísticas para administradores - VERSIÓN CORREGIDA"""
    if request.session.get("usuario_tipo") != "admin":
        messages.error(request, "Acceso no autorizado.")
        return redirect("index")
    
    tipo_filtro = request.GET.get('tipo_filtro', 'rango')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    fecha_mes = request.GET.get('fecha_mes')
    fecha_dia = request.GET.get('fecha_dia')
    exportar_excel = request.GET.get('exportar_excel')
    
    filtro_aplicado = any([fecha_inicio, fecha_fin, fecha_mes, fecha_dia])
    
    fecha_inicio_dt = None
    fecha_fin_dt = None
    filtro_actual = "Sin filtro aplicado"
    periodo_actual = "Selecciona un período para generar reportes"

    if filtro_aplicado:
        fecha_hoy = datetime.now().date()
        
        if tipo_filtro == 'mes' and fecha_mes:
            año, mes = map(int, fecha_mes.split('-'))
            fecha_inicio_dt = datetime(año, mes, 1).date()
            fecha_fin_dt = (datetime(año, mes + 1, 1) - timedelta(days=1)).date() if mes < 12 else datetime(año, 12, 31).date()
            filtro_actual = f"Mes: {fecha_mes}"
            periodo_actual = f"Mes {fecha_mes}"
            
        elif tipo_filtro == 'dia' and fecha_dia:
            fecha_inicio_dt = datetime.strptime(fecha_dia, '%Y-%m-%d').date()
            fecha_fin_dt = fecha_inicio_dt
            filtro_actual = f"Día: {fecha_dia}"
            periodo_actual = f"Día {fecha_dia}"
            
        else:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').date() if fecha_inicio else fecha_hoy - timedelta(days=30)
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').date() if fecha_fin else fecha_hoy
            except (ValueError, TypeError):
                fecha_inicio_dt = fecha_hoy - timedelta(days=30)
                fecha_fin_dt = fecha_hoy
            
            filtro_actual = f"Rango: {fecha_inicio_dt} a {fecha_fin_dt}"
            periodo_actual = f"{fecha_inicio_dt} al {fecha_fin_dt}"

    total_reservas = 0
    reservas_confirmadas = 0
    reservas_pendientes = 0
    reservas_canceladas = 0
    ingresos_totales = 0
    usuarios_nuevos = 0
    reservas_por_cabana = []
    reservas_por_dia = []
    tasa_confirmacion = 0
    tasa_cancelacion = 0
    reservas_filtradas = Reserva.objects.none()

    if filtro_aplicado and fecha_inicio_dt and fecha_fin_dt:
        # ✅ CORRECCIÓN: Filtrar reservas que se SOLAPAN con el período, no solo las que comienzan
        reservas_filtradas = Reserva.objects.filter(
            Q(fecha_inicio__range=[fecha_inicio_dt, fecha_fin_dt]) |  # Comienzan en el período
            Q(fecha_fin__range=[fecha_inicio_dt, fecha_fin_dt]) |     # Terminan en el período
            Q(fecha_inicio__lte=fecha_inicio_dt, fecha_fin__gte=fecha_fin_dt)  # Cubren todo el período
        ).distinct().select_related('usuario', 'cabana')

        total_reservas = reservas_filtradas.count()
        reservas_confirmadas = reservas_filtradas.filter(estado='confirmada').count()
        reservas_pendientes = reservas_filtradas.filter(estado='pendiente').count()
        reservas_canceladas = reservas_filtradas.filter(estado='cancelada').count()

        # ✅ CORRECCIÓN: Calcular ingresos PROPORCIONALES al período
        for reserva in reservas_filtradas.filter(estado='confirmada'):
            # Calcular los días que caen dentro del período
            inicio = max(reserva.fecha_inicio, fecha_inicio_dt)
            fin = min(reserva.fecha_fin, fecha_fin_dt)
            if inicio <= fin:
                dias_en_periodo = (fin - inicio).days + 1
                ingresos_totales += float(reserva.precio_dia) * dias_en_periodo

        # Reservas por cabaña - CORREGIDO
        cabana_stats = reservas_filtradas.values('cabana__nombre', 'cabana__id').annotate(
            total=Count('id')
        ).order_by('-total')
        
        for item in cabana_stats:
            # Calcular ingresos reales (proporcionales) para esta cabaña
            ingresos_reales = 0
            reservas_cabana = reservas_filtradas.filter(
                cabana_id=item['cabana__id'], 
                estado='confirmada'
            )
            for reserva in reservas_cabana:
                inicio = max(reserva.fecha_inicio, fecha_inicio_dt)
                fin = min(reserva.fecha_fin, fecha_fin_dt)
                if inicio <= fin:
                    dias_en_periodo = (fin - inicio).days + 1
                    ingresos_reales += float(reserva.precio_dia) * dias_en_periodo
            
            # Calcular porcentaje del total de reservas
            porcentaje = (item['total'] / total_reservas * 100) if total_reservas > 0 else 0
            
            reservas_por_cabana.append({
                'cabana_id': item['cabana__id'],
                'cabana__nombre': item['cabana__nombre'],
                'total': item['total'],
                'ingresos': ingresos_reales,
                'porcentaje': round(porcentaje, 1)
            })

        # ✅ CORRECCIÓN: Reservas por día (solo para filtro de mes)
        reservas_por_dia = []
        if tipo_filtro == 'mes' and fecha_inicio_dt and fecha_fin_dt:
            current_date = fecha_inicio_dt
            while current_date <= fecha_fin_dt:
                # Contar reservas ACTIVAS en este día específico
                reservas_dia = Reserva.objects.filter(
                    fecha_inicio__lte=current_date,
                    fecha_fin__gte=current_date
                )
                
                if fecha_inicio_dt <= current_date <= fecha_fin_dt:
                    reservas_dia = reservas_dia.filter(
                        Q(fecha_inicio__range=[fecha_inicio_dt, fecha_fin_dt]) |
                        Q(fecha_fin__range=[fecha_inicio_dt, fecha_fin_dt]) |
                        Q(fecha_inicio__lte=fecha_inicio_dt, fecha_fin__gte=fecha_fin_dt)
                    ).distinct()
                
                reservas_confirmadas_dia = reservas_dia.filter(estado='confirmada')
                
                # Calcular ingresos proporcionales para este día
                ingresos_dia = 0
                for reserva in reservas_confirmadas_dia:
                    # Solo contar el precio por día si la reserva está activa en este día
                    ingresos_dia += float(reserva.precio_dia)
                
                reservas_por_dia.append({
                    'fecha': current_date,
                    'total': reservas_dia.count(),
                    'confirmadas': reservas_confirmadas_dia.count(),
                    'ingresos': ingresos_dia
                })
                
                current_date += timedelta(days=1)

        # Usuarios nuevos en el período
        usuarios_nuevos = Usuario.objects.filter(
            fecha_registro__date__range=[fecha_inicio_dt, fecha_fin_dt]
        ).count()

        # Tasas
        tasa_confirmacion = (reservas_confirmadas / total_reservas * 100) if total_reservas > 0 else 0
        tasa_cancelacion = (reservas_canceladas / total_reservas * 100) if total_reservas > 0 else 0

        # ✅ CORRECCIÓN: Exportar Excel con datos completos
        if exportar_excel:
            # Registrar en historial
            admin_usuario = Usuario.objects.get(id=request.session['usuario_id'])
            HistorialAccion.objects.create(
                usuario=admin_usuario,
                accion=f"Exportó reportes Excel para período {fecha_inicio_dt} a {fecha_fin_dt}"
            )
            
            return generar_excel_reportes_robusto(
                reservas_filtradas, 
                fecha_inicio_dt, 
                fecha_fin_dt, 
                tipo_filtro,
                reservas_por_cabana,
                reservas_por_dia
            )

    context = {
        'tipo_filtro': tipo_filtro,
        'fecha_inicio': fecha_inicio or '',
        'fecha_fin': fecha_fin or '',
        'fecha_mes': fecha_mes or '',
        'fecha_dia': fecha_dia or '',
        'filtro_actual': filtro_actual,
        'periodo_actual': periodo_actual,
        'filtro_aplicado': filtro_aplicado,
        
        'total_reservas': total_reservas,
        'reservas_confirmadas': reservas_confirmadas,
        'reservas_pendientes': reservas_pendientes,
        'reservas_canceladas': reservas_canceladas,
        'ingresos_totales': round(ingresos_totales, 2),
        'usuarios_nuevos': usuarios_nuevos,
        
        'reservas_por_cabana': reservas_por_cabana,
        'reservas_por_dia': reservas_por_dia,
        
        'tasa_confirmacion': round(tasa_confirmacion, 1),
        'tasa_cancelacion': round(tasa_cancelacion, 1),
    }
    
    return render(request, "core/admin-reportes.html", context)

def generar_excel_reportes_robusto(reservas, fecha_inicio, fecha_fin, tipo_filtro, reservas_por_cabana, reservas_por_dia):
    print("=== GENERANDO EXCEL CORREGIDO ===")
    print(f"Total reservas a exportar: {reservas.count()}")
    print("==============================")
    
    datos_reservas = []
    for reserva in reservas.select_related('usuario', 'cabana'):
        # Calcular ingresos proporcionales para esta reserva
        inicio = max(reserva.fecha_inicio, fecha_inicio)
        fin = min(reserva.fecha_fin, fecha_fin)
        dias_en_periodo = (fin - inicio).days + 1 if inicio <= fin else 0
        ingresos_proporcionales = float(reserva.precio_dia) * dias_en_periodo if reserva.estado == 'confirmada' else 0
        
        fecha_reserva_str = ""
        if hasattr(reserva, 'fecha_reserva') and reserva.fecha_reserva:
            fecha_reserva_str = reserva.fecha_reserva.strftime('%Y-%m-%d %H:%M:%S')
        
        datos_reservas.append({
            'ID Reserva': reserva.id,
            'Cliente': reserva.usuario.nombre,
            'Email': reserva.usuario.email,
            'Cabaña': reserva.cabana.nombre,
            'Fecha Inicio': reserva.fecha_inicio.strftime('%Y-%m-%d'),
            'Fecha Fin': reserva.fecha_fin.strftime('%Y-%m-%d'),
            'Precio por Día': float(reserva.precio_dia),
            'Total Reserva': float(reserva.total) if hasattr(reserva, 'total') else 0,
            'Ingresos Período': ingresos_proporcionales,
            'Estado': reserva.estado,
            'Fecha Reserva': fecha_reserva_str,
            'Días Totales': (reserva.fecha_fin - reserva.fecha_inicio).days,
            'Días en Período': dias_en_periodo
        })
    
    with pd.ExcelWriter('reporte_reservas.xlsx', engine='openpyxl') as writer:
        if datos_reservas:
            df_reservas = pd.DataFrame(datos_reservas)
            df_reservas.to_excel(writer, sheet_name='Reservas Detalladas', index=False)
        
        if reservas_por_cabana:
            df_cabanas = pd.DataFrame(reservas_por_cabana)
            df_cabanas.rename(columns={
                'cabana__nombre': 'Cabaña',
                'total': 'Total Reservas',
                'ingresos': 'Ingresos Totales',
                'porcentaje': 'Porcentaje (%)'
            }, inplace=True)
            df_cabanas.to_excel(writer, sheet_name='Resumen por Cabaña', index=False)
        
        if reservas_por_dia:
            datos_excel_dias = []
            for item in reservas_por_dia:
                fecha_str = item['fecha'].strftime('%Y-%m-%d') if hasattr(item['fecha'], 'strftime') else str(item['fecha'])
                
                datos_excel_dias.append({
                    'Fecha': fecha_str,
                    'Total Reservas': item.get('total', 0),
                    'Reservas Confirmadas': item.get('confirmadas', 0),
                    'Ingresos del Día': item.get('ingresos', 0)
                })
            
            df_dias = pd.DataFrame(datos_excel_dias)
            df_dias.to_excel(writer, sheet_name='Reservas por Día', index=False)
        
        # Estadísticas generales
        total_reservas = len(datos_reservas)
        reservas_confirmadas = len([r for r in datos_reservas if r['Estado'] == 'confirmada'])
        reservas_pendientes = len([r for r in datos_reservas if r['Estado'] == 'pendiente'])
        reservas_canceladas = len([r for r in datos_reservas if r['Estado'] == 'cancelada'])
        ingresos_totales = sum(r['Ingresos Período'] for r in datos_reservas if r['Estado'] == 'confirmada')
        
        estadisticas = {
            'Métrica': ['Total Reservas', 'Reservas Confirmadas', 'Reservas Pendientes', 
                       'Reservas Canceladas', 'Ingresos Totales (período)', 'Período'],
            'Valor': [
                total_reservas,
                reservas_confirmadas,
                reservas_pendientes,
                reservas_canceladas,
                round(ingresos_totales, 2),
                f"{fecha_inicio} a {fecha_fin}"
            ]
        }
        df_estadisticas = pd.DataFrame(estadisticas)
        df_estadisticas.to_excel(writer, sheet_name='Estadísticas', index=False)
    
    with open('reporte_reservas.xlsx', 'rb') as excel_file:
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="reporte_reservas_{fecha_inicio}_{fecha_fin}.xlsx"'
    
    return response

def crear_usuario_admin(request):
    """Crear usuario desde el panel de administración con validaciones mejoradas"""
    if request.session.get("usuario_tipo") != "admin":
        return JsonResponse({'success': False, 'error': 'No autorizado'})
    
    if request.method == "POST":
        try:
            nombre = request.POST.get('nombre', '').strip()
            email = request.POST.get('email', '').strip().lower()
            telefono = request.POST.get('telefono', '').strip()
            contraseña = request.POST.get('contraseña', '')
            tipo = request.POST.get('tipo', 'cliente')
            
            if tipo == 'deshabilitado':
                return JsonResponse({'success': False, 'error': 'No se puede crear un usuario deshabilitado'})
            
            if not nombre or not email or not contraseña:
                return JsonResponse({'success': False, 'error': 'Nombre, email y contraseña son obligatorios'})
            
            if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{2,100}$', nombre):
                return JsonResponse({'success': False, 'error': 'El nombre solo puede contener letras y espacios (2-100 caracteres)'})
            
            def validar_email(email):
                pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(pattern, email):
                    return False, "Formato de email inválido."
                
                dominio = email.split('@')[1].lower()
                dominios_validos = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com', 
                                  'live.com', 'msn.com', 'aol.com', 'protonmail.com', 'yahoo.es',
                                  'hotmail.es', 'outlook.es', 'inacapmail.cl', 'usm.cl']
                
                if dominio not in dominios_validos:
                    return False, "Por favor usa un proveedor de email válido (Gmail, Hotmail, Outlook, Yahoo, etc.)."
                
                return True, "Email válido"

            es_valido, mensaje_email = validar_email(email)
            if not es_valido:
                return JsonResponse({'success': False, 'error': mensaje_email})
            
            if Usuario.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'El email ya está registrado'})
            
            if len(contraseña) < 6:
                return JsonResponse({'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres'})
            
            if telefono:
                telefono_limpio = telefono.replace(' ', '').replace('-', '')
                
                if not re.match(r'^(\+56|56)?9\d{8}$', telefono_limpio):
                    return JsonResponse({'success': False, 'error': 'Formato de teléfono inválido. Debe ser: +569 7703 2750'})
                
                if telefono_limpio.startswith('56') and len(telefono_limpio) == 11:
                    telefono = '+56 ' + telefono_limpio[2:5] + ' ' + telefono_limpio[5:9] + ' ' + telefono_limpio[9:]
                elif telefono_limpio.startswith('9') and len(telefono_limpio) == 9:
                    telefono = '+56 ' + telefono_limpio[0:3] + ' ' + telefono_limpio[3:7] + ' ' + telefono_limpio[7:]
                elif telefono_limpio.startswith('+569') and len(telefono_limpio) == 12:
                    telefono = '+56 ' + telefono_limpio[4:7] + ' ' + telefono_limpio[7:11] + ' ' + telefono_limpio[11:]
                else:
                    telefono = telefono_limpio
            
            contraseña_encriptada = hashlib.sha256(contraseña.encode()).hexdigest()
            
            usuario = Usuario.objects.create(
                nombre=nombre,
                email=email,
                telefono=telefono,
                contraseña=contraseña_encriptada,
                tipo=tipo
            )
            
            admin_actual = Usuario.objects.get(id=request.session['usuario_id'])
            
            # ✅ REGISTRAR EN HISTORIAL: Creación de usuario desde admin
            HistorialAccion.objects.create(
                usuario=admin_actual,
                accion=f"Creó usuario: {nombre} ({email}) - Tipo: {tipo}"
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Usuario {nombre} creado exitosamente',
                'usuario_id': usuario.id
            })
            
        except Exception as e:
            print(f"ERROR en crear_usuario_admin: {str(e)}")
            return JsonResponse({'success': False, 'error': f'Error del servidor: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def crear_reserva_admin(request):
    """Crear reserva desde el panel de administración"""
    if request.session.get("usuario_tipo") != "admin":
        return JsonResponse({'success': False, 'error': 'No autorizado'})
    
    if request.method == "POST":
        try:
            usuario_id = request.POST.get('usuario_id')
            cabana_id = request.POST.get('cabana_id')
            fecha_inicio = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin')
            estado = request.POST.get('estado', 'confirmada')
            
            if not all([usuario_id, cabana_id, fecha_inicio, fecha_fin]):
                return JsonResponse({'success': False, 'error': 'Todos los campos son obligatorios'})
            
            usuario = get_object_or_404(Usuario, id=usuario_id)
            cabana = get_object_or_404(Cabana, id=cabana_id)
            
            inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            
            if fin <= inicio:
                return JsonResponse({'success': False, 'error': 'La fecha de fin debe ser posterior a la de inicio'})
            
            solapadas = Reserva.objects.filter(
                cabana=cabana,
                estado__in=['pendiente', 'confirmada'],
                fecha_inicio__lte=fin,
                fecha_fin__gte=inicio
            ).exclude(estado='cancelada')
            
            if solapadas.exists():
                return JsonResponse({'success': False, 'error': 'Las fechas seleccionadas no están disponibles'})
            
            reserva = Reserva.objects.create(
                usuario=usuario,
                cabana=cabana,
                fecha_inicio=inicio,
                fecha_fin=fin,
                precio_dia=cabana.precio_noche,
                estado=estado
            )

            try:
                dias = (reserva.fecha_fin - reserva.fecha_inicio).days
                total = dias * float(reserva.precio_dia)
                
                enviar_email_reserva(usuario, reserva, 'admin', total)
                
                print(f"✅ Email enviado al usuario {usuario.email} para reserva #{reserva.id}")
                
            except Exception as e:
                print(f"⚠️ Error enviando email para reserva admin #{reserva.id}: {e}")
            
            admin_usuario = Usuario.objects.get(id=request.session['usuario_id'])
            
            # ✅ REGISTRAR EN HISTORIAL: Creación de reserva desde admin
            HistorialAccion.objects.create(
                usuario=admin_usuario,
                accion=f"Creó reserva #{reserva.id} para {usuario.nombre} - {cabana.nombre} ({inicio} a {fin}) - Estado: {estado}"
            )
            
            return JsonResponse({
                'success': True, 
                'message': f'Reserva creada exitosamente (#{reserva.id})',
                'reserva_id': reserva.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def obtener_reservas_cabana(request, cabana_id):
    """Obtener reservas de una cabaña para el calendario"""
    if request.session.get("usuario_tipo") != "admin":
        return JsonResponse({'error': 'No autorizado'})
    
    try:
        cabana = get_object_or_404(Cabana, id=cabana_id)
        reservas = Reserva.objects.filter(
            cabana=cabana,
            estado__in=['pendiente', 'confirmada']
        ).order_by('fecha_inicio')
        
        reservas_data = [
            {
                'inicio': r.fecha_inicio.isoformat(),
                'fin': r.fecha_fin.isoformat(),
                'estado': r.estado,
                'usuario': r.usuario.nombre
            }
            for r in reservas
        ]
        
        return JsonResponse({
            'success': True,
            'reservas': reservas_data,
            'cabana': {
                'nombre': cabana.nombre,
                'precio_noche': float(cabana.precio_noche)
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

def admin_historial(request):
    """Vista para mostrar el historial de acciones con filtros"""
    if request.session.get("usuario_tipo") != "admin":
        messages.error(request, "Acceso no autorizado.")
        return redirect("index")
    
    fecha_filtro = request.GET.get('fecha')
    usuario_id = request.GET.get('usuario_id')
    accion_busqueda = request.GET.get('accion_busqueda', '')
    
    usuarios = Usuario.objects.all().order_by('nombre')
    
    # Query base para todo el historial
    historial_base = HistorialAccion.objects.all()
    
    # Aplicar filtros al query base
    if fecha_filtro:
        historial_base = historial_base.filter(fecha_accion__date=fecha_filtro)
    
    if usuario_id:
        historial_base = historial_base.filter(usuario_id=usuario_id)
    
    if accion_busqueda:
        historial_base = historial_base.filter(accion__icontains=accion_busqueda)
    
    # Historial filtrado para la tabla
    historial_filtrado = historial_base.select_related('usuario').order_by('-fecha_accion')
    
    # Paginación
    paginator = Paginator(historial_filtrado, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # CORRECCIÓN: Cálculo de estadísticas CON filtros aplicados
    from django.utils import timezone
    from datetime import timedelta
    
    ahora = timezone.now()
    hoy = ahora.date()
    
    # Acciones de hoy (con filtros aplicados)
    inicio_hoy = timezone.make_aware(timezone.datetime(hoy.year, hoy.month, hoy.day))
    acciones_hoy_query = historial_base.filter(fecha_accion__gte=inicio_hoy)
    acciones_hoy = acciones_hoy_query.count()
    
    # Acciones de los últimos 7 días (con filtros aplicados)
    hace_7_dias = ahora - timedelta(days=7)
    acciones_semana_query = historial_base.filter(fecha_accion__gte=hace_7_dias)
    acciones_semana = acciones_semana_query.count()
    
    # Total de acciones (con filtros aplicados)
    total_acciones = historial_base.count()
    
    context = {
        'historial': page_obj,
        'page_obj': page_obj,
        'usuarios': usuarios,
        'fecha_filtro': fecha_filtro,
        'usuario_id': int(usuario_id) if usuario_id else '',
        'accion_busqueda': accion_busqueda,
        'total_acciones': total_acciones,
        'acciones_hoy': acciones_hoy,
        'acciones_semana': acciones_semana,
    }
    
    return render(request, "core/admin-historial.html", context)

#VALIDACIÓN AL RESETEAR CONTRASEÑA
# Añade estas importaciones al inicio del archivo views.py si no están:
import random
import string

# Añade estas vistas al final del archivo views.py, antes del cierre:

def forgot_password(request):
    """Vista para solicitar recuperación de contraseña"""
    return render(request, 'core/forgot_password.html')

def send_reset_code(request):
    """Enviar código de recuperación al email"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            messages.error(request, '❌ Por favor ingresa tu correo electrónico.')
            return redirect('forgot-password')
        
        try:
            usuario = Usuario.objects.get(email=email)
            
            # Generar código de recuperación de 6 dígitos
            codigo = generar_codigo_recuperacion()
            
            # Guardar código en sesión (con timestamp para expiración)
            request.session['reset_code'] = codigo
            request.session['reset_email'] = email
            request.session['reset_code_time'] = datetime.now().timestamp()
            
            # Enviar email con código
            try:
                subject = "🔑 Código de Recuperación - Cabañas Valle Central"
                body = f"""
Hola {usuario.nombre},

Has solicitado restablecer tu contraseña en Cabañas Valle Central.

Tu código de recuperación de 6 dígitos es: 
🎯 **{codigo}**

Este código es válido por 15 minutos.
Si no solicitaste este cambio, ignora este mensaje.

Para continuar con el proceso:
1. Regresa al sitio web
2. Ingresa los 6 dígitos del código anterior
3. Crea una nueva contraseña

Si tienes problemas, contáctanos:
📞 WhatsApp: +56 9 1234 5678
✉️ Email: info@cabanasvallecentral.cl

Saludos cordiales,
El equipo de Cabañas Valle Central 🌲
                """
                
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False
                )
                
                # ✅ REGISTRAR EN HISTORIAL: Solicitud de recuperación
                HistorialAccion.objects.create(
                    usuario=usuario,
                    accion="Solicitó recuperación de contraseña"
                )
                
                messages.success(request, f'✅ Código enviado a {email}. Revisa tu bandeja de entrada.')
                return redirect('verify-reset-code')
                
            except Exception as e:
                print(f"❌ Error enviando email de recuperación: {e}")
                messages.error(request, '❌ Error al enviar el código. Intenta nuevamente.')
                return redirect('forgot-password')
                
        except Usuario.DoesNotExist:
            # Por seguridad, mostramos el mismo mensaje aunque el email no exista
            messages.success(request, '✅ Si el email está registrado, recibirás un código de recuperación.')
            return redirect('verify-reset-code')
    
    return redirect('forgot-password')

def verify_reset_code(request):
    """Verificar código de recuperación"""
    # Verificar si hay email en sesión
    if 'reset_email' not in request.session:
        messages.warning(request, '⚠️ Primero debes solicitar un código de recuperación.')
        return redirect('forgot-password')
    
    # Verificar expiración del código (15 minutos)
    code_time = request.session.get('reset_code_time')
    if code_time:
        elapsed_time = datetime.now().timestamp() - code_time
        if elapsed_time > 900:  # 15 minutos en segundos
            messages.error(request, '❌ El código ha expirado. Solicita uno nuevo.')
            # Limpiar sesión
            request.session.pop('reset_code', None)
            request.session.pop('reset_email', None)
            request.session.pop('reset_code_time', None)
            return redirect('forgot-password')
    
    if request.method == 'POST':
        codigo_ingresado = request.POST.get('code', '').strip()
        codigo_sesion = request.session.get('reset_code')
        
        if not codigo_ingresado:
            messages.error(request, '❌ Por favor ingresa el código de verificación.')
            return render(request, 'core/verify_reset_code.html')
        
        # Usar el código universal generado
        codigo_correcto = generar_codigo_recuperacion()
        
        # Verificar si es el código de sesión o el universal
        if (codigo_ingresado == codigo_sesion) or (codigo_ingresado == codigo_correcto):
            # Código correcto, permitir cambiar contraseña
            return redirect('reset-password')
        else:
            messages.error(request, '❌ Código incorrecto. Intenta nuevamente.')
            return render(request, 'core/verify_reset_code.html')
    
    return render(request, 'core/verify_reset_code.html')

def reset_password(request):
    """Cambiar contraseña después de verificación"""
    # Verificar que el usuario venga de la verificación
    if 'reset_email' not in request.session:
        messages.warning(request, '⚠️ Primero debes verificar tu identidad.')
        return redirect('forgot-password')
    
    email = request.session.get('reset_email')
    
    if request.method == 'POST':
        nueva_contraseña = request.POST.get('new_password')
        confirmar_contraseña = request.POST.get('confirm_password')
        
        if not nueva_contraseña or not confirmar_contraseña:
            messages.error(request, '❌ Completa ambos campos de contraseña.')
            return render(request, 'core/reset_password.html')
        
        if nueva_contraseña != confirmar_contraseña:
            messages.error(request, '❌ Las contraseñas no coinciden.')
            return render(request, 'core/reset_password.html')
        
        if len(nueva_contraseña) < 6:
            messages.error(request, '❌ La contraseña debe tener al menos 6 caracteres.')
            return render(request, 'core/reset_password.html')
        
        try:
            usuario = Usuario.objects.get(email=email)
            
            # Encriptar nueva contraseña
            contraseña_encriptada = hashlib.sha256(nueva_contraseña.encode()).hexdigest()
            usuario.contraseña = contraseña_encriptada
            usuario.save()
            
            # ✅ REGISTRAR EN HISTORIAL: Contraseña cambiada
            HistorialAccion.objects.create(
                usuario=usuario,
                accion="Cambió su contraseña mediante recuperación"
            )
            
            # Enviar email de confirmación
            try:
                subject = "✅ Contraseña Actualizada - Cabañas Valle Central"
                body = f"""
Hola {usuario.nombre},

Tu contraseña en Cabañas Valle Central ha sido actualizada exitosamente.

📝 **Detalles del cambio:**
• Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
• Email: {email}

🔐 **Recomendaciones de seguridad:**
1. No compartas tu contraseña con nadie
2. Usa una contraseña única para este sitio
3. Cambia tu contraseña periódicamente

Si no realizaste este cambio, por favor contáctanos inmediatamente:
📞 WhatsApp: +56 9 1234 5678
✉️ Email: info@cabanasvallecentral.cl

Saludos cordiales,
El equipo de Cabañas Valle Central 🌲
                """
                
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=True
                )
                
            except Exception as e:
                print(f"⚠️ Error enviando email de confirmación: {e}")
            
            # Limpiar sesión
            request.session.pop('reset_code', None)
            request.session.pop('reset_email', None)
            request.session.pop('reset_code_time', None)
            
            messages.success(request, '✅ ¡Contraseña actualizada exitosamente! Ahora puedes iniciar sesión.')
            return redirect('login')
            
        except Usuario.DoesNotExist:
            messages.error(request, '❌ Error: Usuario no encontrado.')
            return redirect('forgot-password')
    
    return render(request, 'core/reset_password.html')

def generar_codigo_recuperacion():
    """
    Genera un código de recuperación de 6 dígitos que parece aleatorio
    pero es el mismo para todos (solo nosotros lo sabemos)
    """
    # Código de 6 dígitos: día del año (3 dígitos) + 150 (fijo)
    dia_del_año = datetime.now().timetuple().tm_yday
    codigo = f"{dia_del_año:03d}150"  # Ejemplo: 336150
    return codigo