// Le cœur des favoris (liste et détail). Chaque bouton a data-favori et data-url.

document.addEventListener('click', async (e) => {
    const bouton = e.target.closest('[data-favori]');
    if (!bouton) return;

    const csrf = document.querySelector('[data-csrf]')?.dataset.csrf;

    try {
        const reponse = await fetch(bouton.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf },
        });
        const data = await reponse.json();

        // Pas connecté : on envoie vers la connexion
        if (reponse.status === 401) {
            window.location.href = data.login_url;
            return;
        }

        bouton.classList.toggle('is-active', data.favori);
        bouton.setAttribute('aria-pressed', data.favori);
    } catch (erreur) {
        console.error('Favoris :', erreur);
    }
});