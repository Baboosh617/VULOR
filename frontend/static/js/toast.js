(function () {
    'use strict';

    var TAG_COLORS = {
        success: '#10B981',
        error: '#EF4444',
        warning: '#F59E0B',
        info: '#111111',
        debug: '#111111'
    };

    function getContainer() {
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = [
                'position: fixed',
                'top: 1rem',
                'right: 1rem',
                'z-index: 9999',
                'display: flex',
                'flex-direction: column',
                'gap: 0.5rem',
                'pointer-events: none',
                'max-width: 90vw'
            ].join(';');
            document.body.appendChild(container);
        }
        return container;
    }

    function resolveColor(tags) {
        var tagList = (tags || '').trim().split(/\s+/);
        for (var i = 0; i < tagList.length; i++) {
            if (TAG_COLORS[tagList[i]]) return TAG_COLORS[tagList[i]];
        }
        return TAG_COLORS.info;
    }

    window.showToast = function (message, tags) {
        if (!message) return;

        var color = resolveColor(tags);
        var container = getContainer();

        var toast = document.createElement('div');
        toast.setAttribute('role', 'status');
        toast.style.cssText = [
            'background: ' + color,
            'color: #fff',
            'padding: 0.75rem 1.25rem',
            'border-radius: 6px',
            'box-shadow: 0 10px 25px rgba(0,0,0,0.3)',
            'font-size: 0.875rem',
            'font-weight: 600',
            'max-width: 320px',
            'opacity: 0',
            'transform: translateY(-10px)',
            'transition: opacity 0.25s ease, transform 0.25s ease',
            'pointer-events: auto',
            'cursor: pointer'
        ].join(';');
        toast.textContent = message;

        function dismiss() {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 250);
        }

        toast.addEventListener('click', dismiss);
        container.appendChild(toast);

        requestAnimationFrame(function () {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        setTimeout(dismiss, 4000);
    };

    document.addEventListener('DOMContentLoaded', function () {
        var messages = document.querySelectorAll('[data-django-message]');
        messages.forEach(function (el) {
            window.showToast(
                el.getAttribute('data-django-message'),
                el.getAttribute('data-django-tags')
            );
        });
    });
})();
