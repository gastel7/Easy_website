// Page détail : billets de plusieurs catégories, total, limite par commande, copie du lien

const reserve = document.querySelector('[data-reserve]');
const bouton = reserve?.querySelector('[data-reserver]');

if (reserve && bouton) {
    const billets = [...reserve.querySelectorAll('[data-ticket]')];
    const total = reserve.querySelector('[data-total]');
    const limite = reserve.querySelector('[data-limite]');
    const maxCommande = Number(reserve.dataset.maxCommande || 10);

    const formater = (n) => `${n.toLocaleString('fr-FR')} FCFA`;

    // Quantité choisie dans une catégorie (0 si la catégorie n'est pas disponible)
    const quantiteDe = (billet) => Number(billet.querySelector('[data-quantite-champ]')?.value || 0);

    function mettreAJour() {
        // Nombre de billets choisis, toutes catégories confondues
        const nombre = billets.reduce((somme, billet) => somme + quantiteDe(billet), 0);
        let montant = 0;

        billets.forEach((billet) => {
            const champ = billet.querySelector('[data-quantite-champ]');
            if (!champ) return; // catégorie complète, pas encore ouverte ou terminée

            const quantite = quantiteDe(billet);
            // Maximum pour cette catégorie : son stock, mais aussi ce qui reste dans la commande
            const maxPourCetteCategorie = Math.min(Number(billet.dataset.max), maxCommande - (nombre - quantite));

            montant += quantite * Number(billet.dataset.prix);
            billet.querySelector('[data-quantite]').textContent = quantite;
            billet.classList.toggle('is-choisi', quantite > 0);
            billet.querySelector('[data-moins]').disabled = quantite <= 0;
            billet.querySelector('[data-plus]').disabled = quantite >= maxPourCetteCategorie;
        });

        // Que des billets gratuits : on écrit « Gratuit » plutôt que « 0 FCFA »
        total.textContent = nombre > 0 && montant === 0 ? 'Gratuit' : formater(montant);
        bouton.disabled = nombre === 0;
        limite.hidden = nombre < maxCommande;
    }

    reserve.addEventListener('click', (e) => {
        const moins = e.target.closest('[data-moins]');
        const plus = e.target.closest('[data-plus]');
        if (!moins && !plus) return;

        const champ = e.target.closest('[data-ticket]').querySelector('[data-quantite-champ]');
        champ.value = Math.max(0, Number(champ.value) + (plus ? 1 : -1));
        mettreAJour();
    });

    // Évite un double envoi
    reserve.addEventListener('submit', () => {
        bouton.disabled = true;
        bouton.textContent = 'Réservation en cours…';
    });

    mettreAJour();
}


// Copier le lien de l'événement
const copier = document.querySelector('[data-copier-lien]');

if (copier) {
    copier.addEventListener('click', async () => {
        const texte = copier.textContent;

        try {
            await navigator.clipboard.writeText(copier.dataset.url);
            copier.textContent = 'Lien copié !';
        } catch (erreur) {
            window.prompt('Copie ce lien :', copier.dataset.url);
        }

        setTimeout(() => { copier.textContent = texte; }, 2000);
    });
}