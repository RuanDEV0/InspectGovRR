/* Troca só o painel do lugar para evitar recarregar a página; sem JavaScript, os links funcionam igual. */
(function () {
    function select(slug) {
        document.querySelectorAll('#daily-map .is-selected').forEach((item) => item.classList.remove('is-selected'));
        document.querySelectorAll('#daily-map [data-daily-place="' + slug + '"] path').forEach((area) => {
            const svg = area.closest('svg');
            area.classList.add('is-selected');
            // Acima dos vizinhos, para o contorno aparecer, mas abaixo dos nomes, para não cobri-los.
            svg.insertBefore(area.closest('a'), svg.querySelector('text'));
        });
        document.querySelectorAll('#daily-map [data-daily-label="' + slug + '"]').forEach((label) => {
            label.classList.add('is-selected');
            label.parentNode.appendChild(label);
        });
        document.querySelectorAll('#daily-places [data-daily-place]').forEach((link) => {
            if (link.dataset.dailyPlace === slug) link.setAttribute('aria-current', 'true');
            else link.removeAttribute('aria-current');
        });
    }

    document.addEventListener('click', async (event) => {
        const link = event.target.closest('[data-daily-place]');
        if (!link || event.metaKey || event.ctrlKey) return;
        event.preventDefault();
        const url = link.getAttribute('href') ?? link.href.baseVal;
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(response.status);
            const page = new DOMParser().parseFromString(await response.text(), 'text/html');
            const panel = document.getElementById('daily-panel');
            panel.innerHTML = page.getElementById('daily-panel').innerHTML;
            select(link.dataset.dailyPlace);
            link.focus({ preventScroll: true });
            history.replaceState(null, '', url);
            if (matchMedia('(max-width: 900px)').matches) panel.scrollIntoView({ block: 'nearest' });
        } catch {
            location.href = url;
        }
    });
})();
