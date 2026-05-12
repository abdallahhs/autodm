/* AutoDM Dashboard — app.js */

const API = '';  // same origin

// ── Utility ──────────────────────────────────────────────────────────────────

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function showToast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast show ${type}`;
  setTimeout(() => { t.className = 'toast'; }, 3500);
}

function badge(text, cls) {
  return `<span class="badge badge-${cls}">${text}</span>`;
}

function fmtDate(str) {
  if (!str) return '—';
  try {
    return new Date(str).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return str; }
}

// ── Tab Navigation ────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'logs') loadLogs();
    if (btn.dataset.tab === 'overview') loadStats();
  });
});

// ── Webhook URL ───────────────────────────────────────────────────────────────

function setWebhookUrl() {
  const url = `${location.origin}/webhook`;
  document.getElementById('webhookUrl').textContent = url;
  document.getElementById('cs-webhook').textContent = url;
}
setWebhookUrl();

// ── Stats ─────────────────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const s = await apiFetch('/api/stats');
    document.getElementById('stat-campaigns').textContent = s.total_campaigns;
    document.getElementById('stat-active').textContent = s.active_campaigns;
    document.getElementById('stat-replies').textContent = s.total_replies;
    document.getElementById('stat-dms').textContent = s.total_dms;
  } catch (e) { console.error('Stats error', e); }

  // Recent logs
  try {
    const logs = await apiFetch('/api/logs?limit=8');
    const tbody = document.getElementById('recentLogsTbody');
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No activity yet</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td>${formatAction(l.action)}</td>
        <td>${l.status === 'success' ? badge('Success', 'success') : badge('Failed', 'error')}</td>
        <td style="font-family:var(--mono);font-size:12px;">${l.comment_id || '—'}</td>
        <td>${fmtDate(l.created_at)}</td>
      </tr>
    `).join('');
  } catch (e) { console.error('Logs error', e); }
}

function formatAction(a) {
  if (a === 'comment_reply') return '💬 Comment Reply';
  if (a === 'dm_sent') return '📩 DM Sent';
  return a;
}

// ── Settings ──────────────────────────────────────────────────────────────────

async function loadConfig() {
  try {
    const c = await apiFetch('/api/config');
    const set = v => v ? badge('Set ✓', 'set') : badge('Not set', 'unset');
    document.getElementById('cs-token').outerHTML = `<span class="badge badge-${c.access_token_set ? 'set' : 'unset'}" id="cs-token">${c.access_token_set ? 'Set ✓' : 'Not set'}</span>`;
    document.getElementById('cs-account').outerHTML = `<span class="badge badge-${c.ig_account_id ? 'set' : 'unset'}" id="cs-account">${c.ig_account_id || 'Not set'}</span>`;
    document.getElementById('cs-secret').outerHTML = `<span class="badge badge-${c.facebook_app_secret_set ? 'set' : 'unset'}" id="cs-secret">${c.facebook_app_secret_set ? 'Set ✓' : 'Not set'}</span>`;
    if (c.ig_account_id) document.getElementById('igAccountId').value = c.ig_account_id;
  } catch (e) { console.error('Config load error', e); }
}

document.getElementById('settingsForm').addEventListener('submit', async () => {
  const btn = document.getElementById('btnSaveSettings');
  const status = document.getElementById('settingsStatus');
  btn.disabled = true;
  btn.textContent = 'Saving…';
  status.textContent = '';

  try {
    await apiFetch('/api/config', {
      method: 'POST',
      body: JSON.stringify({
        access_token: document.getElementById('accessToken').value,
        ig_account_id: document.getElementById('igAccountId').value,
        facebook_app_secret: document.getElementById('appSecret').value,
      }),
    });
    showToast('Credentials saved!', 'success');
    status.textContent = '✓ Saved';
    status.className = 'inline-status ok';
    loadConfig();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
    status.textContent = '✕ Error';
    status.className = 'inline-status err';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Credentials';
  }
});

