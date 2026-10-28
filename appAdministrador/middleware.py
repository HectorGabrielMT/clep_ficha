class HistorialNavegacionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 1. Verificamos que sea un GET exitoso y no sea AJAX
        if (response.status_code == 200 and 
            request.method == 'GET' and 
            not request.headers.get('x-requested-with') == 'XMLHttpRequest'):
            
            # 2. FILTRO DE CONTENIDO: Evita guardar si la respuesta es un archivo (PDF, Excel, etc.)
            content_type = response.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                return response

            # 3. FILTRO DE RUTAS: Evita guardar URLs que suelen ser acciones (opcional)
            url_actual = request.get_full_path()
            palabras_clave_ignorar = ['descargar', 'exportar', 'pdf', 'save', 'delete']
            if any(palabra in url_actual.lower() for palabra in palabras_clave_ignorar):
                return response

            # Lógica de guardado
            historial = request.session.get('historial_personalizado', [])
            if not historial or historial[-1] != url_actual:
                historial.append(url_actual)
                request.session['historial_personalizado'] = historial[-15:]
        
        return response