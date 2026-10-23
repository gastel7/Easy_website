// Espace : menu réduit sur ordinateur (préférence mémorisée) et menu en tiroir sur mobile

const layout = document.querySelector('.espace-layout');
const menu = document.querySelector('[data-espace-sidebar]');
const boutonMobile = document.querySelector('[data-espace-toggle]');
const boutonReduire = document.querySelector('[data-espace-reduire]');
const cleStockage = 'espace-menu-reduit';

// Rouvre le menu réduit si l'utilisateur l'avait choisi lors d'une visite précédente
try {
    if (layout && localStorage.getItem(cleStockage) === '1') {
        layout.classList.add('is-reduit');
    }
} catch (erreur) {
    // Stockage indisponible (navigation privée, par exemple) : on garde le menu normal
}

function majBoutonReduire() {
    if (!boutonReduire || !layout) return;
    const reduit = layout.classList.contains('is-reduit');
    boutonReduire.setAttribute('aria-expanded', String(!reduit));
    boutonReduire.setAttribute('aria-label', reduit ? 'Agrandir le menu' : 'Réduire le menu');
}

if (boutonReduire && layout) {
    boutonReduire.addEventListener('click', () => {
        const reduit = layout.classList.toggle('is-reduit');
        try {
            localStorage.setItem(cleStockage, reduit ? '1' : '0');
        } catch (erreur) {
            // Pas de mémorisation possible : le choix vaut pour cette page seulement
        }
        majBoutonReduire();
    });
}

majBoutonReduire();

// Mobile : menu en tiroir
if (boutonMobile && menu) {
    boutonMobile.addEventListener('click', () => {
        const ouvert = menu.classList.toggle('is-ouvert');
        boutonMobile.setAttribute('aria-expanded', String(ouvert));
    });

    // Un clic sur un lien ferme le tiroir
    menu.addEventListener('click', (e) => {
        if (e.target.closest('a')) {
            menu.classList.remove('is-ouvert');
            boutonMobile.setAttribute('aria-expanded', 'false');
        }
    });
}