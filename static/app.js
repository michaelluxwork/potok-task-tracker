(() => {
  const live = document.querySelector('#live-status');
  let dragged = null;
  let busy = false;
  const announce = text => { if (live) live.textContent = text; };
  document.querySelectorAll('.task-card[draggable="true"]').forEach(card => {
    card.addEventListener('dragstart', event => {
      if (busy) { event.preventDefault(); return; }
      dragged = card;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.dataset.taskId);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      document.querySelectorAll('.drag-target').forEach(target => target.classList.remove('drag-target'));
      dragged = null;
    });
  });
  document.querySelectorAll('.kanban-column').forEach(column => {
    column.addEventListener('dragover', event => {
      if (dragged && !busy) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; column.classList.add('drag-target'); }
    });
    column.addEventListener('dragleave', event => {
      if (!column.contains(event.relatedTarget)) column.classList.remove('drag-target');
    });
    column.addEventListener('drop', async event => {
      event.preventDefault();
      column.classList.remove('drag-target');
      if (!dragged || busy || dragged.closest('.kanban-column') === column) return;
      const card = dragged;
      busy = true;
      const errorBox = document.querySelector('#move-error');
      errorBox.hidden = true;
      announce('Сохраняем новый статус…');
      const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1];
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      try {
        const response = await fetch(card.dataset.moveUrl, { method: 'POST', credentials: 'same-origin', redirect: 'error', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': decodeURIComponent(token || ''), 'Accept': 'application/json' }, body: new URLSearchParams({ status: column.dataset.status, version: card.dataset.version }), signal: controller.signal });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || 'Не удалось изменить статус. Обновите доску и проверьте свои права.');
        announce('Статус задачи сохранён. Обновляем доску.');
        window.location.reload();
      } catch (error) {
        errorBox.textContent = error.name === 'AbortError' ? 'Ответ сервера не получен вовремя. Обновите доску и проверьте статус перед повторной попыткой.' : (error.message === 'Failed to fetch' ? 'Нет связи с сервером. Обновите доску перед повторной попыткой.' : error.message);
        errorBox.hidden = false;
        announce(errorBox.textContent);
        errorBox.scrollIntoView({ block: 'nearest' });
      } finally { clearTimeout(timeout); busy = false; }
    });
  });
  document.querySelectorAll('form[method="post"]').forEach(form => {
    form.addEventListener('submit', event => {
      if (form.dataset.submitting === 'yes') { event.preventDefault(); return; }
      if (form.classList.contains('remove-member-form') && !window.confirm('Убрать участника с доски? Его задачи сохранятся без исполнителя.')) { event.preventDefault(); return; }
      form.dataset.submitting = 'yes';
      form.querySelectorAll('button[type="submit"],button:not([type])').forEach(button => { button.disabled = true; });
    });
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[data-submitting]').forEach(form => { delete form.dataset.submitting; form.querySelectorAll('button:disabled').forEach(button => { button.disabled = false; }); });
  });
  document.querySelector('[data-back]')?.addEventListener('click', () => { if (window.history.length > 1) window.history.back(); else window.location.assign('/boards/'); });
})();
