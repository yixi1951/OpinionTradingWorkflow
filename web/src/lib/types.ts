export type ServiceHealth = {
  status?: string;
  error?: string;
  service?: string;
  version?: string;
};

export type StatusResponse = {
  api: string;
  collector: ServiceHealth;
  inference: ServiceHealth;
  compute: ServiceHealth;
};

export type StockQuote = {
  symbol?: string;
  name?: string;
  last_price?: number | null;
  change_pct?: number | null;
  change_amount?: number | null;
  as_of?: string | null;
  market_status?: "open" | "closed" | "lunch" | string;
  source?: string;
  delayed?: boolean;
  ok?: boolean;
  error?: string;
  note?: string;
};

export type PickRow = {
  symbol?: string;
  name?: string;
  rank?: number;
  score?: number;
  confidence?: number;
  action?: string;
  reason?: string;
  explanation?: string;
  quote?: StockQuote;
  [key: string]: unknown;
};

export type PicksResponse = {
  ok?: boolean;
  error?: string;
  picks?: PickRow[];
  trade_date?: string;
  [key: string]: unknown;
};

export type SentimentRow = {
  trade_date?: string;
  symbol?: string;
  platform?: string;
  sentiment_score?: number;
  [key: string]: unknown;
};

export type WalkForwardReport = {
  avg_test_accuracy?: number;
  avg_test_sharpe?: number;
  avg_degradation_accuracy?: number;
  recommendation?: string;
  folds?: Array<Record<string, unknown>>;
};
