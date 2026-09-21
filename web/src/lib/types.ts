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

export type PickRow = {
  symbol?: string;
  rank?: number;
  score?: number;
  confidence?: number;
  action?: string;
  reason?: string;
  explanation?: string;
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
