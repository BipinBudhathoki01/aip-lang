export interface PromptToken {
  type: 'text' | 'variable';
  text?: string;
  name?: string;
}

export interface TypeSpecNode {
  kind: 'type' | 'object';
  name?: string;
  type_args?: TypeSpecNode[];
  fields?: Record<string, TypeSpecNode>;
  repr?: string;
}

export interface SystemPromptAST {
  tokens: PromptToken[];
  raw_template: string;
  variables: string[];
}

export interface UserPromptAST {
  tokens: PromptToken[];
  raw_template: string;
  variables: string[];
}

export interface GenerateAST {
  target_class: string | null;
  model: string | null;
  temperature: number | null;
  schema: Record<string, TypeSpecNode>;
  json_schema: Record<string, any>;
  options: Record<string, any>;
}

export interface AIPScriptAST {
  system_prompt: SystemPromptAST | null;
  user_prompt: UserPromptAST | null;
  generate: GenerateAST | null;
  variables: string[];
}
