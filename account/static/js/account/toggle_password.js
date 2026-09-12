document.addEventListener('DOMContentLoaded', function () {
    const toggleButtons = document.querySelectorAll('.toggle-password');

    toggleButtons.forEach(function (btn) {
        const input = btn.parentElement.querySelector('input');
        if (!input) return;

        btn.addEventListener('click', function () {
            const willShow = input.type === 'password';
            input.type = willShow ? 'text' : 'password';

            btn.classList.toggle('is-visible', willShow);
            btn.setAttribute(
                'aria-label',
                willShow ? 'Masquer le mot de passe' : 'Afficher le mot de passe'
            );
        });
    });
});

