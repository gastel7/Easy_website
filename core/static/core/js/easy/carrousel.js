document.addEventListener("DOMContentLoaded", function() {
    const track = document.getElementById('carrouselTrack');
    if (!track) return;

    const cards = Array.from(track.children);
    
    // Si tu as trop peu de cartes, on évite le traitement
    if (cards.length === 0) return;

    // Clone chaque carte existante et l'ajoute à la fin du conteneur
    // Cela crée l'illusion d'une boucle infinie parfaite
    cards.forEach(card => {
        const clone = card.cloneNode(true);
        track.appendChild(clone);
    });
});