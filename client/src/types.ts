export interface ReasoningStep {
  tool:   string;
  input:  Record<string, unknown>;
  output: unknown;
}

export interface Message {
  role:                   'user' | 'assistant';
  content:                string;
  reasoning_steps?:       ReasoningStep[];
  thinking?:              string;
  follow_up_suggestions?: string[];
  loading?:               boolean;
  isError?:               boolean;
  rateLimitReset?:        string;
}
