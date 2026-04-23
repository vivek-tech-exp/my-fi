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
  resolveSourceImportSelection,
  renderSummaryView,
  renderTransactionsView,
  renderUploadView,
} from "./components.js";
import { setBusy, setImportFilters, setState, setTransactionFilters, state } from "./state.js";

const viewTitles = {
  upload: "Upload",
  imports: "Imports",
  transactions: "Transactions",
  summary: "Summary",
};

const emptyImportFilters = {
  bankName: "",
  status: "",
  accountId: "",
  filename: "",
  dateFrom: "",
  dateTo: "",
  quick: "",
};

const emptyTransactionFilters = {
  bankName: "",
  accountId: "",
  direction: "",
  search: "",
  amountMin: "",
  amountMax: "",
  duplicateConfidence: "",
  hasBalance: "",
  sourceFileId: "",
  sourceImportQuery: "",
  dateFrom: "",
  dateTo: "",
  limit: 50,
  offset: 0,
};

const viewRoot = document.querySelector("#view-root");
const viewTitle = document.querySelector("#view-title");
const globalStatus = document.querySelector("#global-status");
const rail = document.querySelector(".rail");
const railToggle = document.querySelector("#rail-toggle");

function closeRail() {
  rail?.classList.remove("is-open");
  railToggle?.setAttribute("aria-expanded", "false");
}

function toggleRail() {
  if (!rail || !railToggle) {
    return;
  }
  const isOpen = rail.classList.toggle("is-open");
  railToggle.setAttribute("aria-expanded", String(isOpen));
}

function setStatus(message, isError = false) {
  globalStatus.textContent = message || "";
  globalStatus.classList.toggle("error-state", isError);
}

function anyBusy() {
  return Object.values(state.busy).some(Boolean);
}

function render() {
  viewTitle.textContent = viewTitles[state.activeView];
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.activeView);
    button.disabled = anyBusy();
  });

  if (state.activeView === "upload") {
    viewRoot.innerHTML = renderUploadView({
      selectedBank: state.selectedBank,
      uploadResult: state.uploadResult,
      isBusy: state.busy.upload,
    });
    bindUploadView();
    return;
  }

  if (state.activeView === "imports") {
    viewRoot.innerHTML = renderImportsView({
      imports: state.imports,
      importFilters: state.importFilters,
      selectedImportId: state.selectedImportId,
      selectedImport: state.selectedImport,
      selectedReport: state.selectedReport,
      selectedRows: state.selectedRows,
      rowFilter: state.rowFilter,
      busy: state.busy,
    });
    bindImportsView();
    return;
  }

  if (state.activeView === "transactions") {
    viewRoot.innerHTML = renderTransactionsView({
      filters: state.transactionFilters,
      imports: state.imports,
      transactions: state.transactions,
      page: state.transactionPage,
      selectedTransactionId: state.selectedTransactionId,
      busy: state.busy,
    });
    bindLedgerFilter("transactions-filter", refreshTransactions);
    bindTransactionPager();
    bindTransactionDetailButtons();
    return;
  }

  viewRoot.innerHTML = renderSummaryView({
    filters: state.transactionFilters,
    imports: state.imports,
    summary: state.summary,
    busy: state.busy,
  });
  bindLedgerFilter("summary-filter", refreshSummary);
  bindSummaryDrilldown();
}

function bindNavigation() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const nextView = button.dataset.view;
      closeRail();
      setState({ activeView: nextView });
      render();
      await loadViewData(nextView);
    });
  });
}

function bindRailToggle() {
  railToggle?.addEventListener("click", () => {
    toggleRail();
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) {
      closeRail();
    }
  });
}

function bindUploadView() {
  document.querySelector("#upload-bank")?.addEventListener("change", (event) => {
    setState({ selectedBank: event.target.value });
  });

  document.querySelector("#upload-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy.upload) {
      return;
    }
    const files = document.querySelector("#upload-files").files;
    if (!files.length) {
      setStatus("Choose one or more CSV files first.", true);
      return;
    }

    setBusy("upload", true);
    render();
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
    } finally {
      setBusy("upload", false);
      render();
    }
  });
}

