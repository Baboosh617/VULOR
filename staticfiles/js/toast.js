// backend/static/js/toast.js
// ─── Toast Notification System ───────────────────────────────────────────────
// Usage:
//   Toast.success('Item added to cart')
//   Toast.error('Something went wrong')
//   Toast.info('Your session expires soon')
//   Toast.warning('Only 2 items left in stock')

const Toast = (() => {
    let container = null;

    const ICONS = {
        success: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>`,
        error:   `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                  </svg>`,
        warning: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                  </svg>`,
        info:    `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>`,
    };

    const STYLES = {
        success: 'bg-[#111111] border-l-4 border-green-500 text-white',
        error:   'bg-[#111111] border-l-4 border-[#dc2626] text-white',
        warning: 'bg-[#111111] border-l-4 border-yellow-500 text-white',
        info:    'bg-[#111111] border-l-4 border-blue-500 text-white',
    };

    const ICON_STYLES = {
        success: 'text-green-500',
        error:   'text-[#dc2626]',
        warning: 'text-yellow-500',
        info:    'text-blue-500',
    };

    function getContainer() {
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'fixed top-4 right-4 z-[9999] flex flex-col gap-3 pointer-events-none';
            container.style.maxWidth = '380px';
            container.style.width = '100%';
            document.body.appendChild(container);
        }
        return container;
    }

    function show(message, type = 'info', duration = 4000) {
        const c = getContainer();

        const toast = document.createElement('div');
        toast.className = [
            STYLES[type],
            'flex items-start gap-3 px-4 py-3 rounded-lg shadow-2xl',
            'pointer-events-auto cursor-pointer',
            'transform transition-all duration-300 ease-out',
            'translate-x-full opacity-0',
        ].join(' ');

        toast.innerHTML = `
            <div class="flex-shrink-0 mt-0.5 ${ICON_STYLES[type]}">
                ${ICONS[type]}
            </div>
            <p class="flex-1 text-sm font-medium leading-relaxed">${message}</p>
            <button class="flex-shrink-0 ml-2 text-gray-500 hover:text-white transition-colors mt-0.5">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        `;

        c.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toast.classList.remove('translate-x-full', 'opacity-0');
                toast.classList.add('translate-x-0', 'opacity-100');
            });
        });

        // Close on click
        const closeBtn = toast.querySelector('button');
        closeBtn.addEventListener('click', () => dismiss(toast));
        toast.addEventListener('click', () => dismiss(toast));

        // Auto-dismiss
        const timer = setTimeout(() => dismiss(toast), duration);

        // Pause timer on hover
        toast.addEventListener('mouseenter', () => clearTimeout(timer));
        toast.addEventListener('mouseleave', () => {
            setTimeout(() => dismiss(toast), 1500);
        });

        return toast;
    }

    function dismiss(toast) {
        toast.classList.add('translate-x-full', 'opacity-0');
        toast.addEventListener('transitionend', () => {
            toast.remove();
        }, { once: true });
    }

    // Convert any Django messages present in the DOM to toasts
    function absorbDjangoMessages() {
        const djangoMessages = document.querySelectorAll('[data-django-message]');
        djangoMessages.forEach(el => {
            const msg  = el.dataset.djangoMessage;
            const tags = el.dataset.djangoTags || 'info';

            let type = 'info';
            if (tags.includes('success')) type = 'success';
            else if (tags.includes('error'))   type = 'error';
            else if (tags.includes('warning')) type = 'warning';

            show(msg, type);
            el.remove();
        });
    }

    document.addEventListener('DOMContentLoaded', absorbDjangoMessages);

    return { show, success: m => show(m, 'success'), error: m => show(m, 'error'), warning: m => show(m, 'warning'), info: m => show(m, 'info') };
})();