// ── Campaigns ─────────────────────────────────────────────────────────────────

let campaigns = [];

async function loadCampaigns() {
  try {
    campaigns = await apiFetch('/api/campaigns');
    renderCampaigns();
  } catch (e) {
    showToast('Failed to load campaigns', 'error');
  }
}

function renderCampaigns() {
  const el = document.getElementById('campaignsList');
  if (!campaigns.length) {
    el.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚡</div>
        <p>No campaigns yet. Create your first one!</p>
      </div>`;
    return;
  }
  el.innerHTML = campaigns.map(c => {
    const thumb = c.post_thumbnail
      ? `<img class="campaign-thumb" src="${c.post_thumbnail}" alt="Post" onerror="this.style.display='none'" />`
      : `<div class="campaign-thumb-placeholder">📸</div>`;
    const kws = c.keywords.split(',').map(k => k.trim()).join(' · ');
    return `
      <div class="campaign-card ${c.is_active ? '' : 'inactive'}" id="camp-${c.id}">
        ${thumb}
        <div class="campaign-body">
          <div class="campaign-name">${escHtml(c.name)}</div>
          <div class="campaign-meta">
            ${c.is_active ? badge('Active', 'active') : badge('Inactive', 'inactive')}
            <span style="color:var(--text-muted);font-size:12px;">Post: <code style="font-family:var(--mono);font-size:11px;">${escHtml(c.post_id)}</code></span>
          </div>
          <div class="campaign-keywords">🔑 ${escHtml(kws)}</div>
        </div>
        <div class="campaign-actions">
          <button class="btn-icon" title="${c.is_active ? 'Deactivate' : 'Activate'}" onclick="toggleCampaign(${c.id})">
            ${c.is_active
              ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>'
              : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>'
            }
          </button>
          <button class="btn-icon" title="Edit" onclick="openEditModal(${c.id})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="btn-icon danger" title="Delete" onclick="openDeleteModal(${c.id})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>
        </div>
      </div>`;
  }).join('');
}

async function toggleCampaign(id) {
  try {
    await apiFetch(`/api/campaigns/${id}/toggle`, { method: 'PATCH' });
    await loadCampaigns();
    showToast('Campaign updated', 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ── Campaign Modal ────────────────────────────────────────────────────────────

let editingId = null;

function openNewModal() {
  editingId = null;
  document.getElementById('modalTitle').textContent = 'New Campaign';
  document.getElementById('campaignForm').reset();
  document.getElementById('campaignId').value = '';
  document.getElementById('postPreview').style.display = 'none';
  document.getElementById('campaignModal').classList.add('open');
}

function openEditModal(id) {
  const c = campaigns.find(x => x.id === id);
  if (!c) return;
  editingId = id;
  document.getElementById('modalTitle').textContent = 'Edit Campaign';
  document.getElementById('campaignId').value = c.id;
  document.getElementById('campName').value = c.name;
  document.getElementById('campPostId').value = c.post_id;
  document.getElementById('campKeywords').value = c.keywords;
  document.getElementById('campCommentReply').value = c.comment_reply;
  document.getElementById('campDmMessage').value = c.dm_message;
  document.getElementById('campActive').checked = c.is_active;

  const prev = document.getElementById('postPreview');
  if (c.post_thumbnail) {
    document.getElementById('postThumb').src = c.post_thumbnail;
    document.getElementById('postCaption').textContent = c.post_caption || '';
    prev.style.display = 'flex';
  } else {
    prev.style.display = 'none';
  }
  document.getElementById('campaignModal').classList.add('open');
}

function closeModal() {
  document.getElementById('campaignModal').classList.remove('open');
}

document.getElementById('btnNewCampaign').addEventListener('click', openNewModal);
document.getElementById('btnCloseModal').addEventListener('click', closeModal);
document.getElementById('btnCancelModal').addEventListener('click', closeModal);

// Post preview fetch
document.getElementById('btnFetchPost').addEventListener('click', async () => {
  const postId = document.getElementById('campPostId').value.trim();
  if (!postId) { showToast('Enter a Post ID first', 'error'); return; }
  const btn = document.getElementById('btnFetchPost');
  btn.textContent = '…';
  btn.disabled = true;
  try {
    const d = await apiFetch(`/api/post-preview?post_id=${encodeURIComponent(postId)}`);
    if (d.thumbnail_url) {
      document.getElementById('postThumb').src = d.thumbnail_url;
      document.getElementById('postCaption').textContent = d.caption || 'No caption';
      document.getElementById('postPreview').style.display = 'flex';
    }
    showToast('Post loaded!', 'success');
  } catch (e) {
    showToast('Could not fetch post: ' + e.message, 'error');
  } finally {
    btn.textContent = 'Preview';
    btn.disabled = false;
  }
});

// Save campaign
document.getElementById('campaignForm').addEventListener('submit', async () => {
  const btn = document.getElementById('btnSaveCampaign');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  const thumb = document.getElementById('postThumb').src;
  const payload = {
    name: document.getElementById('campName').value.trim(),
    post_id: document.getElementById('campPostId').value.trim(),
    post_thumbnail: thumb && !thumb.includes('undefined') ? thumb : null,
    post_caption: document.getElementById('postCaption').textContent || null,
    keywords: document.getElementById('campKeywords').value.trim(),
    comment_reply: document.getElementById('campCommentReply').value.trim(),
    dm_message: document.getElementById('campDmMessage').value.trim(),
    is_active: document.getElementById('campActive').checked,
  };

  try {
    if (editingId) {
      await apiFetch(`/api/campaigns/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Campaign updated!', 'success');
    } else {
      await apiFetch('/api/campaigns', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Campaign created!', 'success');
    }
    closeModal();
    loadCampaigns();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Campaign';
  }
});

