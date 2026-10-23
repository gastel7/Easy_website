// Notifications : fermeture manuelle ou automatique (5 s, 8 s pour une erreur)

(function () {
    const stack = document.getElementById('notif-stack');
    if (!stack) return;

    function fermer(notif) {
        if (notif.classList.contains('is-leaving')) return;
        notif.classList.add('is-leaving');
        setTimeout(() => notif.remove(), 250); // délai = durée de l'animation de sortie
    }

    stack.querySelectorAll('[data-notif]').forEach((notif) => {
        const duree = notif.classList.contains('notif--error') ? 8000 : 5000;
        notif.style.setProperty('--notif-duree', `${duree}ms`);
        notif.querySelector('[data-notif-close]').addEventListener('click', () => fermer(notif));
        setTimeout(() => fermer(notif), duree);
    });
})();