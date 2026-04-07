// Nashat Admin — editor interactions

// ----- save form -----
const form = document.getElementById('agent-form');
const saveBtn = document.getElementById('save-button');
const saveStatus = document.getElementById('save-status');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  saveBtn.disabled = true;
  saveStatus.textContent = 'saving…';
  saveStatus.className = 'save-status';

  try {
    const fd = new FormData(form);
    const r = await fetch(form.action, { method: 'POST', body: fd });
    const data = await r.json();
    if (data.ok) {
      saveStatus.textContent = '✓ saved';
      saveStatus.className = 'save-status success';
      setTimeout(() => { saveStatus.textContent = ''; }, 4000);
    } else {
      saveStatus.textContent = '✗ ' + (data.error || 'save failed').substring(0, 80);
      saveStatus.className = 'save-status error';
    }
  } catch (err) {
    saveStatus.textContent = '✗ ' + err.message;
    saveStatus.className = 'save-status error';
  }
  saveBtn.disabled = false;
});


// ----- list row add/remove -----
function removeListRow(btn) {
  const row = btn.closest('.list-row');
  const container = row.parentElement;
  row.remove();
  reindexList(container);
}

function addListRow(btn, fieldType = 'text') {
  const fieldset = btn.closest('.list-field');
  const container = fieldset.querySelector('.list-items');
  const prefix = container.dataset.listPrefix;
  const newIdx = container.querySelectorAll('.list-row').length;
  const row = document.createElement('div');
  row.className = 'list-row';
  if (fieldType === 'textarea') {
    row.innerHTML = `<textarea name="${prefix}[${newIdx}]" rows="2"></textarea>` +
      `<button type="button" class="btn-remove" onclick="removeListRow(this)">×</button>`;
  } else {
    row.innerHTML = `<input type="text" name="${prefix}[${newIdx}]">` +
      `<button type="button" class="btn-remove" onclick="removeListRow(this)">×</button>`;
  }
  container.appendChild(row);
  row.querySelector('input, textarea').focus();
}

function reindexList(container) {
  const prefix = container.dataset.listPrefix;
  container.querySelectorAll('.list-row').forEach((row, i) => {
    const inp = row.querySelector('input, textarea');
    if (inp) inp.name = `${prefix}[${i}]`;
  });
}


// ----- test panel -----
const testSendBtn = document.getElementById('test-send');
const testQuestion = document.getElementById('test-question');
const testMode = document.getElementById('test-mode');
const testConvo = document.getElementById('test-conversation');

function appendTestMsg(type, html, meta = null) {
  const div = document.createElement('div');
  div.className = `test-msg test-msg-${type}`;
  div.innerHTML = html;
  if (meta) {
    const m = document.createElement('div');
    m.className = 'test-msg-meta';
    m.textContent = meta;
    div.appendChild(m);
  }
  testConvo.appendChild(div);
  testConvo.scrollTop = testConvo.scrollHeight;
  return div;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}


testSendBtn.addEventListener('click', sendTest);
testQuestion.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    sendTest();
  }
});

async function sendTest() {
  const q = testQuestion.value.trim();
  if (!q) return;
  testSendBtn.disabled = true;
  appendTestMsg('user', escapeHtml(q));
  testQuestion.value = '';
  const loading = appendTestMsg('loading', 'Nashat is thinking…');

  try {
    const body = { question: q };
    const mode = testMode.value.trim();
    if (mode) body.mode = mode;
    const r = await fetch('/api/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    loading.remove();
    if (data.error) {
      appendTestMsg('error', escapeHtml(data.error));
    } else {
      const text = (data.response || '').replace(/\n/g, '<br>');
      const meta = `${data.mode_label || data.mode || ''} · ${data.chunk_count || 0} chunks`;
      appendTestMsg('nashat', text, meta);
    }
  } catch (err) {
    loading.remove();
    appendTestMsg('error', escapeHtml(err.message));
  }
  testSendBtn.disabled = false;
  testQuestion.focus();
}
