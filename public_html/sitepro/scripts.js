// script.js

// Функция, которая будет вызвана после загрузки контента страницы
document.addEventListener("DOMContentLoaded", function() {
    // Получаем элемент хедера
    var header = document.getElementById("wb_header_a188dd94d37a0374c81c636d09cd1f05");

    // Задаем начальное положение хедера
    var prevScrollPos = window.pageYOffset;
    var headerHeight = header.clientHeight;

    // Функция, которая будет вызываться при прокрутке страницы
    function handleScroll() {
        // Получаем новое положение прокрутки страницы
        var currentScrollPos = window.pageYOffset;

        // Определяем направление прокрутки и рассчитываем положение хедера
        if (prevScrollPos > currentScrollPos) {
            // Прокрутка вверх
            if (currentScrollPos < headerHeight) {
                header.style.top = "0";
            } else {
                header.style.top = "0";
            }
        } else {
            // Прокрутка вниз
            if (currentScrollPos > headerHeight) {
                header.style.top = "-" + headerHeight + "px";
            }
        }

        // Обновляем предыдущее положение прокрутки
        prevScrollPos = currentScrollPos;
    }

    // Добавляем обработчик события прокрутки страницы
    window.addEventListener("scroll", handleScroll);
});
