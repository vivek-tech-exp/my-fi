import {
  getImport,
  getImportReport,
  getImportRows,
  getTransactionSummary,
  listImports,
  listTransactions,
  reprocessImport,
  uploadCsvBatch,
} from "./api-client.js";
import {
  renderImportsView,
  renderSummaryView,
  renderTransactionsView,
  renderUploadView,
} from "./components.js";
import { setState, setTransactionFilters, state } from "./state.js";

const viewTitles = {
  upload: "Upload",
  imports: "Imports",
  transactions: "Transactions",
  summary: "Summary",
};

const viewRoot = document.querySelector("#view-root");
const viewTitle = document.querySelector("#view-title");
const globalStatus = document.querySelector("#global-status");

function setStatus(message, isError = false) {
  globalStatus.textContent = message || "";
  globalStatus.classList.toggle("error-state", isError);
}

function render() {
  viewTitle.textContent = viewTitles[state.activeView];
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.activeView);
  });

  if (state.activeView === "upload") {
    viewRoot.innerHTML = renderUploadView({
      selectedBank: state.selectedBank,
      uploadResult: state.uploadResult,
    });
    bindUploadView();
    return;
  }

  if (state.activeView === "imports") {
    viewRoot.innerHTML = renderImportsView({
      imports: state.imports,
      selectedImportId: state.selectedImportId,
      selectedImport: state.selectedImport,
      selectedReport: state.selectedReport,
      selectedRows: state.selectedRows,
      rowFilter: state.rowFilter,
    });
    bindImportsView();
    return;
  }

  if (state.activeView === "transactions") {
    viewRoot.innerHTML = renderTransactionsView({
      filters: state.transactionFilters,
      transactions: state.transactions,
      page: state.transactionPage,
    });
    bindLedgerFilter("transactions-filter", refreshTransactions);
    bindTransactionPager();
    return;
  }

  viewRoot.innerHTML = renderSummaryView({
    filters: state.transactionFilters,
    summary: state.summary,
  });
  bindLedgerFilter("summary-filter", refreshSummary);
}

function bindNavigation() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const nextView = button.dataset.view;
      setState({ activeView: nextView });
      render();
      await loadViewData(nextView);
    });
  });
}

function bindUploadView() {
  document.querySelector("#upload-bank")?.addEventListener("change", (event) => {
    setState({ selectedBank: event.target.value });
  });

  document.querySelector("#upload-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const files = document.querySelector("#upload-files").files;
    if (!files.length) {
      setStatus("Choose one or more CSV files first.", true);
      return;
    }

    try {
      setStatus(`Uploading ${files.length} file(s)...`);
      const uploadResult = await uploadCsvBatch({
        bankName: state.selectedBank,
        files,
      });
      setState({ uploadResult });
      setStatus(`Upload complete: ${uploadResult.succeeded} succeeded, ${uploadResult.failed} failed.`);
      render();
      await refreshImports({ silent: true });
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

function bindImportsView() {
  document.querySelector("#refresh-imports")?.addEventListener("click", () => refreshImports());
  document.querySelectorAll("[data-import-id]").forEach((button) => {
    button.addEventListener("click", () => selectImport(button.dataset.importId));
  });
  document.querySelector("#row-filter")?.addEventListener("change", (event) => {
    setState({ rowFilter: event.target.value });
    render();
  });
  document.querySelector("#reprocess-import")?.addEventListener("click", async () => {
    if (!state.selectedImportId) {
      return;
    }
    try {
      setStatus("Reprocessing selected import...");
      await reprocessImport(state.selectedImportId);
      await Promise.all([refreshImports({ silent: true }), selectImport(state.selectedImportId, true)]);
      await Promise.all([refreshTransactions({ silent: true }), refreshSummary({ silent: true })]);
      setStatus("Reprocess complete. Import detail, rows, transactions, and summary refreshed.");
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

function bindLedgerFilter(formId, refreshCallback) {
  document.querySelector(`#${formId}`)?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setTransactionFilters({
      bankName: formData.get("bankName"),
      accountId: formData.get("accountId"),
      direction: formData.get("direction"),
      dateFrom: formData.get("dateFrom"),
      dateTo: formData.get("dateTo"),
      offset: 0,
    });
    await refreshCallback();
  });
}

function bindTransactionPager() {
  document.querySelector("#transactions-prev")?.addEventListener("click", async () => {
    const limit = Number(state.transactionFilters.limit || 100);
    setTransactionFilters({
      offset: Math.max(Number(state.transactionFilters.offset || 0) - limit, 0),
    });
    await refreshTransactions();
  });
  document.querySelector("#transactions-next")?.addEventListener("click", async () => {
    const limit = Number(state.transactionFilters.limit || 100);
    setTransactionFilters({
      offset: Number(state.transactionFilters.offset || 0) + limit,
    });
    await refreshTransactions();
  });
}

async function loadViewData(view) {
  if (view === "imports") {
    await refreshImports();
  } else if (view === "transactions") {
    await refreshTransactions();
  } else if (view === "summary") {
    await refreshSummary();
  }
}

async function refreshImports({ silent = false } = {}) {
  try {
    if (!silent) {
      setStatus("Loading imports...");
    }
    const imports = await listImports();
    setState({ imports });
    if (!silent) {
      setStatus(`Loaded ${imports.length} import(s).`);
    }
    if (state.activeView === "imports") {
      render();
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function selectImport(fileId, silent = false) {
  try {
    if (!silent) {
      setStatus("Loading import detail...");
    }
    const [detailResult, reportResult, rowsResult] = await Promise.allSettled([
      getImport(fileId),
      getImportReport(fileId),
      getImportRows(fileId),
    ]);

    if (detailResult.status === "rejected") {
      throw detailResult.reason;
    }

    setState({
      selectedImportId: fileId,
      selectedImport: detailResult.value,
      selectedReport: reportResult.status === "fulfilled" ? reportResult.value : null,
      selectedRows: rowsResult.status === "fulfilled" ? rowsResult.value : [],
    });

    if (reportResult.status === "rejected") {
      setStatus(`Import loaded, but report failed: ${reportResult.reason.message}`, true);
    } else if (rowsResult.status === "rejected") {
      setStatus(`Import loaded, but rows failed: ${rowsResult.reason.message}`, true);
    } else if (!silent) {
      setStatus(`Loaded import ${fileId}.`);
    }
    render();
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function refreshTransactions({ silent = false } = {}) {
  try {
    if (!silent) {
      setStatus("Loading transactions...");
    }
    const transactionResult = await listTransactions(state.transactionFilters);
    setState({
      transactions: transactionResult.rows,
      transactionPage: transactionResult.page,
    });
    if (!silent) {
      setStatus(`Loaded ${transactionResult.rows.length} transaction(s).`);
    }
    if (state.activeView === "transactions") {
      render();
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function refreshSummary({ silent = false } = {}) {
  try {
    if (!silent) {
      setStatus("Loading monthly summary...");
    }
    const summary = await getTransactionSummary(state.transactionFilters);
    setState({ summary });
    if (!silent) {
      setStatus(`Loaded ${summary.length} monthly row(s).`);
    }
    if (state.activeView === "summary") {
      render();
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

bindNavigation();
render();
