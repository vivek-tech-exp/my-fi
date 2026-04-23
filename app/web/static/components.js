const statusMeta = {
  PASS: {
    label: "Ready",
    tone: "pass",
    help: "Parsed and validated without blocking issues.",
  },
  PASS_WITH_WARNINGS: {
    label: "Review warnings",
    tone: "warning",
    help: "Imported, but warnings should be checked.",
  },
  FAIL_NEEDS_REVIEW: {
    label: "Needs review",
    tone: "fail",
    help: "Not trusted yet. Review validation issues and diagnostics.",
  },
  RECEIVED: {
    label: "Received",
    tone: "neutral",
    help: "Stored but not fully processed.",
  },
  PROCESSING: {
    label: "Processing",
    tone: "neutral",
    help: "Import is still running.",
  },
};

const rowTypeLabels = {
  accepted: "Imported",
  ignored: "Skipped",
  suspicious: "Needs review",
};

const repairStatusLabels = {
  not_required: "No repair needed",
  repaired: "Repaired",
  not_repairable: "Could not repair",
  not_attempted: "Not attempted",
};

const reasonLabels = {
  blank_row: "Blank row",
  header_row: "Header row",
  repeated_header_row: "Repeated header",
  account_metadata: "Account metadata",
  statement_metadata: "Statement metadata",
  statement_footer: "Statement footer",
  content_before_header: "Before header",
  column_count_mismatch: "Column mismatch",
  invalid_transaction_date: "Invalid date",
  missing_description: "Missing description",
  invalid_amount_shape: "Invalid amount",
};

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatDate(value) {
  return value || "-";
}

