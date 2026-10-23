// Carrousels (flèche suivante) et tri de la liste

document.querySelectorAll('[data-carousel]').forEach((carousel) => {
    const piste = carousel.querySelector('.carousel-track');
    const suivant = carousel.querySelector('[data-carousel-next]');

    suivant.addEventListener('click', () => {
        piste.scrollBy({ left: piste.clientWidth * 0.8, behavior: 'smooth' });
    });

    // Plus de flèche s'il n'y a rien à faire défiler
    suivant.hidden = piste.scrollWidth <= piste.clientWidth;
});

// Le tri garde les autres filtres de l'URL (recherche, catégorie...)
const tri = document.querySelector('[data-tri]');

if (tri) {
    tri.addEventListener('change', () => {
        const url = new URL(window.location.href);
        url.searchParams.set('tri', tri.value);
        url.searchParams.delete('page');
        window.location.href = url;
    });
}