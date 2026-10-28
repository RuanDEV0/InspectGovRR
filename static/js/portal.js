// Comportamentos compartilhados. As páginas funcionam sem JavaScript; aqui só há melhorias.
(() => {
    const storage = {
        get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
        set(key, value) { try { sessionStorage.setItem(key, value); } catch { /* armazenamento indisponível */ } },
    };

    // Aviso sobre a origem dos dados: uma vez por visita e sob demanda.
    const dialog = document.querySelector('[data-source-dialog]');
    if (dialog && typeof dialog.showModal === 'function') {
        const SEEN_KEY = 'source-notice-seen';
        document.querySelectorAll('[data-source-open]').forEach((button) => {
            button.hidden = false;
            button.addEventListener('click', () => dialog.showModal());
        });
        dialog.addEventListener('close', () => storage.set(SEEN_KEY, '1'));
        dialog.addEventListener('click', (event) => {
            if (event.target === dialog) dialog.close();
        });
        if (!storage.get(SEEN_KEY)) dialog.showModal();
    }

    // Menu do header em telas pequenas.
    const header = document.querySelector('[data-site-header]');
    const toggle = document.querySelector('[data-nav-toggle]');
    if (header && toggle) {
        toggle.hidden = false;
        const setOpen = (open) => {
            toggle.setAttribute('aria-expanded', String(open));
            header.toggleAttribute('data-nav-open', open);
        };
        toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && header.hasAttribute('data-nav-open')) {
                setOpen(false);
                toggle.focus();
            }
        });
        const onScroll = () => header.toggleAttribute('data-scrolled', window.scrollY > 8);
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    // Busca em listas: [data-filter-input] filtra [data-filter-item] pelo texto de data-filter-text.
    document.querySelectorAll('[data-filter-input]').forEach((input) => {
        const scope = document.querySelector(input.dataset.filterInput);
        const counter = document.querySelector(input.dataset.filterCount);
        if (!scope) return;
        const normalize = (text) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
        const items = [...scope.querySelectorAll('[data-filter-item]')];
        const groups = [...scope.querySelectorAll('[data-filter-group]')];
        input.closest('[hidden]')?.removeAttribute('hidden');
        input.addEventListener('input', () => {
            const query = normalize(input.value.trim());
            let visible = 0;
            items.forEach((item) => {
                const match = !query || normalize(item.dataset.filterText).includes(query);
                item.hidden = !match;
                if (match) visible += 1;
            });
            groups.forEach((group) => {
                group.hidden = !group.querySelector('[data-filter-item]:not([hidden])');
            });
            if (counter) counter.textContent = query ? `${visible} de ${items.length} encontrados` : '';
        });
    });
})();
