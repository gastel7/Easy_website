// Thème clair / sombre de l'espace.
// Ce fichier doit être chargé dans le <head>, SANS defer : le thème est appliqué
// avant l'affichage de la page, pour éviter un flash de la mauvaise couleur.

(function () {
    const cle = 'easy-theme';
    let theme = 'dark';

    try {
        theme = localStorage.getItem(cle) || 'dark';
    } catch (erreur) {
        // Stockage indisponible : on reste sur le thème sombre
    }
    document.documentElement.dataset.theme = theme;

    // Le bouton n'existe qu'une fois la page chargée
    document.addEventListener('DOMContentLoaded', () => {
        const bouton = document.querySelector('[data-theme-toggle]');
        if (!bouton) return;

        const majBouton = () => {
            const clair = document.documentElement.dataset.theme === 'light';
            bouton.setAttribute('aria-label', clair ? 'Passer en thème sombre' : 'Passer en thème clair');
        };

        bouton.addEventListener('click', () => {
            const nouveau = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
            document.documentElement.dataset.theme = nouveau;
            try {
                localStorage.setItem(cle, nouveau);
            } catch (erreur) {
                // Pas de mémorisation possible : le choix vaut pour cette page seulement
            }
            majBouton();
        });

        majBouton();
    });
})();