function bindImportsView() {
  document.querySelector("#refresh-imports")?.addEventListener("click", () => {
    if (!state.busy.imports && !state.busy.importDetail && !state.busy.reprocess) {
      refreshImports();
    }
  });
  document.querySelector("#imports-filter")?.addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.busy.imports || state.busy.importDetail || state.busy.reprocess) {
      return;
    }
    const formData = new FormData(event.currentTarget);
    setImportFilters({
      bankName: formData.get("bankName"),
      status: formData.get("status"),
      accountId: formData.get("accountId"),
      filename: formData.get("filename"),
      dateFrom: formData.get("dateFrom"),
      dateTo: formData.get("dateTo"),
      quick: formData.get("quick"),
    });
    render();
  });
  document.querySelector("#clear-import-filters")?.addEventListener("click", () => {
    if (state.busy.imports || state.busy.importDetail || state.busy.reprocess) {
      return;
    }
    setState({ importFilters: { ...emptyImportFilters } });
    render();
  });
  document.querySelectorAll("[data-import-id]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!state.busy.importDetail && !state.busy.reprocess) {
        selectImport(button.dataset.importId);
      }
    });
  });
  document.querySelector("#row-filter")?.addEventListener("change", (event) => {
    setState({ rowFilter: event.target.value });
    render();
  });
  document.querySelector("#reprocess-import")?.addEventListener("click", async () => {
    if (!state.selectedImportId || state.busy.reprocess) {
      return;
    }
    setBusy("reprocess", true);
    render();
    try {
      setStatus("Reprocessing selected import...");
      await reprocessImport(state.selectedImportId);
      await Promise.all([refreshImports({ silent: true }), selectImport(state.selectedImportId, true)]);
      await Promise.all([refreshTransactions({ silent: true }), refreshSummary({ silent: true })]);
      setStatus("Reprocess complete. Import detail, diagnostics, transactions, and summary refreshed.");
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      setBusy("reprocess", false);
      render();
    }
  });
}

function bindLedgerFilter(formId, refreshCallback) {
  document.querySelector(`#${formId}`)?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const busyKey = formId === "summary-filter" ? "summary" : "transactions";
    if (state.busy[busyKey]) {
      return;
    }
    const formData = new FormData(event.currentTarget);
    const nextFilters = {
      bankName: formData.get("bankName"),
      accountId: formData.get("accountId"),
      direction: formData.get("direction"),
      search: formData.get("search"),
      amountMin: formData.get("amountMin"),
      amountMax: formData.get("amountMax"),
      duplicateConfidence: formData.get("duplicateConfidence"),
      hasBalance: formData.get("hasBalance"),
      sourceImportQuery: formData.get("sourceImportQuery"),
      dateFrom: formData.get("dateFrom"),
      dateTo: formData.get("dateTo"),
      limit: formData.get("limit")
        ? Number(formData.get("limit") || 50)
        : state.transactionFilters.limit,
      offset: 0,
    };

    try {
      setTransactionFilters({
        ...nextFilters,
        ...resolveSourceImportSelection(nextFilters, state.imports),
      });
    } catch (error) {
      setStatus(error.message, true);
      return;
    }
    await refreshCallback();
  });

  document.querySelector(`#${formId}-clear`)?.addEventListener("click", async () => {
    const busyKey = formId === "summary-filter" ? "summary" : "transactions";
    if (state.busy[busyKey]) {
      return;
    }
    setState({ transactionFilters: { ...emptyTransactionFilters }, selectedTransactionId: null });
    await refreshCallback();
  });
}

function bindTransactionPager() {
  document.querySelector("#transactions-prev")?.addEventListener("click", async () => {
    if (state.busy.transactions) {
      return;
    }
    const limit = Number(state.transactionFilters.limit || 50);
    setTransactionFilters({
      offset: Math.max(Number(state.transactionFilters.offset || 0) - limit, 0),
    });
    await refreshTransactions();
  });
  document.querySelector("#transactions-next")?.addEventListener("click", async () => {
    if (state.busy.transactions) {
      return;
    }
    const limit = Number(state.transactionFilters.limit || 50);
    setTransactionFilters({
      offset: Number(state.transactionFilters.offset || 0) + limit,
    });
    await refreshTransactions();
  });
}

