# Webpage/ui.py
ERR_TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Data Error</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{ --ink:#1f2937; --muted:#64748b; }
    body{ padding:28px; background:#f7fafc; color:var(--ink); }
    .card-lite{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); }
  </style>
</head>
<body>
  <div class="container">
    <div class="card-lite bg-white p-4">
      <div class="alert alert-danger m-0">
        <div class="fw-bold fs-5">Load Error</div>
        <div class="mt-2">{{ error }}</div>
      </div>
    </div>
  </div>

  
</body>
</html>
"""

INDEX_TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>LT Check — DB</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --ink:#0f172a; --muted:#6b7280; --bg:#f7fafc;
      --ok-bg:#e7f8ed; --ok-fg:#137a2a;
      --warn-bg:#ffecec; --warn-fg:#a61b1b;
      --hdr:#f8fafc;
    }
    html,body{ background:var(--bg); color:var(--ink); }
    body{ padding:28px; }
    .card-lite{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); }
    .muted{ color:var(--muted); }
    .nowrap{ white-space:nowrap; }
    .clicky a{text-decoration:none}
    .clicky a:hover{text-decoration:underline}
            .table td, .table th{ vertical-align:middle; }
    .table tbody tr:nth-child(odd){ background:#fcfcfe; }
    .table tbody tr:hover{ background:#eef6ff; }
    .table-responsive{ max-height:70vh; overflow:auto; }
    .table thead th{ position:sticky; top:0; z-index:2; background:var(--hdr); white-space:nowrap; }
    .num{ text-align:right; font-variant-numeric: tabular-nums; }
    .neg{ color:var(--warn-fg); background:#fff6f6; }
    .zero{ color:var(--muted); }
    .badge-pill{ display:inline-block; padding:.25rem .6rem; border-radius:999px; font-weight:600; }
    .badge-ok{ background:var(--ok-bg); color:var(--ok-fg); }
    .badge-warn{ background:var(--warn-bg); color:var(--warn-fg); }
    .num-center{ text-align:center; font-variant-numeric: tabular-nums; }
    .blue-cell{ color:#0d6efd; font-weight:600; }
    .num-center{ text-align:center; font-variant-numeric: tabular-nums; }
    .page-title{ text-align:center; font-size:2.7rem; font-weight:700; letter-spacing:.05em; margin-bottom:.35rem; text-transform:uppercase; }
    .page-sub{ text-align:center; color:var(--muted); margin-bottom:1.5rem; }
    .form-section label{ font-weight:600; font-size:.95rem; color:var(--muted); margin-bottom:.4rem; display:block; text-transform:uppercase; letter-spacing:.08em; }
    .summary-card{ border-radius:14px; box-shadow:0 6px 14px rgba(15,23,42,.08); }
    .summary-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:1rem; }
    .summary-field{ border:1px solid #e2e8f0; border-radius:12px; padding:.75rem 1rem; background:#f8fafc; }
    .summary-label{ text-transform:uppercase; font-size:.75rem; letter-spacing:.08em; color:var(--muted); font-weight:600; }
    .summary-value{ font-size:1rem; font-weight:600; color:var(--ink); margin-top:.2rem; }
    .detail-link{ color:#0d6efd; font-weight:600; text-decoration:none; }
    .detail-link:hover{ text-decoration:underline; }
    .detail-panel{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); background:#fff; padding:1.5rem; margin-top:1rem; display:none; }
    .detail-panel h6{ text-transform:uppercase; font-size:.85rem; letter-spacing:.08em; font-weight:600; }
    .detail-panel .subcard{ border:1px solid #e2e8f0; border-radius:12px; padding:1rem; background:#f8fafc; height:100%; }
    .detail-panel .subcard.active{ border-color:#0d6efd; box-shadow:0 0 0 3px rgba(13,110,253,.15); }
    .detail-panel{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); background:#fff; padding:1.5rem; display:none; }
    .detail-panel h6{ text-transform:uppercase; font-size:.85rem; letter-spacing:.08em; font-weight:600; }
    .detail-panel .subcard{ border:1px solid #e2e8f0; border-radius:12px; padding:1rem; background:#f8fafc; height:100%; }
    .detail-panel .subcard.active{ border-color:#0d6efd; box-shadow:0 0 0 3px rgba(13,110,253,.15); }
  </style>
</head>
<body>
  <div class="page-title">LT Check</div>
  <div class="page-sub">Loaded {{ loaded_at }}</div>

  <form class="row gy-3 gx-4 align-items-end justify-content-center mb-5" method="get">
    <div class="col-12 col-md-4 form-section">
      <label for="search-so">By SO / QB</label>
      <input id="search-so" class="form-control form-control-lg" style="height:60px;font-size:1.05rem"
             name="so" placeholder="SO-20251368 or 20251368" value="{{ so_num or '' }}">
    </div>
    <div class="col-12 col-md-4 form-section">
      <label for="search-item">By Item</label>
      <input id="search-item" class="form-control form-control-lg" style="height:60px;font-size:1.05rem"
             name="item" placeholder="Item (e.g., M.280-SSD-1TB-SATA-TLC5WT-TD)" value="{{ item_val or '' }}">
    </div>
    <div class="col-6 col-md-auto text-center">
      <button class="btn btn-primary px-4 w-100" style="height:52px;font-size:1rem;font-weight:600">Search</button>
    </div>
    <div class="col-6 col-md-auto text-center">
      <a class="btn btn-outline-secondary w-100" style="height:52px;font-size:1rem;font-weight:600" href="/?reload=1">Reload</a>
    </div>
    <div class="col-12 d-flex justify-content-between align-items-center">
      <div class="text-muted small">Tip: Enter an SO / QB number or an Item to view its details.</div>
      <a class="btn btn-sm btn-outline-secondary" href="/">Back to Home</a>
    </div>
  </form>

  {% if order_summary %}
  <div class="summary-card bg-white mb-4 p-4">
    <div class="d-flex justify-content-between flex-wrap gap-2 mb-3">
      <div class="fw-bold">SO / QB Num: {{ order_summary.qb_num }}</div>
      <div class="text-muted small">Rows: {{ order_summary.row_count }}</div>
    </div>
    <div class="summary-grid">
      {% for field in order_summary.fields %}
        <div class="summary-field">
          <div class="summary-label">{{ field.label }}</div>
          <div class="summary-value">{{ field.value or "—" }}</div>
        </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if so_num and rows %}
  <div class="card-lite bg-white">
    <div class="card-header fw-bold">
      SO / QB Num: {{ so_num }} &nbsp; <span class="text-muted">Rows: {{ count }}</span>
    </div>
    <div class="card-body">
      <div class="table-responsive">
        <table class="table table-sm table-bordered table-hover align-middle">
          <thead class="table-light text-uppercase small text-muted">
            <tr>
              {% for h in headers %}
                <th class="{{ 'text-end' if h in numeric_cols else 'text-center' }}" title="{{ h }}">{{ header_labels.get(h, h) }}</th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for r in rows %}
              {% set status_badge = 'badge-ok' if r.get('Component_Status') == 'Available' else 'badge-warn' %}
              <tr>
              {% for h in headers %}
                {% if h == 'On Sales Order' %}
                  {% set item_val = r.get('Item','') %}
                  <td class="num clicky"><a href="#" class="detail-link" data-item="{{ item_val | e }}" data-focus="so">{{ r.get(h,'') }}</a></td>
                {% elif h == 'On PO' %}
                  {% set item_val = r.get('Item','') %}
                  <td class="num clicky"><a href="#" class="detail-link" data-item="{{ item_val | e }}" data-focus="po">{{ r.get(h,'') }}</a></td>
                {% elif h == 'On Hand - WIP' %}
                  <td class="num blue-cell">{{ r.get('On Hand - WIP', '') }}</td>
                {% elif h == 'Component_Status' %}
                  <td><span class="badge-pill {{ status_badge }}">{{ r.get(h,'') }}</span></td>
                {% elif h == 'Item' %}
                  {% set item_val = r.get('Item','') %}
                  <td class="nowrap clicky">
                    <a href="/item_details?item={{ item_val | urlencode }}">{{ item_val }}</a>
                  </td>
                {% elif h in numeric_cols %}
                  {% set v = r.get(h,'') %}
                  <td class="num-center {% if v is number and v < 0 %}neg{% elif v == 0 %}zero{% endif %}">{{ v }}</td>
                {% else %}
                  <td class="{{ 'nowrap' if h in ['Ship Date'] else '' }}">{{ r.get(h,'') }}</td>
                {% endif %}
              {% endfor %}
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="mt-2 text-muted small">Tip: Click "On Sales Order" or "On PO" to drill down without leaving the page. Headers stay visible when you scroll.</div>
      <div id="item-detail-panel" class="detail-panel"></div>
    </div>
  </div>
  {% elif so_num %}
  <div class="alert alert-warning mt-3">No rows found for "{{ so_num }}".</div>
  {% endif %} 
  <script>
  (function () {
    var panel = document.getElementById('item-detail-panel');
    if (!panel) return;

    var cache = {};

    function escapeHtml(value) {
      if (value === null || value === undefined) return '';
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function buildTable(columns, rows) {
      var safeCols = Array.isArray(columns) ? columns : [];
      var head = safeCols.map(function (c) { return '<th>' + escapeHtml(c) + '</th>'; }).join('');
      var body = '';
      if (Array.isArray(rows) && rows.length) {
        body = rows.map(function (row) {
          return '<tr>' + safeCols.map(function (col) {
            return '<td>' + escapeHtml(row[col]) + '</td>';
          }).join('') + '</tr>';
        }).join('');
      } else {
        body = '<tr><td colspan="' + (safeCols.length || 1) + '" class="text-center text-muted">No data</td></tr>';
      }
      return [
        '<div class="table-responsive mt-2">',
          '<table class="table table-sm table-bordered table-hover align-middle">',
            '<thead class="table-light text-uppercase small text-muted"><tr>' + head + '</tr></thead>',
            '<tbody>' + body + '</tbody>',
          '</table>',
        '</div>'
      ].join('');
    }

    function buildCard(opts) {
      opts = opts || {};
      var title = opts.title || '';
      var columns = opts.columns || [];
      var rows = Array.isArray(opts.rows) ? opts.rows : [];
      var total = opts.totalText;
      var note = opts.note;
      var active = opts.active ? ' active' : '';
      return [
        '<div class="subcard' + active + '">',
          '<div class="d-flex justify-content-between align-items-center">',
            '<h6 class="m-0">' + escapeHtml(title) + '</h6>',
            '<div class="text-muted small">' + rows.length + ' rows</div>',
          '</div>',
          (total ? '<div class="small fw-semibold text-primary mt-1">' + escapeHtml(total) + '</div>' : ''),
          buildTable(columns, rows),
          (note ? '<div class="text-muted small mt-2">' + escapeHtml(note) + '</div>' : ''),
        '</div>'
      ].join('');
    }

    function renderDetail(data, focus) {
      data = data || {};
      var so = data.so || {};
      var po = data.po || {};
      var itemLabel = data.item || '';
      var onPoLabel = (data.on_po_label !== null && data.on_po_label !== undefined) ? data.on_po_label : '—';

      var card;
      if (focus === 'po') {
        card = {
          title: 'On PO',
          data: po,
          total: so.total_on_po !== null && so.total_on_po !== undefined ? 'On PO (SO_INV): ' + so.total_on_po : null,
          note: 'Source: public."NT Shipping Schedule"',
        };
      } else {
        card = {
          title: 'On Sales Order',
          data: so,
          total: so.total_on_sales !== null && so.total_on_sales !== undefined ? 'On Sales Order: ' + so.total_on_sales : null,
          note: 'Source: public.wo_structured',
        };
      }

      var openSection = '';
      if (focus === 'po') {
        var openData = data.open_po || {};
        var openRows = Array.isArray(openData.rows) ? openData.rows : [];
        var openColumns = Array.isArray(openData.columns) ? openData.columns : [];
        openSection = '<hr class="my-3">';
        if (openRows.length) {
          openSection += '<div class="fw-bold small text-muted text-uppercase">Open Purchase Orders</div>' +
            buildTable(openColumns, openRows) +
            '<div class="text-muted small">Source: public.Open_Purchase_Orders</div>';
        } else {
          openSection += '<div class="text-muted small">No open purchase orders</div>';
        }
      }

      panel.innerHTML = [
        '<div class="d-flex justify-content-between flex-wrap gap-2 mb-3">',
          '<div>',
            '<h5 class="mb-1">Item — ' + escapeHtml(itemLabel) + '</h5>',
            '<div class="text-muted small">On PO (from SO data): ' + escapeHtml(onPoLabel) + '</div>',
          '</div>',
          '<div class="text-muted small">Data pulled live from cached tables.</div>',
        '</div>',
        '<div class="subcard active">',
          '<div class="d-flex justify-content-between align-items-center">',
            '<h6 class="m-0">' + escapeHtml(card.title) + '</h6>',
            '<div class="text-muted small">' + ((card.data.rows || []).length) + ' rows</div>',
          '</div>',
          (card.total ? '<div class="small fw-semibold text-primary mt-1">' + escapeHtml(card.total) + '</div>' : ''),
          buildTable(card.data.columns, card.data.rows),
          (card.note ? '<div class="text-muted small mt-2">' + escapeHtml(card.note) + '</div>' : ''),
          openSection,
        '</div>'
      ].join('');
      panel.style.display = 'block';
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    document.addEventListener('click', function (event) {
      if (!event.target.closest) return;
      var link = event.target.closest('.detail-link');
      if (!link) return;
      event.preventDefault();

      var item = link.getAttribute('data-item') || '';
      if (!item) return;
      var focus = link.getAttribute('data-focus') || 'so';

      if (cache[item]) {
        renderDetail(cache[item], focus);
        return;
      }

      panel.style.display = 'block';
      panel.innerHTML = '<div class="text-muted small">Loading ' + escapeHtml(item) + '…</div>';

      fetch('/api/item_overview?item=' + encodeURIComponent(item))
        .then(function (resp) {
          if (!resp.ok) throw new Error('Server error (' + resp.status + ')');
          return resp.json();
        })
        .then(function (json) {
          if (!json.ok) throw new Error(json.error || 'Failed to load item');
          cache[item] = json;
          renderDetail(json, focus);
        })
        .catch(function (err) {
          panel.innerHTML = '<div class="alert alert-danger mb-0">Error loading ' +
            escapeHtml(item) + ': ' + escapeHtml(err.message) + '</div>';
          panel.style.display = 'block';
        });
    });
  })();
  </script>

</body>
</html>
"""

SUBPAGE_TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ title }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{ --hdr:#f8fafc; }
    body{ padding:28px; background:#f7fafc; }
    .table td, .table th{ vertical-align:middle; }
    .card-lite{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); }
    .pill{ display:inline-block; padding:.2rem .65rem; border-radius:999px; background:#eef4ff; border:1px solid #d9e4ff; font-weight:600; margin-left:.5rem; }
    .table-responsive{ max-height:70vh; overflow:auto; }
    .table thead th{ position:sticky; top:0; z-index:2; background:var(--hdr); }
  </style>
</head>
<body>
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h5 class="m-0">{{ title }}</h5>
    <a class="btn btn-sm btn-outline-secondary" href="/">Back</a>
  </div>

  <div class="card-lite bg-white">
    <div class="card-header fw-bold d-flex align-items-center justify-content-between">
      <span>{{ title }}</span>
      {% if on_po is not none %}
        <span class="pill">On PO: {{ on_po }}</span>
      {% endif %}
    </div>
    <div class="card-body">
      <div class="table-responsive">
        <table class="table table-sm table-bordered table-hover align-middle">
          <thead class="table-light text-uppercase small text-muted">
            <tr>
              {% for c in columns %}
                <th>{{ c }}</th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% if rows %}
              {% for r in rows %}
                <tr>
                  {% for c in columns %}
                    <td>{{ r[c] }}</td>
                  {% endfor %}
                </tr>
              {% endfor %}
            {% else %}
              <tr><td colspan="{{ columns|length }}" class="text-center text-muted">No data</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
      <div class="text-muted small">{{ extra_note }}</div>
      {% if open_po_rows %}
      <hr class="my-4">
      <div class="fw-bold small text-muted text-uppercase">Open Purchase Orders</div>
      <div class="table-responsive mt-2">
        <table class="table table-sm table-bordered table-hover align-middle">
          <thead class="table-light text-uppercase small text-muted">
            <tr>
              {% for c in open_po_columns %}
                <th>{{ c }}</th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for r in open_po_rows %}
              <tr>
              {% for c in open_po_columns %}
                <td>{{ r[c] }}</td>
              {% endfor %}
              </tr>
            {% else %}
              <tr><td colspan="{{ open_po_columns|length }}" class="text-center text-muted">No open purchase orders</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="text-muted small">{{ extra_note_open_po }}</div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

