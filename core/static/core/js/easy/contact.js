const nomInput = document.getElementById('full_name');
const emailInput = document.getElementById('email');
const sujetInput = document.getElementById('subject');
const messageInput = document.getElementById('message');


document.getElementById('whatsapp-btn').addEventListener('click', function(e) {
    e.preventDefault();


    const nom = nomInput.value;
    const email = emailInput.value;
    const sujet = sujetInput.value;
    const message = messageInput.value;
    const successBox = document.getElementById('success-message');



    if(!nom || !email || !sujet || !message) {
        alert("Veuillez remplir tous les champs avant d'envoyer.");
        return;
    }

    successBox.style.display = "block";
    successBox.scrollIntoView({ behavior: 'smooth' });


    // Préparation et envoi vers WhatsApp
    const monNumero = "242065581403";
    const texteBrut = `Bonjour, je m'appelle ${nom}.\nEmail: ${email}\nSujet: ${sujet}.\nMessage: ${message}`;
    const url = `https://wa.me/${monNumero}?text=${encodeURIComponent(texteBrut)}`;


    // Ouverture de WhatsApp
    setTimeout(() => {
        window.open(url, '_blank');

        successBox.style.display = "none";
        window.scrollTo({top: 0, behavior: 'smooth'});

    }, 3000);
    
});
