// backend/static/js/cart.js
// ─── Cart Operations (no page refresh) ───────────────────────────────────────

function getCookie(name) {
    let value = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(c => {
            const [k, v] = c.trim().split('=');
            if (k === name) value = decodeURIComponent(v);
        });
    }
    return value;
}

// ── Update cart badge count everywhere on the page ───────────────────────────
function updateCartBadge(count) {
    document.querySelectorAll('[data-cart-count]').forEach(el => {
        el.textContent = count;
        el.style.display = count > 0 ? 'flex' : 'none';
    });
}

// ── Add to cart ──────────────────────────────────────────────────────────────
async function addToCart(productId, quantity = 1, size = '', color = '') {
    const btn = document.querySelector(`[data-add-to-cart="${productId}"]`);
    if (btn) {
        btn.disabled = true;
        btn.dataset.originalText = btn.innerHTML;
        btn.innerHTML = `<span class="flex items-center gap-2 justify-center">
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            Adding...
        </span>`;
    }

    try {
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
        formData.append('quantity', quantity);
        if (size)  formData.append('size', size);
        if (color) formData.append('color', color);

        const response = await fetch(`/cart/add/${productId}/`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData,
        });

        const data = await response.json();

        if (response.ok && data.success) {
            updateCartBadge(data.cart_count);
            Toast.success(data.message || 'Added to cart!');

            if (btn) {
                btn.innerHTML = `<span class="flex items-center gap-2 justify-center">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    Added!
                </span>`;
                setTimeout(() => {
                    btn.innerHTML = btn.dataset.originalText;
                    btn.disabled = false;
                }, 1500);
            }
        } else {
            Toast.error(data.message || 'Could not add item.');
            if (btn) { btn.innerHTML = btn.dataset.originalText; btn.disabled = false; }
        }
    } catch (err) {
        console.error(err);
        Toast.error('Network error. Please try again.');
        if (btn) { btn.innerHTML = btn.dataset.originalText; btn.disabled = false; }
    }
}

// ── Remove from cart ─────────────────────────────────────────────────────────
async function removeFromCart(itemId) {
    try {
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));

        const response = await fetch(`/cart/remove/${itemId}/`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData,
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Remove the item row from the DOM
            const row = document.querySelector(`[data-cart-item="${itemId}"]`);
            if (row) {
                row.style.transition = 'all 0.3s ease';
                row.style.opacity = '0';
                row.style.transform = 'translateX(20px)';
                setTimeout(() => {
                    row.remove();
                    updateCartTotals(data);
                }, 300);
            }
            updateCartBadge(data.cart_count);
            Toast.info('Item removed from cart');
        } else {
            Toast.error('Could not remove item.');
        }
    } catch (err) {
        console.error(err);
        Toast.error('Network error. Please try again.');
    }
}

// ── Update cart quantity ──────────────────────────────────────────────────────
async function updateCartQuantity(itemId, quantity) {
    try {
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
        formData.append('quantity', quantity);

        const response = await fetch(`/cart/update/${itemId}/`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body: formData,
        });

        const data = await response.json();

        if (response.ok && data.success) {
            updateCartBadge(data.cart_count);
            updateCartTotals(data);
            // Update item total in DOM
            const itemTotal = document.querySelector(`[data-item-total="${itemId}"]`);
            if (itemTotal) itemTotal.textContent = `₦${data.item_total}`;
        } else {
            Toast.error(data.message || 'Could not update quantity.');
        }
    } catch (err) {
        console.error(err);
        Toast.error('Network error.');
    }
}

// ── Update totals in DOM after cart change ────────────────────────────────────
function updateCartTotals(data) {
    const subtotalEl = document.querySelector('[data-cart-subtotal]');
    const totalEl    = document.querySelector('[data-cart-total]');
    if (subtotalEl && data.subtotal) subtotalEl.textContent = `₦${data.subtotal}`;
    if (totalEl    && data.subtotal) totalEl.textContent    = `₦${data.subtotal}`;
}