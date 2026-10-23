// On récupère toutes les sections de questions (les blocs parents)
const blocks = document.querySelectorAll(".section_questions_content_sub");

blocks.forEach((block) => {
    const open = block.querySelector(".open");
    const answerWrapper = block.querySelector(".div_faq_answer");

    open.addEventListener("click", () => {
        const estDejaOuvert = open.classList.contains("clicked");

        // 1. On ferme TOUS les autres blocs
        blocks.forEach((b) => {
            b.querySelector(".open").classList.remove("clicked");
            b.querySelector(".div_faq_answer").classList.remove("text_open");
        });

        // 2. Si le bloc cliqué n'était pas ouvert, on l'ouvre
        if (!estDejaOuvert) {
            open.classList.add("clicked");
            answerWrapper.classList.add("text_open");
        }
    });
});
