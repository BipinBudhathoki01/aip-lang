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
  {
    id: "openai-summary",
    name: "OpenAI summary",
    description: "Summary contract using openai",
    defaultVariables: { message: "I cannot access my account and need help today." },
    code: `system:
    Summarize support messages accurately and briefly.
user:
    Message: {{ $message }}
generate as Summary {
    provider: "openai",
    model: "gpt-5-mini",
    max_tokens: 8192,
    schema: { summary: string, urgent: bool }
}
`,
  },
  {
    id: "claude-summary",
    name: "Claude summary",
    description: "Summary contract using anthropic",
    defaultVariables: { message: "I cannot access my account and need help today." },
    code: `system:
    Summarize support messages accurately and briefly.
user:
    Message: {{ $message }}
generate as Summary {
    provider: "anthropic",
    model: "claude-sonnet-4-6",
    max_tokens: 4096,
    schema: { summary: string, urgent: bool }
}
`,
  },
  {
    id: "groq-summary",
    name: "Groq summary",
    description: "Summary contract using groq",
    defaultVariables: { message: "I cannot access my account and need help today." },
    code: `system:
    Summarize support messages accurately and briefly.
user:
    Message: {{ $message }}
generate as Summary {
    provider: "groq",
    model: "openai/gpt-oss-20b",
    max_tokens: 1024,
    schema: { summary: string, urgent: bool }
}
`,
  },
  {
    id: "ollama-summary",
    name: "Ollama local summary",
    description: "Summary contract using ollama",
    defaultVariables: { message: "I cannot access my account and need help today." },
    code: `system:
    Summarize support messages accurately and briefly.
user:
    Message: {{ $message }}
generate as Summary {
    provider: "ollama",
    model: "llama3.2",
    max_tokens: 1024,
    temperature: 0.2,
    schema: { summary: string, urgent: bool }
}
`,
  },
  {
    id: "invoice-extraction",
    name: "Invoice extraction",
    description: "Extract a nested vendor and line items from synthetic invoice text",
    defaultVariables: {"invoice_text": "DEMONSTRATION INVOICE — SYNTHETIC DATA\nInvoice: DEMO-001\nIssued: 2026-01-15\nVendor: Example Office Supplies\nAddress: 10 Example Street\nCurrency: USD\nItems:\nNotebook | Quantity: 2 | Unit price: 12.50\nTotal: 25.00 USD"},
    code: `system:
    Extract an invoice into the declared schema. Use only information present in
    the input. Preserve the currency code and line item values. Do not invent
    vendors or amounts. This example uses synthetic demonstration data.
user:
    Invoice text:
    {{ $invoice_text }}
generate as InvoiceResult {
    model: "gemini-3.8-flash",
    temperature: 0.1,
    schema: {
        invoice_number: string,
        issued_on: string,
        currency: string,
        vendor: { name: string, address: string },
        items: list[{ description: string, quantity: int, unit_price: float }],
        total: float
    }
}
`,
  },
];
