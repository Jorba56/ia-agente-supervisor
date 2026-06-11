document.addEventListener('DOMContentLoaded', () => {
    // ==========================================
    // Lógica del Buscador (Search Bar)
    // ==========================================
    const searchInput = document.getElementById('searchInput');
    // Asumimos que los elementos a filtrar tienen la clase 'searchable-item'
    const itemsToSearch = document.querySelectorAll('.searchable-item');

    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            const searchTerm = event.target.value.toLowerCase().trim();

            itemsToSearch.forEach(item => {
                // Busca el texto dentro del elemento
                const textContent = item.textContent.toLowerCase();
                
                if (textContent.includes(searchTerm)) {
                    item.style.display = ''; // Muestra el elemento
                    item.classList.remove('hidden-by-search');
                } else {
                    item.style.display = 'none'; // Oculta el elemento
                    item.classList.add('hidden-by-search');
                }
            });
        });
    }

    // ==========================================
    // Animaciones de Entrada (Intersection Observer)
    // ==========================================
    // Asumimos que los elementos a animar tienen la clase 'animate-on-scroll'
    const animatedElements = document.querySelectorAll('.animate-on-scroll');

    const observerOptions = {
        root: null, // Usa el viewport del navegador
        rootMargin: '0px',
        threshold: 0.15 // Se activa cuando el 15% del elemento es visible
    };

    const scrollObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Añade la clase que dispara la animación CSS (ej. fade-in, slide-up)
                entry.target.classList.add('is-visible');
                
                // Opcional: Dejar de observar el elemento si solo queremos que se anime una vez
                // observer.unobserve(entry.target);
            } else {
                // Opcional: Quitar la clase si queremos que la animación se repita al volver a hacer scroll
                // entry.target.classList.remove('is-visible');
            }
        });
    }, observerOptions);

    // Iniciar la observación de cada elemento
    animatedElements.forEach(element => {
        scrollObserver.observe(element);
    });
});
