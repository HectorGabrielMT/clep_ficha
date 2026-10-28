/**
 * Muestra una notificación tipo Toast en la pantalla
 * @param {string} mensaje - El texto a mostrar
 * @param {string} tipo - 'exito', 'error', 'advertencia', 'info'
 */
function mostrarNotificacion(mensaje, tipo = 'exito') {
    // Buscar o crear el contenedor
    let contenedor = document.getElementById('contenedor-notificaciones');
    if (!contenedor) {
        contenedor = document.createElement('div');
        contenedor.id = 'contenedor-notificaciones';
        contenedor.className = 'fixed top-5 right-5 z-[100] flex flex-col gap-3 min-w-[300px] max-w-md';
        document.body.appendChild(contenedor);
    }

    const toast = document.createElement('div');
    
    // Configuración de colores y estilos según el tipo
    const estilos = {
        exito: 'bg-green-600 border-green-700',
        error: 'bg-red-600 border-red-700',
        advertencia: 'bg-yellow-500 border-yellow-600',
        info: 'bg-blue-600 border-blue-700'
    };

    toast.className = `${estilos[tipo] || estilos.info} text-white px-4 py-3 rounded-lg shadow-2xl border-l-4 flex items-center justify-between transform transition-all duration-300 translate-x-full opacity-0`;
    
    toast.innerHTML = `
        <div class="flex items-center gap-3">
            <span class="text-sm font-medium">${mensaje}</span>
        </div>
        <button class="ml-4 hover:text-gray-200 transition-colors" onclick="this.parentElement.remove()">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
    `;

    contenedor.appendChild(toast);

    // Animación de entrada
    setTimeout(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
        toast.classList.add('translate-x-0', 'opacity-100');
    }, 10);

    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}