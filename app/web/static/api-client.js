const jsonHeaders = { Accept: "application/json" };

async function requestJson(endpoint, options = {}) {
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      ...jsonHeaders,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      detail = response.statusText || "Request failed";
    }
    throw new Error(`${endpoint} returned ${response.status}: ${detail}`);
  }

  return response.json();
}

function appendOptionalParam(params, key, value) {
  if (value !== undefined && value !== null && String(value).trim() !== "") {
    params.set(key, String(value).trim());
  }
}

export async function uploadCsvBatch({ bankName, files }) {
  const formData = new FormData();
  formData.set("bank_name", bankName);
  Array.from(files).forEach((file) => formData.append("files", file));

  return requestJson("/imports/csv/batch", {
    method: "POST",
    body: formData,
  });
}

export async function listImports() {
  return requestJson("/imports");
}

export async function getImport(fileId) {
  return requestJson(`/imports/${encodeURIComponent(fileId)}`);
}

export async function getImportReport(fileId) {
  return requestJson(`/imports/${encodeURIComponent(fileId)}/report`);
}

export async function getImportRows(fileId) {
  return requestJson(`/imports/${encodeURIComponent(fileId)}/rows`);
}

export async function reprocessImport(fileId) {
  return requestJson(`/imports/${encodeURIComponent(fileId)}/reprocess`, { method: "POST" });
}

export async function listTransactions(filters) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "bank_name", filters.bankName);
  appendOptionalParam(params, "account_id", filters.accountId);
  appendOptionalParam(params, "direction", filters.direction);
  appendOptionalParam(params, "transaction_date_from", filters.dateFrom);
  appendOptionalParam(params, "transaction_date_to", filters.dateTo);
  appendOptionalParam(params, "limit", filters.limit || 100);
  appendOptionalParam(params, "offset", filters.offset || 0);

  return requestJson(`/transactions?${params.toString()}`);
}

export async function getTransactionSummary(filters) {
  const params = new URLSearchParams({ group_by: "month" });
  appendOptionalParam(params, "bank_name", filters.bankName);
  appendOptionalParam(params, "account_id", filters.accountId);
  appendOptionalParam(params, "direction", filters.direction);
  appendOptionalParam(params, "transaction_date_from", filters.dateFrom);
  appendOptionalParam(params, "transaction_date_to", filters.dateTo);
  appendOptionalParam(params, "limit", filters.limit || 100);
  appendOptionalParam(params, "offset", filters.offset || 0);

  return requestJson(`/transactions/summary?${params.toString()}`);
}
