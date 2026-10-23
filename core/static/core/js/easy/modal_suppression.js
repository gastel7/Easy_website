// Modal de suppression : ouverte par les boutons « Supprimer », envoie le formulaire en POST

(function () {
    const modal = document.getElementById('modal-suppression');
    if (!modal) return;

    const form = modal.querySelector('[data-modal-form]');
    const titre = modal.querySelector('[data-modal-titre]');
    const annuler = modal.querySelector('[data-modal-annuler]');
    const envoyer = form.querySelector('[type="submit"]');
    let declencheur = null; // le bouton qui a ouvert la modal, pour lui rendre le focus

    function ouvrir(bouton) {
        declencheur = bouton;
        form.action = bouton.dataset.action;
        titre.textContent = bouton.dataset.titre;
        modal.hidden = false;
        annuler.focus();
    }

    function fermer() {
        modal.hidden = true;
        if (declencheur) declencheur.focus();
    }

    document.addEventListener('click', (e) => {
        const bouton = e.target.closest('[data-supprimer]');
        if (bouton) ouvrir(bouton);
    });

    annuler.addEventListener('click', fermer);

    // Clic en dehors de la carte
    modal.addEventListener('click', (e) => {
        if (e.target === modal) fermer();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.hidden) fermer();
    });

    // Évite un double envoi
    form.addEventListener('submit', () => {
        envoyer.disabled = true;
    });
})();