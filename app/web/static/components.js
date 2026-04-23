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
    help: "Not trusted yet. Review messages and rows.",
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
  not_required: "Not needed",
  repaired: "Repaired",
  not_repairable: "Could not repair",
  not_attempted: "Not attempted",
};

const reasonLabels = {
  blank_row: "Blank row",
  header_row: "Header row",
  repeated_header_row: "Repeated header",
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

function statusHelp(status) {
  return statusMeta[status]?.help || "";
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
  selectedImportId,
  selectedImport,
  selectedReport,
  selectedRows,
  rowFilter,
}) {
  return `
    <section class="split-view">
      <div class="panel">
        <div class="section-heading">
          <h2>Imports</h2>
          <button id="refresh-imports" class="secondary-action" type="button">Refresh</button>
        </div>
        ${renderImportList(imports, selectedImportId)}
      </div>
      <div class="panel detail-panel">
        ${renderImportDetail({ selectedImport, selectedReport, selectedRows, rowFilter })}
      </div>
    </section>
  `;
}

function renderImportList(imports, selectedImportId) {
  if (!imports.length) {
    return emptyState("No imports yet.");
  }

  return `
    <div class="import-list">
      ${imports
        .map(
          (item) => `
            <button class="import-row ${item.file_id === selectedImportId ? "active" : ""}" type="button" data-import-id="${item.file_id}">
              <span>
                <strong>${escapeHtml(item.original_filename)}</strong>
                <small>${escapeHtml(item.account_id || "account pending")}</small>
              </span>
              <span>
                ${statusPill(item.status)}
                <small>${formatDate(item.statement_start_date)} to ${formatDate(item.statement_end_date)}</small>
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
    return emptyState("Select an import to inspect report and rows.");
  }

  const report = selectedReport || selectedImport.report;
  const messages = report?.messages || [];
  return `
    <div class="section-heading">
      <div>
        <h2>${escapeHtml(selectedImport.original_filename)}</h2>
        <p>${escapeHtml(selectedImport.account_id || "account pending")}</p>
      </div>
      <button id="reprocess-import" class="secondary-action" type="button">Reprocess</button>
    </div>
    <div class="metric-strip">
      <span>${statusPill(selectedImport.status)}</span>
      <span>${escapeHtml(statusHelp(selectedImport.status))}</span>
      <span>${report?.transactions_imported ?? 0} transactions</span>
      <span>${report?.suspicious_rows ?? 0} suspicious</span>
      <span>${report?.duplicate_rows ?? 0} duplicates</span>
    </div>
    <div class="messages">
      ${messages.length ? messages.map((message) => `<p>${escapeHtml(message)}</p>`).join("") : "<p>No validation messages.</p>"}
    </div>
    <div class="row-toolbar">
      <label>
        <span>Rows</span>
        <select id="row-filter">
          ${["all", "accepted", "ignored", "suspicious"]
            .map(
              (value) =>
                `<option value="${value}" ${value === rowFilter ? "selected" : ""}>${value}</option>`,
            )
            .join("")}
        </select>
      </label>
    </div>
    ${renderRowsTable(selectedRows, rowFilter)}
  `;
}

function renderRowsTable(rows, rowFilter) {
  const filteredRows = rowFilter === "all" ? rows : rows.filter((row) => row.row_type === rowFilter);
  if (!filteredRows.length) {
    return emptyState("No rows match this filter.");
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Outcome</th>
            <th>Reason</th>
            <th>Repair status</th>
            <th>Raw text</th>
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

function rawRowText(row) {
  return row.raw_text || JSON.stringify(row.raw_payload || []);
}

function rawRowPreview(row) {
  const text = rawRowText(row);
  return text.length > 90 ? `${text.slice(0, 90)}...` : text;
}

export function renderTransactionsView({ filters, transactions, page }) {
  return `
    <section class="panel">
      ${renderLedgerFilters("transactions-filter", filters)}
    </section>
    <section class="panel">
      <div class="section-heading">
        <h2>Transactions</h2>
        ${renderPagination(page, transactions.length)}
      </div>
      ${renderTransactionsTable(transactions)}
    </section>
  `;
}

export function renderSummaryView({ filters, summary }) {
  return `
    <section class="panel">
      ${renderLedgerFilters("summary-filter", filters)}
    </section>
    <section class="panel">
      <div class="section-heading"><h2>Monthly summary</h2></div>
      ${renderSummaryTable(summary)}
    </section>
  `;
}

function renderLedgerFilters(formId, filters) {
  return `
    <form id="${formId}" class="filter-grid">
      <label><span>Bank</span><select name="bankName">
        <option value="">all</option>
        ${["kotak", "hdfc", "federal"]
          .map(
            (bank) => `<option value="${bank}" ${filters.bankName === bank ? "selected" : ""}>${bank}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>Account</span><input name="accountId" value="${escapeHtml(filters.accountId)}" /></label>
      <label><span>Direction</span><select name="direction">
        <option value="">all</option>
        ${["DEBIT", "CREDIT"]
          .map(
            (direction) =>
              `<option value="${direction}" ${filters.direction === direction ? "selected" : ""}>${direction}</option>`,
          )
          .join("")}
      </select></label>
      <label><span>From</span><input type="date" name="dateFrom" value="${escapeHtml(filters.dateFrom)}" /></label>
      <label><span>To</span><input type="date" name="dateTo" value="${escapeHtml(filters.dateTo)}" /></label>
      <button class="primary-action" type="submit">Apply</button>
    </form>
  `;
}

function renderPagination(page, visibleCount) {
  const safePage = page || { limit: 100, offset: 0, hasPrevious: false, hasNext: false };
  const start = visibleCount ? safePage.offset + 1 : 0;
  const end = safePage.offset + visibleCount;
  return `
    <div class="pager" aria-label="Transaction pagination">
      <span>Showing ${start}-${end}</span>
      <button id="transactions-prev" class="secondary-action" type="button" ${safePage.hasPrevious ? "" : "disabled"}>Previous</button>
      <button id="transactions-next" class="secondary-action" type="button" ${safePage.hasNext ? "" : "disabled"}>Next</button>
    </div>
  `;
}

function renderTransactionsTable(transactions) {
  if (!transactions.length) {
    return emptyState("No transactions match the current filters.");
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Direction</th>
            <th>Amount</th>
            <th>Balance</th>
            <th>Description</th>
            <th>Source row</th>
          </tr>
        </thead>
        <tbody>
          ${transactions
            .map(
              (transaction) => `
                <tr>
                  <td>${formatDate(transaction.transaction_date)}</td>
                  <td>${escapeHtml(transaction.direction)}</td>
                  <td>${formatMoney(transaction.amount)}</td>
                  <td>${formatMoney(transaction.balance)}</td>
                  <td>${escapeHtml(transaction.description_raw)}</td>
                  <td>${transaction.source_row_number}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
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
            <th>Count</th>
            <th>Debit</th>
            <th>Credit</th>
            <th>Net</th>
          </tr>
        </thead>
        <tbody>
          ${summary
            .map(
              (row) => `
                <tr>
                  <td>${formatDate(row.period_start)}</td>
                  <td>${row.transaction_count}</td>
                  <td>${formatMoney(row.debit_total)}</td>
                  <td>${formatMoney(row.credit_total)}</td>
                  <td>${formatMoney(row.net_amount)}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}
