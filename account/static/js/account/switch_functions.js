function switchTab(input) {
    // Sélectionne et retire la classe active de tous les onglets
    document.querySelectorAll('.tab-item').forEach(tab => {
        tab.classList.remove('active');
    });
    // Ajoute la classe active uniquement sur l'onglet cliqué
    input.parentElement.classList.add('active');

    // Met à jour le champ caché avec la valeur de l'onglet sélectionné
    const role = document.getElementById('selected-role').value = input.id === 'tab-organisateur' ? 'organisateur' : 'participant';
    
    console.log("Role sélectionné: " + role);
}




function switchEmailOrPhone(input) {
    // Enlever la classe active de tous les rôles
    document.querySelectorAll('.email_or_phone-item').forEach(item => {
        item.classList.remove('active');
    });

    document.querySelectorAll('.login_input').forEach(b => {
        b.classList.toggle('not_choiced');
    });

    // L'ajouter uniquement sur le parent du bouton cliqué
    input.parentElement.classList.add('active');
}