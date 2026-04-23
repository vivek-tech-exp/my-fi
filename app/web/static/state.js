export const state = {
  activeView: "upload",
  selectedBank: "kotak",
  selectedImportId: null,
  rowFilter: "all",
  imports: [],
  selectedImport: null,
  selectedReport: null,
  selectedRows: [],
  uploadResult: null,
  transactions: [],
  transactionPage: {
    hasNext: false,
  },
  summary: [],
  transactionFilters: {
    bankName: "",
    accountId: "",
    direction: "",
    dateFrom: "",
    dateTo: "",
    limit: 100,
    offset: 0,
  },
};

export function setState(updates) {
  Object.assign(state, updates);
}

export function setTransactionFilters(updates) {
  state.transactionFilters = {
    ...state.transactionFilters,
    ...updates,
  };
}
