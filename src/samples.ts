export interface SampleScript {
  id: string;
  name: string;
  description: string;
  defaultVariables: Record<string, string>;
  code: string;
}

export const SAMPLES: SampleScript[] = [
  {
    id: 'examiner',
    name: 'Examiner (User Sample)',
    description: 'The exact sample syntax from your prompt with typed AnalysisResult output',
    defaultVariables: {
      name: 'Ada Lovelace',
      text: 'The Analytical Engine weaves algebraic patterns just as the Jacquard loom weaves flowers and leaves.',
    },
    code: `system:
    You are an expert examiner.

user:
    Analyze the following submission by {{ $name }}:
    "{{ $text }}"

generate as AnalysisResult {
    model: "gemini-2.0-flash",
    temperature: 0.2,
    schema: {
        score: int,
        passed: bool,
        notes: list[string]
    }
}`,
  },
  {
    id: 'code-review',
    name: 'Code Reviewer',
    description: 'Automated syntax & security reviewer with typed severity output',
    defaultVariables: {
      language: 'Python',
      code: 'def execute_query(query):\n    return db.cursor().execute("SELECT * FROM users WHERE id = " + query)',
    },
    code: `system:
    You are a senior compiler and security engineer reviewing code submissions.

user:
    Review this {{ $language }} snippet:
    \`\`\`
    {{ $code }}
    \`\`\`

generate as SecurityAudit {
    model: "gemini-2.0-flash",
    temperature: 0.1,
    schema: {
        has_vulnerabilities: bool,
        cwe_category: string,
        risk_level: int,
        recommendations: list[string]
    }
}`,
  },
  {
    id: 'support-triage',
    name: 'Customer Support Triage',
    description: 'Ticket classification and priority estimation DSL script',
    defaultVariables: {
      customer: 'Acme Corp (Enterprise)',
      message: 'Our production database synchronization is failing with timeout 504. Urgent help needed!',
    },
    code: `system:
    You are a customer success operations bot classifying enterprise support inquiries.

user:
    Customer: {{ $customer }}
    Inquiry:
    "{{ $message }}"

generate as TicketResolution {
    model: "gemini-2.0-flash",
    temperature: 0.3,
    schema: {
        priority: int,
        escalate_to_tier3: bool,
        suggested_action: string,
        tags: list[string]
    }
}`,
  },
];