// ── Delete Modal ──────────────────────────────────────────────────────────────

let deletingId = null;

function openDeleteModal(id) {
  deletingId = id;
  document.getElementById('deleteModal').classList.add('open');
}

document.getElementById('btnCloseDelete').addEventListener('click', () => {
  document.getElementById('deleteModal').classList.remove('open');
});
document.getElementById('btnCancelDelete').addEventListener('click', () => {
  document.getElementById('deleteModal').classList.remove('open');
});
document.getElementById('btnConfirmDelete').addEventListener('click', async () => {
  if (!deletingId) return;
  try {
    await apiFetch(`/api/campaigns/${deletingId}`, { method: 'DELETE' });
    showToast('Campaign deleted', 'success');
    document.getElementById('deleteModal').classList.remove('open');
    loadCampaigns();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
});

// Close modals on overlay click
['campaignModal', 'deleteModal'].forEach(id => {
  document.getElementById(id).addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.remove('open');
  });
});

// ── Logs ─────────────────────────────────────────────────────────────────────

async function loadLogs() {
  try {
    const logs = await apiFetch('/api/logs?limit=100');
    const tbody = document.getElementById('logsTbody');
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No activity yet</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td>${formatAction(l.action)}</td>
        <td>${l.status === 'success' ? badge('Success', 'success') : badge('Failed', 'error')}</td>
        <td style="font-family:var(--mono);font-size:11.5px;">${l.comment_id || '—'}</td>
        <td>${l.campaign_id ? `#${l.campaign_id}` : '—'}</td>
        <td>${fmtDate(l.created_at)}</td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('logsTbody').innerHTML =
      `<tr><td colspan="5" class="empty-row" style="color:var(--red);">Error loading logs</td></tr>`;
  }
}

document.getElementById('btnRefreshLogs').addEventListener('click', loadLogs);

// ── Utils ─────────────────────────────────────────────────────────────────────

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Boot ──────────────────────────────────────────────────────────────────────

(async () => {
  await Promise.allSettled([loadStats(), loadConfig(), loadCampaigns()]);
})();
