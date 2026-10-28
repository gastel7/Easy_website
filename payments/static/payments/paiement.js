// Page de paiement : lancement de la collecte Tamo, sondage du statut,
// et portail TamoCheckout (optionnel). Le serveur reste la seule source de vérité.

(function () {
    const zone = document.querySelector('[data-paiement]');
    if (!zone) return;

    const form = zone.querySelector('[data-form-paiement]');
    const boutonLancer = zone.querySelector('[data-lancer]');
    const boutonCheckout = zone.querySelector('[data-checkout]');
    const zoneStatut = zone.querySelector('[data-zone-statut]');
    const message = zone.querySelector('[data-message]');

    const urls = {
        lancer: zone.dataset.urlLancer,
        statut: zone.dataset.urlStatut,
        checkout: zone.dataset.urlCheckout,
        billets: zone.dataset.urlBillets,
    };

    const csrf = document.querySelector('[data-csrf]')?.dataset.csrf || '';
    const entetes = {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrf};

    const STATUTS_FINALS = ['reussi', 'echoue', 'expire', 'annule'];
    const DELAI_SONDAGE = 4000;              // 15 appels/min : large sous la limite de 120 lectures/min
    const DUREE_MAX = 30 * 60 * 1000;        // la collecte expire après 30 minutes chez Tamo

    const texteInitialBouton = boutonLancer ? boutonLancer.textContent : '';
    let minuterie = null;
    let debutTentative = Date.now();

    function afficher(texte, etat) {
        zoneStatut.hidden = false;
        zoneStatut.dataset.etat = etat;
        if (texte) message.textContent = texte;
    }

    function arreter() {
        if (minuterie) { clearTimeout(minuterie); minuterie = null; }
    }

    function reactiver() {
        if (boutonLancer) { boutonLancer.disabled = false; boutonLancer.textContent = texteInitialBouton; }
        if (boutonCheckout) boutonCheckout.disabled = false;
    }

    function masquerActions() {
        if (boutonLancer) boutonLancer.hidden = true;
        if (boutonCheckout) boutonCheckout.hidden = true;
    }

    async function appeler(url, options) {
        const reponse = await fetch(url, options || {});
        let donnees = {};
        try { donnees = await reponse.json(); } catch (_) { /* réponse non JSON */ }
        if (!reponse.ok) {
            const erreur = new Error(
                donnees.erreur
                || (donnees.erreurs && Object.values(donnees.erreurs).flat()[0])
                || 'Une erreur est survenue.'
            );
            throw erreur;
        }
        return donnees;
    }

    // Retourne true si l'opération est terminée (payé, ou statut définitif)
    function traiterEtat(etat) {
        if (etat.paye) {
            arreter();
            afficher('Paiement confirmé : vos billets sont valides.', 'reussi');
            setTimeout(() => { window.location.href = urls.billets; }, 1800);
            return true;
        }
        if (STATUTS_FINALS.includes(etat.statut)) {
            arreter();
            afficher(etat.message || 'Le paiement aboutit.', etat.statut);
            reactiver();
            return true;
        }
        afficher(etat.message || "En attente de la confirmation de l'opérateur…", 'attente');
        return false;
    }

    async function sonder() {
        if (Date.now() - debutTentative > DUREE_MAX) {
            arreter();
            afficher("La demande de paiement a expiré. Vous pouvez relancer un paiement.", 'expire');
            reactiver();
            return;
        }
        try {
            const etat = await appeler(urls.statut);
            if (!traiterEtat(etat)) minuterie = setTimeout(sonder, DELAI_SONDAGE);
        } catch (_) {
            // Réseau ou API momentanément indisponible : on recommence un peu plus tard
            minuterie = setTimeout(sonder, Math.round(DELAI_SONDAGE * 1.5));
        }
    }

    function demarrerSondage() {
        arreter();
        minuterie = setTimeout(sonder, 1200);
    }

    // --- Lancement de la collecte depuis le formulaire -----------------------
    if (form) {
        form.addEventListener('submit', async (evenement) => {
            evenement.preventDefault();
            debutTentative = Date.now();
            if (boutonLancer) { boutonLancer.disabled = true; boutonLancer.textContent = 'Envoi de la demande…'; }

            try {
                const etat = await appeler(urls.lancer, {
                    method: 'POST',
                    headers: entetes,
                    body: new FormData(form),
                });
                masquerActions();
                afficher(etat.message || 'Demande envoyée…', 'attente');
                demarrerSondage();
            } catch (erreur) {
                afficher(erreur.message, 'echoue');
                reactiver();
            }
        });
    }

    // --- Portail TamoCheckout (SDK) -----------------------------------------
    let chargementSdk = null;

    function ouvrirCheckout() {
        if (!window.TamoCheckout) {
            if (chargementSdk) return;
            chargementSdk = document.createElement('script');
            chargementSdk.src = zone.dataset.sdkUrl;
            chargementSdk.onload = ouvrirCheckout;
            chargementSdk.onerror = () => {
                chargementSdk = null;
                afficher("Impossible de charger Tamo Checkout. Utilisez le paiement par numéro.", 'echoue');
            };
            document.head.appendChild(chargementSdk);
            return;
        }

        if (boutonCheckout) boutonCheckout.disabled = true;

        window.TamoCheckout.open({
            publicKey: zone.dataset.publicKey,
            productId: zone.dataset.produit,
            amount: Number(zone.dataset.montant),
            currency: zone.dataset.devise,
            merchant: zone.dataset.marchand,
            reference: zone.dataset.reference,
            description: zone.dataset.description,
            onSuccess: async (donnees) => {
                // Le navigateur n'est pas cru : le serveur revérifie auprès de l'API Tamo
                debutTentative = Date.now();
                try {
                    const etat = await appeler(urls.checkout, {
                        method: 'POST',
                        headers: {...entetes, 'Content-Type': 'application/x-www-form-urlencoded'},
                        body: new URLSearchParams({reference: donnees.reference || ''}),
                    });
                    masquerActions();
                    if (!traiterEtat(etat)) {
                        afficher('Confirmation du paiement en cours…', 'attente');
                        demarrerSondage();
                    }
                } catch (erreur) {
                    masquerActions();
                    afficher(erreur.message || 'Paiement reçu, confirmation en cours…', 'attente');
                    demarrerSondage();
                }
            },
            onClose: () => { if (boutonCheckout) boutonCheckout.disabled = false; },
            onError: (erreur) => {
                afficher(erreur?.message || 'Paiement interrompu.', 'echoue');
                if (boutonCheckout) boutonCheckout.disabled = false;
            },
        });
    }

    if (boutonCheckout) boutonCheckout.addEventListener('click', ouvrirCheckout);

    // --- État initial --------------------------------------------------------
    const statutInitial = zone.dataset.statutInitial;
    if (statutInitial === 'en_cours') {
        afficher(message.textContent || "En attente de la confirmation de l'opérateur…", 'attente');
        masquerActions();
        demarrerSondage();
    } else if (STATUTS_FINALS.includes(statutInitial)) {
        afficher(message.textContent || 'Paiement non abouti.', statutInitial);
    }
})();
