export const state = {
  activeView: "imports",
  selectedBank: "kotak",
  selectedImportId: null,
  rowFilter: "issues",
  busy: {
    upload: false,
    imports: false,
    importDetail: false,
    reprocess: false,
    transactions: false,
    summary: false,
  },
  importFilters: {
    bankName: "",
    status: "",
    accountId: "",
    filename: "",
    dateFrom: "",
    dateTo: "",
    quick: "",
  },
  imports: [],
  selectedImport: null,
  selectedReport: null,
  selectedRows: [],
  uploadResult: null,
  transactions: [],
  selectedTransactionId: null,
  transactionPage: {
    total: 0,
    limit: 50,
    offset: 0,
    hasNext: false,
    hasPrevious: false,
  },
  summary: [],
  transactionFilters: {
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
  },
};

export function setState(updates) {
  Object.assign(state, updates);
}

export function setImportFilters(updates) {
  state.importFilters = {
    ...state.importFilters,
    ...updates,
  };
}

export function setTransactionFilters(updates) {
  state.transactionFilters = {
    ...state.transactionFilters,
    ...updates,
  };
}

export function setBusy(key, value) {
  state.busy = {
    ...state.busy,
    [key]: value,
  };
}