ITEM_TPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Item Detail — {{ item }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{ --hdr:#f8fafc; }
    body{ padding:28px; background:#f7fafc; color:#0f172a; }
    .card-lite{ border-radius:14px; box-shadow:0 10px 22px rgba(0,0,0,.06); }
    .table td, .table th{ vertical-align:middle; }
    .table-responsive{ max-height:70vh; overflow:auto; }
    .table thead th{ position:sticky; top:0; z-index:2; background:var(--hdr); }
    .pill{ display:inline-block; padding:.2rem .65rem; border-radius:999px; background:#eef4ff; border:1px solid #d9e4ff; font-weight:600; margin-left:.5rem; }
    .muted{ color:#64748b; }
  </style>
</head>
<body>
  <div class="d-flex justify-content-between align-items-start mb-3 flex-wrap gap-3">
    <div>
      <h5 class="m-0">Item Detail — {{ item }}</h5>
      {% if on_po is not none %}
        <div class="text-muted small mt-1">On PO (from SO data): {{ on_po }}</div>
      {% endif %}
    </div>
    <div class="d-flex gap-2">
      <a class="btn btn-sm btn-outline-secondary" href="/">Back</a>
      <a class="btn btn-sm btn-outline-primary" href="/?item={{ item | urlencode }}">Search Again</a>
    </div>
  </div>

  <div class="row g-4">
    <div class="col-12 col-lg-6">
      <div class="card-lite bg-white h-100">
        <div class="card-header fw-bold d-flex justify-content-between align-items-center">
          <span>On Sales Order</span>
          <div class="text-end">
            <div class="text-muted small">{{ so_rows|length }} rows</div>
            {% if so_total_on_sales is not none %}
              <div class="small fw-semibold text-primary">On Sales Order: {{ so_total_on_sales }}</div>
            {% endif %}
          </div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover align-middle">
              <thead class="table-light text-uppercase small text-muted">
                <tr>
                  {% for c in so_columns %}
                    <th>{{ c }}</th>
                  {% endfor %}
                </tr>
              </thead>
              <tbody>
                {% if so_rows %}
                  {% for row in so_rows %}
                    <tr>
                      {% for c in so_columns %}
                        <td>{{ row[c] }}</td>
                      {% endfor %}
                    </tr>
                  {% endfor %}
                {% else %}
                  <tr><td colspan="{{ so_columns|length }}" class="text-center text-muted">No sales order rows for this item.</td></tr>
                {% endif %}
              </tbody>
            </table>
          </div>
          <div class="text-muted small">{{ extra_note_so }}</div>
        </div>
      </div>
    </div>

    <div class="col-12 col-lg-6">
      <div class="card-lite bg-white h-100">
        <div class="card-header fw-bold d-flex justify-content-between align-items-center">
          <span>On PO</span>
          <div class="text-end">
            <div class="text-muted small">{{ po_rows|length }} rows</div>
            {% if so_total_on_po is not none %}
              <div class="small fw-semibold text-primary">On PO (SO_INV): {{ so_total_on_po }}</div>
            {% endif %}
          </div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-sm table-bordered table-hover align-middle">
              <thead class="table-light text-uppercase small text-muted">
                <tr>
                  {% for c in po_columns %}
                    <th>{{ c }}</th>
                  {% endfor %}
                </tr>
              </thead>
              <tbody>
                {% if po_rows %}
                  {% for row in po_rows %}
                    <tr>
                      {% for c in po_columns %}
                        <td>{{ row[c] }}</td>
                      {% endfor %}
                    </tr>
                  {% endfor %}
                {% else %}
                  <tr><td colspan="{{ po_columns|length }}" class="text-center text-muted">No PO rows for this item.</td></tr>
                {% endif %}
              </tbody>
            </table>
          </div>
          <div class="text-muted small">{{ extra_note_po }}</div>
          {% if open_po_rows %}
          <hr class="my-3">
          <div class="fw-bold small text-muted text-uppercase">Open Purchase Orders</div>
          <div class="table-responsive mt-2">
            <table class="table table-sm table-bordered table-hover align-middle">
              <thead class="table-light text-uppercase small text-muted">
                <tr>
                  {% for c in open_po_columns %}
                    <th>{{ c }}</th>
                  {% endfor %}
                </tr>
              </thead>
              <tbody>
                {% if open_po_rows %}
                  {% for row in open_po_rows %}
                    <tr>
                      {% for c in open_po_columns %}
                        <td>{{ row[c] }}</td>
                      {% endfor %}
                    </tr>
                  {% endfor %}
                {% else %}
                  <tr><td colspan="{{ open_po_columns|length }}" class="text-center text-muted">No open purchase orders</td></tr>
                {% endif %}
              </tbody>
            </table>
          </div>
          <div class="text-muted small">{{ extra_note_open_po }}</div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""
