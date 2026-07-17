(function () {
    'use strict';

    // Centralised badge update (also called by the PDP add-to-cart flow).
    window.updateCartBadge = function (count) {
        ['cart-count', 'cart-count-m'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.textContent = count;
        });
    };

    function naira(n) {
        return '₦ ' + Number(n).toLocaleString('en-NG', {
            minimumFractionDigits: 2, maximumFractionDigits: 2
        });
    }

    var reduceMotion = window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ---- Scroll reveal: one smooth entrance per element, once. -----------
    function initReveal() {
        var els = document.querySelectorAll('[data-reveal]');
        if (!els.length) return;
        if (reduceMotion || !('IntersectionObserver' in window)) {
            els.forEach(function (el) { el.classList.add('is-revealed'); });
            return;
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-revealed');
                    io.unobserve(entry.target);
                }
            });
        }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 });
        els.forEach(function (el) { io.observe(el); });
    }

    // ---- Cart page: optimistic qty + smooth remove over the JSON API. ----
    // Progressive enhancement: the underlying forms still POST and reload when
    // JS/fetch is unavailable; here we intercept to avoid the full-page reload.
    function initCart() {
        var root = document.querySelector('[data-cart]');
        if (!root || !window.fetch) return;

        function post(form) {
            return fetch(form.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: new FormData(form)
            }).then(function (r) { return r.ok ? r.json() : Promise.reject(r); });
        }

        function recalc() {
            var subtotal = 0;
            root.querySelectorAll('[data-line-total]').forEach(function (cell) {
                subtotal += parseFloat(cell.dataset.lineTotal) || 0;
            });
            root.querySelectorAll('[data-cart-subtotal], [data-cart-total]')
                .forEach(function (el) { el.textContent = naira(subtotal); });
        }

        root.querySelectorAll('form[data-qty-form]').forEach(function (form) {
            var input = form.querySelector('input[name="quantity"]');
            if (!input) return;
            // Drop the inline reload-on-change; the JS path takes over.
            input.removeAttribute('onchange');
            input.addEventListener('change', function () {
                var qty = Math.max(1, Math.min(100, parseInt(input.value, 10) || 1));
                input.value = qty;
                var row = form.closest('[data-item]');
                var cell = row.querySelector('[data-line-total]');
                var unit = parseFloat(row.dataset.unitPrice) || 0;
                cell.dataset.lineTotal = unit * qty;   // optimistic
                cell.textContent = naira(unit * qty);
                recalc();
                post(form).catch(function () { window.location.reload(); });
            });
        });

        root.querySelectorAll('form[data-remove-form]').forEach(function (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var row = form.closest('[data-item]');
                post(form).then(function () {
                    if (!reduceMotion) {
                        row.style.transition = 'opacity var(--motion-base) var(--ease-mech)';
                        row.style.opacity = '0';
                    }
                    window.setTimeout(function () {
                        row.remove();
                        recalc();
                        if (!root.querySelectorAll('[data-item]').length) window.location.reload();
                    }, reduceMotion ? 0 : 240);
                    if (window.showToast) window.showToast('Removed from cart.', 'info');
                }).catch(function () { window.location.reload(); });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initReveal();
        initCart();
    });
})();
