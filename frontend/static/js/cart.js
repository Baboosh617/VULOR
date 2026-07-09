(function () {
    'use strict';

    // Updates the cart count badge in the navbar. Templates that add/remove
    // items via AJAX already build their own request handling inline
    // (product_list.html, index.html, product_detail.html, cart.html) — this
    // just centralizes the badge-update DOM logic so it isn't hand-rolled in
    // four different places going forward.
    window.updateCartBadge = function (count) {
        var badge = document.querySelector('nav .relative span.bg-\\[\\#dc2626\\]');
        if (!badge) return;

        badge.textContent = count;
        badge.classList.add('animate-pulse');
        setTimeout(function () {
            badge.classList.remove('animate-pulse');
        }, 1000);
    };
})();