export function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatMoney(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function statusPill(status) {
  const meta = statusMeta[status] || { label: status || "-", tone: "neutral", help: status || "" };
  return `<span class="status-pill ${meta.tone}" title="${escapeHtml(meta.help)}">${escapeHtml(meta.label)}</span>`;
}

export function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

export function renderUploadView({ selectedBank, uploadResult }) {
  return `
    <section class="panel">
      <form id="upload-form" class="upload-form">
        <label>
          <span>Bank</span>
          <select id="upload-bank" name="bank">
            ${["kotak", "hdfc", "federal"]
              .map(
                (bank) =>
                  `<option value="${bank}" ${bank === selectedBank ? "selected" : ""}>${bank}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label class="file-picker">
          <span>CSV files</span>
          <input id="upload-files" type="file" name="files" accept=".csv,text/csv" multiple />
        </label>
        <button class="primary-action" type="submit">Upload</button>
      </form>
    </section>
    <section class="panel">
      <div class="section-heading">
        <h2>Upload results</h2>
      </div>
      ${renderUploadResults(uploadResult)}
    </section>
  `;
}

export function renderUploadResults(uploadResult) {
  if (!uploadResult) {
    return emptyState("Upload CSV files to see per-file results.");
  }

  return `
    <div class="metric-strip">
      <span>Total ${uploadResult.total_files}</span>
      <span>Succeeded ${uploadResult.succeeded}</span>
      <span>Failed ${uploadResult.failed}</span>
      <span>Duplicates ${uploadResult.duplicates}</span>
    </div>
    <div class="result-list">
      ${uploadResult.results.map(renderUploadResultItem).join("")}
    </div>
  `;
}

function renderUploadResultItem(item) {
  if (item.error) {
    return `
      <article class="result-card fail-card">
        <div>
          <strong>${escapeHtml(item.original_filename)}</strong>
          <p>${escapeHtml(item.error)}</p>
        </div>
        <span class="status-pill fail">${item.status_code}</span>
      </article>
    `;
  }

  const result = item.result;
  return `
    <article class="result-card">
      <div>
        <strong>${escapeHtml(item.original_filename)}</strong>
        <p>${escapeHtml(result.message)}</p>
        <div class="compact-meta">
          <span>${escapeHtml(result.account_id || "account pending")}</span>
          <span>${result.transactions_imported} tx</span>
          <span>${result.duplicate_transactions_detected} duplicates</span>
        </div>
      </div>
      ${statusPill(result.status)}
    </article>
  `;
}

export function renderImportsView({
  imports,
  importFilters,
  selectedImportId,
  selectedImport,
  selectedReport,
  selectedRows,
  rowFilter,
}) {
  const filteredImports = filterImports(imports, importFilters);
  return `
    ${renderImportOverview(imports)}
    <section class="split-view">
      <div class="panel">
        <div class="section-heading">
          <h2>Imports</h2>
          <button id="refresh-imports" class="secondary-action" type="button">Refresh</button>
        </div>
        ${renderImportFilters(importFilters)}
        ${renderImportList(filteredImports, selectedImportId)}
      </div>
      <div class="panel detail-panel">
        ${renderImportDetail({ selectedImport, selectedReport, selectedRows, rowFilter })}
      </div>
    </section>
  `;
}

function renderImportOverview(imports) {
  const metrics = {
    total: imports.length,
    ready: imports.filter((item) => item.status === "PASS").length,
    warnings: imports.filter((item) => item.status === "PASS_WITH_WARNINGS").length,
    review: imports.filter((item) => item.status === "FAIL_NEEDS_REVIEW").length,
    transactions: sum(imports, "transactions_imported"),
    suspicious: sum(imports, "suspicious_rows"),
    duplicates: sum(imports, "duplicate_rows"),
    action: imports.filter((item) => item.needs_action).length,
  };

  return `
    <section class="overview-grid">
      ${metricCard("Needs action", metrics.action, "Review failed and warning imports first.")}
      ${metricCard("Ready", metrics.ready, "Imports trusted for ledger review.")}
      ${metricCard("Warnings", metrics.warnings, "Imported, but requires checking.")}
      ${metricCard("Failed", metrics.review, "Not trusted yet.")}
      ${metricCard("Transactions", metrics.transactions, "Canonical ledger rows imported.")}
      ${metricCard("Suspicious rows", metrics.suspicious, "Parser diagnostics needing review.")}
      ${metricCard("Duplicates", metrics.duplicates, "Transactions skipped by duplicate protection.")}
      ${metricCard("Total imports", metrics.total, "Files registered locally.")}
    </section>
  `;
}

function metricCard(label, value, help) {
  return `
    <article class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(help)}</small>
    </article>
  `;
}

function renderImportFilters(filters) {
  return `
    <form id="imports-filter" class="filter-grid import-filter-grid">
      <label><span>Bank</span><select name="bankName">
        <option value="">all</option>
        ${["kotak", "hdfc", "federal"]
          .map(
            (bank) => `<option value="${bank}" ${filters.bankName === bank ? "selected" : ""}>${bank}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Status</span><select name="status">
        <option value="">all</option>
        ${["PASS", "PASS_WITH_WARNINGS", "FAIL_NEEDS_REVIEW", "RECEIVED", "PROCESSING"]
          .map(
            (status) =>
              `<option value="${status}" ${filters.status === status ? "selected" : ""}>${statusMeta[status]?.label || status}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Account</span><input name="accountId" value="${escapeHtml(filters.accountId)}" /></label>
      <label><span>Filename</span><input name="filename" value="${escapeHtml(filters.filename)}" /></label>
      <label><span>From</span><input type="date" name="dateFrom" value="${escapeHtml(filters.dateFrom)}" /></label>
      <label><span>To</span><input type="date" name="dateTo" value="${escapeHtml(filters.dateTo)}" /></label>
      <label><span>Quick filter</span><select name="quick">
        ${[
          ["", "all"],
          ["needs_action", "needs action"],
          ["warnings", "warnings"],
          ["ready", "ready"],
          ["suspicious", "has suspicious rows"],
          ["duplicates", "has duplicates"],
        ]
          .map(
            ([value, label]) =>
              `<option value="${value}" ${filters.quick === value ? "selected" : ""}>${label}</option>`,
          )
          .join("")}
      </select></label>
      <button class="primary-action" type="submit">Apply</button>
      <button id="clear-import-filters" class="secondary-action" type="button">Clear</button>
    </form>
  `;
}

function renderImportList(imports, selectedImportId) {
  if (!imports.length) {
    return emptyState("No imports match the current filters.");
  }

  return `
    <div class="import-list">
      ${imports
        .map(
          (item) => `
            <button class="import-row ${item.file_id === selectedImportId ? "active" : ""}" type="button" data-import-id="${item.file_id}">
              <span>
                <strong>${escapeHtml(item.original_filename)}</strong>
                <small>${escapeHtml(item.bank_name)} · ${escapeHtml(item.account_id || "account pending")}</small>
                <small>${formatDate(item.statement_start_date)} to ${formatDate(item.statement_end_date)}</small>
              </span>
              <span>
                ${statusPill(item.status)}
                <small>${item.transactions_imported} tx · ${item.suspicious_rows} issue rows · ${item.duplicate_rows} duplicates</small>
              </span>
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderImportDetail({ selectedImport, selectedReport, selectedRows, rowFilter }) {
  if (!selectedImport) {
    return emptyState("Select an import to inspect validation, actions, and diagnostics.");
  }

  const report = selectedReport || selectedImport.report;
  const issues = report?.issues || [];
  return `
    <div class="section-heading">
      <div>
        <h2>${escapeHtml(selectedImport.original_filename)}</h2>
        <p>${escapeHtml(selectedImport.bank_name)} · ${escapeHtml(selectedImport.account_id || "account pending")}</p>
      </div>
      <button id="reprocess-import" class="secondary-action" type="button">Reprocess</button>
    </div>
    <div class="callout ${selectedImport.needs_action ? "warning-callout" : "pass-callout"}">
      <strong>${escapeHtml(selectedImport.recommended_action)}</strong>
      <span>${statusPill(selectedImport.status)}</span>
    </div>
    <div class="metric-strip">
      <span>${selectedImport.transactions_imported} transactions</span>
      <span>${selectedImport.accepted_rows} imported rows</span>
      <span>${selectedImport.ignored_rows} skipped rows</span>
      <span>${selectedImport.suspicious_rows} issue rows</span>
      <span>${selectedImport.duplicate_rows} duplicates</span>
    </div>
    ${renderIssues(issues)}
    <details class="technical-details">
      <summary>Technical details</summary>
      <dl>
        <dt>File ID</dt><dd class="mono">${escapeHtml(selectedImport.file_id)}</dd>
        <dt>Hash</dt><dd class="mono">${escapeHtml(selectedImport.file_hash)}</dd>
        <dt>Stored path</dt><dd>${escapeHtml(selectedImport.stored_path || "-")}</dd>
        <dt>Parser</dt><dd>${escapeHtml(selectedImport.parser_version || "-")}</dd>
        <dt>Encoding</dt><dd>${escapeHtml(selectedImport.encoding_detected || "-")}</dd>
        <dt>Delimiter</dt><dd>${escapeHtml(selectedImport.delimiter_detected || "-")}</dd>
      </dl>
    </details>
    <div class="row-toolbar">
      <h3>Diagnostics</h3>
      <label>
        <span>Rows</span>
        <select id="row-filter">
          ${[
            ["issues", "issues and repairs"],
            ["suspicious", "needs review"],
            ["accepted", "imported"],
            ["ignored", "skipped"],
            ["repaired", "repaired"],
            ["all", "all rows"],
          ]
            .map(
              ([value, label]) =>
                `<option value="${value}" ${value === rowFilter ? "selected" : ""}>${label}</option>`,
            )
            .join("")}
        </select>
      </label>
    </div>
    ${renderRowsTable(selectedRows, rowFilter)}
  `;
}

function renderIssues(issues) {
  if (!issues.length) {
    return `<div class="messages"><p>No validation issues.</p></div>`;
  }

  return `
    <div class="issue-list">
      ${issues
        .map(
          (issue) => `
            <article class="issue-card ${escapeHtml(issue.severity)}">
              <strong>${escapeHtml(issue.title)}</strong>
              <p>${escapeHtml(issue.detail)}</p>
              <small>${escapeHtml(issue.suggested_action)}${issue.affected_row_count ? ` · ${issue.affected_row_count} affected` : ""}</small>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderRowsTable(rows, rowFilter) {
  const filteredRows = filterRows(rows, rowFilter);
  if (!filteredRows.length) {
    return emptyState("No diagnostic rows match this filter.");
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Outcome</th>
            <th>Reason</th>
            <th>Repair</th>
            <th>Row preview</th>
          </tr>
        </thead>
        <tbody>
          ${filteredRows
            .map(
              (row) => `
                <tr>
                  <td>${row.row_number}</td>
                  <td>${escapeHtml(rowTypeLabel(row.row_type))}</td>
                  <td>${escapeHtml(reasonLabel(row.rejection_reason))}</td>
                  <td>${escapeHtml(repairStatusLabel(row))}</td>
                  <td><details><summary>${escapeHtml(rawRowPreview(row))}</summary><pre>${escapeHtml(rawRowText(row))}</pre></details></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderTransactionsView({ filters, imports, transactions, page, selectedTransactionId }) {
  const selectedTransaction = transactions.find(
    (transaction) => transaction.transaction_id === selectedTransactionId,
  );
  return `
    <section class="panel">
      ${renderLedgerFilters("transactions-filter", filters, imports)}
    </section>
    <section class="panel">
      <div class="section-heading">
        <h2>Transactions</h2>
        ${renderPagination(page, transactions.length)}
      </div>
      ${renderTransactionsTable(transactions, selectedTransactionId)}
      ${selectedTransaction ? renderTransactionDetail(selectedTransaction) : ""}
    </section>
  `;
}

export function renderSummaryView({ filters, imports, summary }) {
  return `
    <section class="panel">
      ${renderLedgerFilters("summary-filter", filters, imports)}
    </section>
    <section class="panel">
      <div class="section-heading"><h2>Monthly summary</h2></div>
      ${renderSummaryTable(summary)}
    </section>
  `;
}

function renderLedgerFilters(formId, filters, imports) {
  return `
    <form id="${formId}" class="filter-grid ledger-filter-grid">
      <label><span>Bank</span><select name="bankName">
        <option value="">all</option>
        ${["kotak", "hdfc", "federal"]
          .map(
            (bank) => `<option value="${bank}" ${filters.bankName === bank ? "selected" : ""}>${bank}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Account</span><input name="accountId" value="${escapeHtml(filters.accountId)}" /></label>
      <label><span>Search</span><input name="search" placeholder="narration or ref" value="${escapeHtml(filters.search)}" /></label>
      <label><span>Direction</span><select name="direction">
        <option value="">all</option>
        ${["DEBIT", "CREDIT"]
          .map(
            (direction) =>
              `<option value="${direction}" ${filters.direction === direction ? "selected" : ""}>${direction}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Amount min</span><input type="number" step="0.01" name="amountMin" value="${escapeHtml(filters.amountMin)}" /></label>
      <label><span>Amount max</span><input type="number" step="0.01" name="amountMax" value="${escapeHtml(filters.amountMax)}" /></label>
      <label><span>Duplicate status</span><select name="duplicateConfidence">
        <option value="">all</option>
        ${["UNIQUE", "EXACT_DUPLICATE", "PROBABLE_DUPLICATE", "AMBIGUOUS"]
          .map(
            (value) =>
              `<option value="${value}" ${filters.duplicateConfidence === value ? "selected" : ""}>${value}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Balance</span><select name="hasBalance">
        ${[
          ["", "all"],
          ["true", "has balance"],
          ["false", "missing balance"],
        ]
          .map(
            ([value, label]) =>
              `<option value="${value}" ${filters.hasBalance === value ? "selected" : ""}>${label}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Source import</span><select name="sourceFileId">
        <option value="">all</option>
        ${imports
          .map(
            (item) =>
              `<option value="${item.file_id}" ${filters.sourceFileId === item.file_id ? "selected" : ""}>${escapeHtml(item.original_filename)}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>From</span><input type="date" name="dateFrom" value="${escapeHtml(filters.dateFrom)}" /></label>
      <label><span>To</span><input type="date" name="dateTo" value="${escapeHtml(filters.dateTo)}" /></label>
      <label><span>Page size</span><select name="limit">
        ${[25, 50, 100, 250, 500]
          .map(
            (limit) =>
              `<option value="${limit}" ${Number(filters.limit) === limit ? "selected" : ""}>${limit}</option>`,
          )
          .join("")}
      </select></label>
      <button class="primary-action" type="submit">Apply</button>
      <button id="${formId}-clear" class="secondary-action" type="button">Clear</button>
    </form>
  `;
}

function renderPagination(page, visibleCount) {
  const safePage = page || {
    limit: 50,
    offset: 0,
    total: 0,
    has_previous: false,
    has_next: false,
  };
  const start = visibleCount ? safePage.offset + 1 : 0;
  const end = Math.min(safePage.offset + visibleCount, safePage.total);
  return `
    <div class="pager" aria-label="Transaction pagination">
      <span>Showing ${start}-${end} of ${safePage.total}</span>
      <button id="transactions-prev" class="secondary-action" type="button" ${safePage.has_previous ? "" : "disabled"}>Previous</button>
      <button id="transactions-next" class="secondary-action" type="button" ${safePage.has_next ? "" : "disabled"}>Next</button>
    </div>
  `;
}

function renderTransactionsTable(transactions, selectedTransactionId) {
  if (!transactions.length) {
    return emptyState("No transactions match the current filters.");
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Bank/account</th>
            <th>Direction</th>
            <th>Amount</th>
            <th>Balance</th>
            <th>Description</th>
            <th>Source</th>
            <th>Duplicate</th>
          </tr>
        </thead>
        <tbody>
          ${transactions
            .map(
              (transaction) => `
                <tr class="${transaction.transaction_id === selectedTransactionId ? "selected-row" : ""}">
                  <td>${formatDate(transaction.transaction_date)}</td>
                  <td>${escapeHtml(transaction.bank_name)}<br /><small>${escapeHtml(transaction.account_id || "-")}</small></td>
                  <td>${escapeHtml(transaction.direction)}</td>
                  <td>${formatMoney(transaction.amount)}</td>
                  <td>${formatMoney(transaction.balance)}</td>
                  <td><button class="link-button" type="button" data-transaction-id="${transaction.transaction_id}">${escapeHtml(transactionPreview(transaction))}</button></td>
                  <td>${escapeHtml(transaction.source_filename || "-")}<br /><small>row ${transaction.source_row_number}</small></td>
                  <td>${escapeHtml(transaction.duplicate_confidence)}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderTransactionDetail(transaction) {
  return `
    <aside class="detail-drawer">
      <div class="section-heading">
        <h3>Transaction detail</h3>
        <span>${escapeHtml(transaction.direction)} · ${formatMoney(transaction.amount)}</span>
      </div>
      <dl>
        <dt>Narration</dt><dd>${escapeHtml(transaction.description_raw)}</dd>
        <dt>Reference</dt><dd>${escapeHtml(transaction.reference_number || "-")}</dd>
        <dt>Source file</dt><dd>${escapeHtml(transaction.source_filename || "-")}</dd>
        <dt>Source row</dt><dd>${transaction.source_row_number}</dd>
        <dt>Statement period</dt><dd>${formatDate(transaction.source_statement_start_date)} to ${formatDate(transaction.source_statement_end_date)}</dd>
        <dt>Duplicate status</dt><dd>${escapeHtml(transaction.duplicate_confidence)}</dd>
        <dt>Fingerprint</dt><dd class="mono">${escapeHtml(transaction.transaction_fingerprint)}</dd>
        <dt>Created</dt><dd>${formatDateTime(transaction.created_at)}</dd>
      </dl>
    </aside>
  `;
}

function renderSummaryTable(summary) {
  if (!summary.length) {
    return emptyState("No monthly summary for the current filters.");
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Month</th>
            <th>Transactions</th>
            <th>Debits</th>
            <th>Credits</th>
            <th>Debit total</th>
            <th>Credit total</th>
            <th>Net</th>
            <th>Opening balance</th>
            <th>Closing balance</th>
          </tr>
        </thead>
        <tbody>
          ${summary
            .map(
              (row) => `
                <tr>
                  <td><button class="link-button" type="button" data-summary-period="${row.period_start}">${formatDate(row.period_start)}</button></td>
                  <td>${row.transaction_count}</td>
                  <td>${row.debit_count}</td>
                  <td>${row.credit_count}</td>
                  <td>${formatMoney(row.debit_total)}</td>
                  <td>${formatMoney(row.credit_total)}</td>
                  <td>${formatMoney(row.net_amount)}</td>
                  <td>${formatMoney(row.opening_balance)}</td>
                  <td>${formatMoney(row.closing_balance)}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function filterImports(imports, filters) {
  const filename = filters.filename.trim().toLowerCase();
  const accountId = filters.accountId.trim().toLowerCase();
  return imports.filter((item) => {
    if (filters.bankName && item.bank_name !== filters.bankName) {
      return false;
    }
    if (filters.status && item.status !== filters.status) {
      return false;
    }
    if (filename && !item.original_filename.toLowerCase().includes(filename)) {
      return false;
    }
    if (accountId && !(item.account_id || "").toLowerCase().includes(accountId)) {
      return false;
    }
    if (filters.dateFrom && (!item.statement_end_date || item.statement_end_date < filters.dateFrom)) {
      return false;
    }
    if (filters.dateTo && (!item.statement_start_date || item.statement_start_date > filters.dateTo)) {
      return false;
    }
    if (filters.quick === "needs_action" && !item.needs_action) {
      return false;
    }
    if (filters.quick === "warnings" && !item.has_warnings) {
      return false;
    }
    if (filters.quick === "ready" && item.status !== "PASS") {
      return false;
    }
    if (filters.quick === "suspicious" && !item.has_suspicious_rows) {
      return false;
    }
    if (filters.quick === "duplicates" && !item.has_duplicates) {
      return false;
    }
    return true;
  });
}

function filterRows(rows, rowFilter) {
  if (rowFilter === "all") {
    return rows;
  }
  if (rowFilter === "issues") {
    return rows.filter(
      (row) =>
        row.row_type === "suspicious" ||
        row.repaired_row ||
        row.repair_status === "not_repairable",
    );
  }
  if (rowFilter === "repaired") {
    return rows.filter((row) => row.repaired_row || row.repair_status === "repaired");
  }
  return rows.filter((row) => row.row_type === rowFilter);
}

function rowTypeLabel(type) {
  return rowTypeLabels[type] || type || "-";
}

function repairStatusLabel(row) {
  return repairStatusLabels[row.repair_status] || (row.repaired_row ? "Repaired" : "Unknown");
}

function reasonLabel(reason) {
  return reasonLabels[reason] || reason || "-";
}

function rawRowText(row) {
  return row.raw_text || JSON.stringify(row.raw_payload || []);
}

function rawRowPreview(row) {
  const text = rawRowText(row);
  return text.length > 90 ? `${text.slice(0, 90)}...` : text;
}

function transactionPreview(transaction) {
  const text = transaction.description_raw || transaction.reference_number || transaction.transaction_id;
  return text.length > 80 ? `${text.slice(0, 80)}...` : text;
}

function sum(items, key) {
  return items.reduce((total, item) => total + Number(item[key] || 0), 0);
}