function bindTransactionDetailButtons() {
  document.querySelectorAll("[data-transaction-id]").forEach((button) => {
    button.addEventListener("click", () => {
      setState({ selectedTransactionId: button.dataset.transactionId });
      render();
    });
  });
  document.querySelectorAll("[data-open-source-import]").forEach((button) => {
    button.addEventListener("click", async () => {
      await openSourceImport(button.dataset.openSourceImport);
    });
  });
}

function bindSummaryDrilldown() {
  document.querySelectorAll("[data-summary-period]").forEach((button) => {
    button.addEventListener("click", async () => {
      const periodStart = button.dataset.summaryPeriod;
      setTransactionFilters({
        dateFrom: periodStart,
        dateTo: monthEnd(periodStart),
        offset: 0,
      });
      setState({ activeView: "transactions" });
      render();
      await refreshTransactions();
    });
  });
}

async function loadViewData(view) {
  if (view === "imports") {
    await refreshImports();
  } else if (view === "transactions") {
    await ensureImportsLoaded();
    await refreshTransactions();
  } else if (view === "summary") {
    await ensureImportsLoaded();
    await refreshSummary();
  }
}

async function ensureImportsLoaded() {
  if (!state.imports.length) {
    await refreshImports({ silent: true });
  }
}

async function refreshImports({ silent = false } = {}) {
  setBusy("imports", true);
  render();
  try {
    if (!silent) {
      setStatus("Loading imports...");
    }
    const imports = await listImports();
    if (state.selectedImportId && !imports.some((item) => item.file_id === state.selectedImportId)) {
      setState({
        imports,
        selectedImportId: null,
        selectedImport: null,
        selectedReport: null,
        selectedRows: [],
      });
    } else {
      setState({ imports });
    }
    if (!silent) {
      setStatus(`Loaded ${imports.length} import(s).`);
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy("imports", false);
    render();
  }
}

async function selectImport(fileId, silent = false) {
  setBusy("importDetail", true);
  if (state.activeView === "imports") {
    render();
  }
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
      rowFilter: "issues",
    });

    if (reportResult.status === "rejected") {
      setStatus(`Import loaded, but report failed: ${reportResult.reason.message}`, true);
    } else if (rowsResult.status === "rejected") {
      setStatus(`Import loaded, but diagnostics failed: ${rowsResult.reason.message}`, true);
    } else if (!silent) {
      setStatus(`Loaded import ${fileId}.`);
    }
    render();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy("importDetail", false);
    if (state.activeView === "imports") {
      render();
    }
  }
}

async function refreshTransactions({ silent = false } = {}) {
  setBusy("transactions", true);
  if (state.activeView === "transactions") {
    render();
  }
  try {
    if (!silent) {
      setStatus("Loading transactions...");
    }
    const transactionResult = await listTransactions(state.transactionFilters);
    setState({
      transactions: transactionResult.items,
      selectedTransactionId: null,
      transactionPage: {
        total: transactionResult.total,
        limit: transactionResult.limit,
        offset: transactionResult.offset,
        has_next: transactionResult.has_next,
        has_previous: transactionResult.has_previous,
      },
    });
    if (!silent) {
      setStatus(`Loaded ${transactionResult.items.length} of ${transactionResult.total} transaction(s).`);
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy("transactions", false);
    if (state.activeView === "transactions") {
      render();
    }
  }
}

async function refreshSummary({ silent = false } = {}) {
  setBusy("summary", true);
  if (state.activeView === "summary") {
    render();
  }
  try {
    if (!silent) {
      setStatus("Loading monthly summary...");
    }
    const summary = await getTransactionSummary({ ...state.transactionFilters, offset: 0 });
    setState({ summary });
    if (!silent) {
      setStatus(`Loaded ${summary.length} monthly row(s).`);
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy("summary", false);
    if (state.activeView === "summary") {
      render();
    }
  }
}

async function openSourceImport(fileId) {
  await ensureImportsLoaded();
  const sourceImport = state.imports.find((item) => item.file_id === fileId);
  setState({
    activeView: "imports",
    importFilters: {
      ...emptyImportFilters,
      bankName: sourceImport?.bank_name || "",
      accountId: sourceImport?.account_id || "",
    },
  });
  render();
  await selectImport(fileId, true);
}

function monthEnd(periodStart) {
  const [year, month] = periodStart.split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
}

bindNavigation();
bindRailToggle();
render();
loadViewData(state.activeView);
