(function () {
    'use strict';

    // On-system transient notices. Design system §18: alerts are full-width
    // STRIPS in the `.v-alert` anatomy (top/bottom hairline + 2px left rule in
    // the semantic colour, mono prefix + message) — never floating rounded
    // boxes with drop shadows. Transient toasts reuse that anatomy, slide in
    // from the top edge, auto-dismiss at 4s, and stack at most 2. Colours,
    // radius, and motion come entirely from the design tokens (vulor.css /
    // @theme); the only thing set inline here is positioning + the opaque
    // ground fill a floating strip needs to stay readable over page content.

    var MAX_VISIBLE = 2;
    var DISMISS_MS = 4000;

    // tag -> { modifier class, mono prefix }. Confirmations speak in the signal
    // (lime) rule, failures in error, everything else neutral ink.
    var TAG_STYLE = {
        success: { mod: 'v-alert--signal', prefix: 'DONE' },
        error:   { mod: 'v-alert--error',  prefix: 'ERROR' },
        warning: { mod: '',                prefix: 'NOTE' },
        info:    { mod: '',                prefix: 'NOTE' },
        debug:   { mod: '',                prefix: 'NOTE' }
    };

    // Django attaches non-level marker tags (e.g. "contact") to messages that a
    // page renders inline itself; suppress those here so they don't double up as
    // both an on-page strip and a toast. Extend as pages opt into inline alerts.
    var SUPPRESS_TAGS = ['contact'];

    var prefersReducedMotion = window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function getContainer() {
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            // Fixed to the top edge, centred, capped so the strip stays a
            // readable line rather than a full-bleed banner on wide screens.
            container.style.cssText = [
                'position: fixed',
                'top: 0',
                'left: 50%',
                'transform: translateX(-50%)',
                'z-index: 9999',
                'width: 100%',
                'max-width: 40rem',
                'padding: 0 1rem',
                'display: flex',
                'flex-direction: column',
                'gap: 0.5rem',
                'pointer-events: none'
            ].join(';');
            document.body.appendChild(container);
        }
        return container;
    }

    function resolveStyle(tags) {
        var tagList = (tags || '').trim().split(/\s+/);
        for (var i = 0; i < tagList.length; i++) {
            if (TAG_STYLE[tagList[i]]) return TAG_STYLE[tagList[i]];
        }
        return TAG_STYLE.info;
    }

    function isSuppressed(tags) {
        var tagList = (tags || '').trim().split(/\s+/);
        for (var i = 0; i < tagList.length; i++) {
            if (SUPPRESS_TAGS.indexOf(tagList[i]) !== -1) return true;
        }
        return false;
    }

    window.showToast = function (message, tags) {
        if (!message || isSuppressed(tags)) return;

        var style = resolveStyle(tags);
        var container = getContainer();

        // Keep at most MAX_VISIBLE — drop the oldest before adding a new one.
        while (container.children.length >= MAX_VISIBLE) {
            container.removeChild(container.firstChild);
        }

        var toast = document.createElement('div');
        toast.className = 'v-alert ' + style.mod;
        toast.setAttribute('role', 'status');
        // Opaque ground fill: a floating strip must not let page content bleed
        // through. --ground-900 reads as one elevation step, no shadow needed.
        toast.style.background = 'var(--ground-900)';
        toast.style.pointerEvents = 'auto';
        toast.style.cursor = 'pointer';
        toast.style.opacity = '0';
        toast.style.transform = prefersReducedMotion ? 'none' : 'translateY(-120%)';
        toast.style.transition =
            'opacity var(--motion-base, 240ms) var(--ease-mech, ease),' +
            ' transform var(--motion-base, 240ms) var(--ease-mech, ease)';

        var prefix = document.createElement('span');
        prefix.className = 'v-label';
        prefix.textContent = style.prefix;

        var body = document.createElement('span');
        body.textContent = message;

        toast.appendChild(prefix);
        toast.appendChild(body);

        var dismissed = false;
        function dismiss() {
            if (dismissed) return;
            dismissed = true;
            toast.style.opacity = '0';
            if (!prefersReducedMotion) toast.style.transform = 'translateY(-120%)';
            window.setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 240);
        }

        toast.addEventListener('click', dismiss);
        container.appendChild(toast);

        requestAnimationFrame(function () {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        });

        window.setTimeout(dismiss, DISMISS_MS);
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
