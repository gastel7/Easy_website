(function () {

// Formulaire événement : étapes (PC et mobile), aperçu en direct, zones de dépôt, images supplémentaires, billets

const layout = document.querySelector('.event-layout');

if (layout) {
    const form = layout.querySelector('form');
    const preview = layout.querySelector('.event-preview');
    const steps = [...form.querySelectorAll('.step')];          // 1 à 4
    const stepperItems = [...form.querySelectorAll('[data-steps] li')];
    const prevBtn = form.querySelector('[data-prev]');
    const nextBtn = form.querySelector('[data-next]');
    const submitBtn = form.querySelector('[data-submit]');
    const slots = [...form.querySelectorAll('[data-slot]')];    // image_2 à image_5
    const urls = {};                                             // image principale et vidéo choisies
    const maxImages = 4;
    const maxTickets = 10;
    let current = 1;

    // Lit un élément de l'aperçu. S'il manque dans le gabarit, on renvoie null au lieu de planter.
    const pv = (selecteur) => (preview ? preview.querySelector(selecteur) : null);

    form.noValidate = true; // on gère la validation étape par étape


    // ---------- Étapes (PC et mobile) ----------
    // Placé en premier : même si l'aperçu ou les billets échouent, les étapes fonctionnent.

    function goTo(n, scroll = true) {
        current = Math.max(1, Math.min(steps.length, n));
        layout.dataset.step = current;
        steps.forEach((s) => s.classList.toggle('is-active', Number(s.dataset.step) === current));
        stepperItems.forEach((li, k) => {
            li.classList.toggle('is-active', k + 1 === current);
            li.classList.toggle('is-done', k + 1 < current);
        });
        if (prevBtn) prevBtn.hidden = current === 1;
        if (nextBtn) nextBtn.hidden = current === steps.length;
        if (submitBtn) submitBtn.hidden = current !== steps.length;
        if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function stepIsValid() {
        const step = steps[current - 1];
        if (!step) return true;
        return [...step.querySelectorAll('input, select, textarea')]
            .filter((field) => !field.closest('.ticket-card--removed'))
            .every((field) => field.reportValidity());
    }

    nextBtn?.addEventListener('click', () => {
        if (stepIsValid()) goTo(current + 1);
    });

    prevBtn?.addEventListener('click', () => goTo(current - 1));

    // Entrée dans un champ = étape suivante (pas d'envoi à moitié rempli)
    form.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || current === steps.length) return;
        if (['TEXTAREA', 'BUTTON'].includes(e.target.tagName) || e.target.type === 'file') return;
        e.preventDefault();
        if (stepIsValid()) goTo(current + 1);
    });

    // Champ invalide dans une autre étape : on y retourne
    form.addEventListener('invalid', (e) => {
        const step = e.target.closest('.step');
        if (step && !step.classList.contains('is-active')) goTo(Number(step.dataset.step), false);
    }, true);

    // Envoi : on vérifie toutes les étapes, et on va à la première incomplète
    form.addEventListener('submit', (e) => {
        for (let i = 1; i <= steps.length; i++) {
            goTo(i, false);
            if (!stepIsValid()) { e.preventDefault(); return; }
        }
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Envoi en cours…';
        }
    });

    // Erreur renvoyée par Django : on ouvre l'étape concernée
    const errorStep = form.querySelector('.errorlist')?.closest('.step');
    goTo(errorStep ? Number(errorStep.dataset.step) : 1, false);


    // ---------- Aperçu en direct ----------

    function value(name) {
        const field = form.elements[name];
        if (!field) return '';
        if (field.tagName === 'SELECT') return field.value ? field.selectedOptions[0].textContent.trim() : '';
        return field.value.trim();
    }

    // "2026-12-25T18:00" -> { date: "25/12/2026", time: "18:00" }
    function splitDate(v) {
        const m = (v || '').match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/);
        return m ? { date: `${m[3]}/${m[2]}/${m[1]}`, time: m[4] || '' } : { date: v || '', time: '' };
    }

    function setText(key, text) {
        const el = pv(`[data-pv="${key}"]`);
        if (!el) return;
        el.textContent = text;
        (el.closest('li') || el).hidden = !text;
    }

    function updateText() {
        if (!preview) return;
        const debut = splitDate(form.elements.date_debut?.value);
        const fin = splitDate(form.elements.date_fin?.value);
        const places = value('nombre_de_places');
        const age = value('age_minimum');
        const statut = value('statut');

        setText('titre', value('titre') || "Titre de l'événement");
        setText('categorie', value('categorie') || 'Événement');
        setText('dates', [debut.date, fin.date].filter(Boolean).join(' - '));
        setText('heures', [debut.time, fin.time].filter(Boolean).join(' - '));
        setText('lieu', [value('lieu'), value('adresse'), value('ville'), value('pays')].filter(Boolean).join(', '));
        setText('places', places ? `${places} places` : '');
        setText('age', age ? `Âge min. : ${age} ans` : '');
        setText('statut', statut);
        setText('description', value('description'));

        const badge = pv('[data-pv="statut"]');
        if (badge) badge.dataset.state = /publi/i.test(statut) ? 'on' : 'off';
    }

    function updateMedia() {
        const cover = pv('[data-pv-cover]');
        if (cover) {
            cover.hidden = !urls.image_principale;
            if (urls.image_principale) cover.src = urls.image_principale;
        }
        const coverEmpty = pv('[data-pv-cover-empty]');
        if (coverEmpty) coverEmpty.hidden = !!urls.image_principale;

        const thumbs = slots
            .map((slot) => slot.querySelector('[data-slot-thumb]'))
            .filter((t) => t && !t.hidden && t.src);
        const gallery = pv('[data-pv-gallery]');
        if (gallery) gallery.replaceChildren(...thumbs.map((t) => Object.assign(new Image(), { src: t.src, alt: '' })));
        const galleryWrap = pv('[data-pv-gallery-wrap]');
        if (galleryWrap) galleryWrap.hidden = !thumbs.length;
    }

    function updateAll() {
        updateText();
        updateTickets();
    }


    // ---------- Zones de dépôt : image principale et vidéo ----------

    // Glisser-déposer : le fichier arrive dans l'input, puis on prévient le script
    function bindDrag(zone, input) {
        ['dragenter', 'dragover'].forEach((ev) => zone.addEventListener(ev, (e) => {
            e.preventDefault();
            zone.classList.add('is-dragover');
        }));
        ['dragleave', 'drop'].forEach((ev) => zone.addEventListener(ev, () => zone.classList.remove('is-dragover')));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change'));
        });
    }

    form.querySelectorAll('.dropzone:not(.dropzone--multi)').forEach((zone) => {
        const input = zone.querySelector('input[type="file"]');
        if (!input) return;
        const isVideo = input.name === 'video';
        const maxMo = isVideo ? 50 : 5;
        let added = []; // ce que le script ajoute dans ou sous la zone

        // En édition, Django ajoute un lien vers le fichier actuel et une case "Effacer".
        // On garde le lien (pour l'aperçu) et la case, on enlève le reste du texte.
        const oldUrl = zone.querySelector('a')?.href || '';
        const clearBox = zone.querySelector('input[type="checkbox"]');
        [...zone.childNodes].forEach((node) => {
            const keep = node === input || node === clearBox || node.classList?.contains('dropzone-ui');
            if (!keep) node.remove();
        });
        if (clearBox) clearBox.hidden = true;

        function empty() {
            added.forEach((el) => el.remove());
            added = [];
            zone.classList.remove('has-file');
            if (urls[input.name]?.startsWith('blob:')) URL.revokeObjectURL(urls[input.name]);
            delete urls[input.name];
        }

        function removeButton(onClick) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'file-remove';
            btn.setAttribute('aria-label', 'Retirer le fichier');
            btn.textContent = '×';
            btn.addEventListener('click', onClick);
            return btn;
        }

        // Affiche un fichier : l'image remplit la zone, la vidéo est une ligne sous la zone
        function show(url, name, size, onRemove) {
            urls[input.name] = url;
            if (isVideo) {
                const row = document.createElement('div');
                row.className = 'file-preview file-preview--video';
                row.innerHTML = '<video muted preload="metadata"></video><div class="file-info"><strong></strong><small></small></div>';
                row.querySelector('video').src = `${url}#t=0.5`;
                row.querySelector('strong').textContent = name;
                row.querySelector('small').textContent = size;
                if (onRemove) row.append(removeButton(onRemove));
                zone.after(row);
                added.push(row);
            } else {
                const img = Object.assign(new Image(), { src: url, alt: '', className: 'dropzone-thumb' });
                zone.append(img);
                zone.classList.add('has-file');
                added.push(img);
                if (onRemove) {
                    const btn = removeButton(onRemove);
                    zone.append(btn);
                    added.push(btn);
                }
            }
            updateMedia();
        }

        // Fichier déjà enregistré : affiché tant que la case "Effacer" n'est pas cochée
        function showOld() {
            if (!oldUrl || (clearBox && clearBox.checked)) return updateMedia();
            const name = decodeURIComponent(oldUrl.split('?')[0].split('/').pop());
            show(oldUrl, name, '', () => {
                empty();
                if (clearBox) clearBox.checked = true; // supprimé à l'envoi
                updateMedia();
            });
        }

        input.addEventListener('change', () => {
            empty();
            const file = input.files[0];

            if (file && file.size > maxMo * 1048576) {
                alert(`Ce fichier dépasse la taille maximale (${maxMo} Mo).`);
                input.value = '';
                return showOld();
            }
            if (!file) return showOld();

            if (clearBox) clearBox.checked = false;
            const size = file.size >= 1048576
                ? `${(file.size / 1048576).toFixed(1)} Mo`
                : `${Math.max(1, Math.round(file.size / 1024))} Ko`;

            show(URL.createObjectURL(file), file.name, size, () => {
                empty();
                input.value = '';
                showOld();
            });
        });

        bindDrag(zone, input);
        showOld();
    });


    // ---------- Images supplémentaires : un sélecteur, 4 emplacements ----------
    // Chaque emplacement est le vrai champ image_2 à image_5 (caché) : le modèle ne change pas.

    const picker = form.querySelector('[data-images-picker]');
    const pickerMessage = form.querySelector('[data-images-message]');

    // Affiche ou cache la miniature et le × d'un emplacement
    function paintSlot(slot) {
        const input = slot.querySelector('input[type="file"]');
        const clear = slot.querySelector('input[type="checkbox"]');
        const thumb = slot.querySelector('[data-slot-thumb]');
        const remove = slot.querySelector('[data-slot-remove]');
        if (!input || !thumb || !remove) return;
        const has = input.files.length > 0 || (!!clear && !clear.checked);
        thumb.hidden = !has;
        remove.hidden = !has;
    }

    // Met un fichier dans un emplacement (null = emplacement vide)
    function setSlot(slot, file) {
        const input = slot.querySelector('input[type="file"]');
        const clear = slot.querySelector('input[type="checkbox"]');
        const thumb = slot.querySelector('[data-slot-thumb]');
        if (!input || !thumb) return;
        const dt = new DataTransfer();
        if (file) dt.items.add(file);
        input.files = dt.files;
        if (clear) clear.checked = !file; // image déjà enregistrée : supprimée à l'envoi si l'emplacement est vidé
        if (file) thumb.src = URL.createObjectURL(file);
        paintSlot(slot);
    }

    picker?.addEventListener('change', () => {
        const files = [...picker.files];
        picker.value = ''; // pour pouvoir choisir les mêmes fichiers une deuxième fois
        if (pickerMessage) pickerMessage.hidden = files.length <= maxImages;
        if (files.length > maxImages) return;
        slots.forEach((slot, i) => setSlot(slot, files[i] || null));
        updateMedia();
    });

    slots.forEach((slot) => {
        slot.querySelector('[data-slot-remove]')?.addEventListener('click', () => {
            setSlot(slot, null);
            updateMedia();
        });
    });

    const zoneMulti = form.querySelector('.dropzone--multi');
    if (picker && zoneMulti) bindDrag(zoneMulti, picker);


    // ---------- Billets ----------

    const ticketList = form.querySelector('[data-ticket-list]');
    const ticketTemplate = document.getElementById('ticket-template');
    const ticketTotal = ticketList
        ? form.querySelector(`input[name="${ticketList.dataset.prefix}-TOTAL_FORMS"]`)
        : null;

    function visibleTickets() {
        if (!ticketList) return [];
        return [...ticketList.querySelectorAll('[data-ticket-card]')]
            .filter((card) => !card.classList.contains('ticket-card--removed'));
    }

    function numberTickets() {
        visibleTickets().forEach((card, i) => {
            const numero = card.querySelector('[data-ticket-number]');
            if (numero) numero.textContent = `Billet #${i + 1}`;
        });
    }

    function updateTickets() {
        numberTickets();
        const list = pv('[data-pv-tickets]');
        if (!list) return;
        list.replaceChildren(...visibleTickets().map((card) => {
            const li = document.createElement('li');
            const nom = card.querySelector('input[name$="-nom"]')?.value || 'Billet';
            const prix = card.querySelector('input[name$="-prix"]')?.value;
            li.textContent = `${nom} · ${prix ? Number(prix).toLocaleString('fr-FR') + ' XAF' : 'Gratuit'}`;
            return li;
        }));
        list.hidden = !list.children.length;
    }

    form.querySelector('[data-ticket-add]')?.addEventListener('click', () => {
        if (!ticketList || !ticketTemplate || !ticketTotal) return;
        if (visibleTickets().length >= maxTickets) return;
        const index = Number(ticketTotal.value);
        const holder = document.createElement('div');
        holder.innerHTML = ticketTemplate.innerHTML.replaceAll('__prefix__', index);
        ticketList.append(holder.firstElementChild);
        ticketTotal.value = index + 1;
        updateAll();
    });

    // Le billet reste dans le formulaire, marqué DELETE : le formset l'ignore
    ticketList?.addEventListener('click', (e) => {
        const remove = e.target.closest('[data-ticket-remove]');
        if (!remove) return;
        const card = remove.closest('[data-ticket-card]');
        card.querySelector('input[name$="-DELETE"]')?.toggleAttribute('checked', true);
        const deleteBox = card.querySelector('input[name$="-DELETE"]');
        if (deleteBox) deleteBox.checked = true;
        card.querySelectorAll('[required]').forEach((field) => { field.required = false; });
        card.classList.add('ticket-card--removed');
        updateAll();
    });


    // ---------- Init ----------

    form.addEventListener('input', updateAll);
    form.addEventListener('change', updateAll);

    slots.forEach(paintSlot);
    updateAll();
    updateMedia();
}

})();