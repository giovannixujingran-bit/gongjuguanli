// 自动生成，勿手改 —— 由 tools/generate_contracts.py 从 shared/schema/event.schema.json 生成
export interface UsageEvent {
  record_id: string;
  schema_version: string;
  tool_id: string;
  conversation_id: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  status: "success" | "failed" | "timeout";
  ingested_at?: string | null;
  model?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  cost?: number | null;
  cost_source?: "source" | "computed" | null;
  user_id?: string | null;
  team_id?: string | null;
  result_quality?: number | string | null;
  adopted?: boolean | null;
  input_content?: string | null;
  output_content?: string | null;
  metadata?: Record<string, unknown> | null;
}
