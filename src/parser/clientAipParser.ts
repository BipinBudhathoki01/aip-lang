import { AIPScriptAST, PromptToken, TypeSpecNode, GenerateAST } from '../types/aip';

export function parseAipClient(source: string): { ast: AIPScriptAST | null; error: string | null } {
  try {
    let systemPromptRaw: string | null = null;
    let userPromptRaw: string | null = null;
    let generateRaw: string | null = null;

    // Match section headers and their full matched length
    const sectionRegex = /(?:^|\n)[ \t]*(system\s*:|user\s*:|generate(?:\s+as\s+[a-zA-Z_]\w*)?\s*\{)/g;
    const matches: { startIndex: number; header: string; fullMatchLen: number }[] = [];
    let m;
    while ((m = sectionRegex.exec(source)) !== null) {
      matches.push({
        startIndex: m.index,
        fullMatchLen: m[0].length,
        header: m[1].trim(),
      });
    }

    if (matches.length === 0) {
      return { ast: null, error: 'No valid sections found. Expected system:, user:, or generate block.' };
    }

    for (let i = 0; i < matches.length; i++) {
      const current = matches[i];
      const startContentIndex = current.startIndex + current.fullMatchLen;
      const endContentIndex = i + 1 < matches.length ? matches[i + 1].startIndex : source.length;
      const blockBody = source.slice(startContentIndex, endContentIndex);

      if (current.header.startsWith('system')) {
        systemPromptRaw = blockBody;
      } else if (current.header.startsWith('user')) {
        userPromptRaw = blockBody;
      } else if (current.header.startsWith('generate')) {
        generateRaw = current.header + blockBody;
      }
    }

    // Parse tokens for prompts: text chunks and {{ $var }}
    function tokenizePrompt(raw: string | null): { tokens: PromptToken[]; rawTemplate: string; vars: string[] } | null {
      if (raw === null) return null;
      const tokens: PromptToken[] = [];
      const varRegex = /\{\{\s*\$([a-zA-Z_]\w*)\s*\}\}/g;
      let lastIndex = 0;
      let match;
      const vars: string[] = [];

      while ((match = varRegex.exec(raw)) !== null) {
        if (match.index > lastIndex) {
          tokens.push({ type: 'text', text: raw.slice(lastIndex, match.index) });
        }
        const varName = match[1];
        tokens.push({ type: 'variable', name: varName });
        if (!vars.includes(varName)) vars.push(varName);
        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < raw.length) {
        tokens.push({ type: 'text', text: raw.slice(lastIndex) });
      }

      return {
        tokens,
        rawTemplate: raw,
        vars,
      };
    }

    const systemParsed = tokenizePrompt(systemPromptRaw);
    const userParsed = tokenizePrompt(userPromptRaw);

    // Parse generate block
    let generateAST: GenerateAST | null = null;
    if (generateRaw) {
      const headerMatch = generateRaw.match(/generate(?:\s+as\s+([a-zA-Z_]\w*))?\s*\{([\s\S]*)\}/);
      if (headerMatch) {
        const targetClass = headerMatch[1] || null;
        const innerContent = headerMatch[2];

        let model: string | null = null;
        let temperature: number | null = null;
        const schema: Record<string, TypeSpecNode> = {};
        const options: Record<string, any> = {};
        const providerMatch = innerContent.match(/provider\s*:\s*["']([^"']+)["']/);
        if (providerMatch) options.provider = providerMatch[1];
        const maxTokensMatch = innerContent.match(/max_tokens\s*:\s*(\d+)/);
        if (maxTokensMatch) options.max_tokens = Number(maxTokensMatch[1]);

        // Extract model
        const modelMatch = innerContent.match(/model\s*:\s*["']([^"']+)["']/);
        if (modelMatch) model = modelMatch[1];

        // Extract temperature
        const tempMatch = innerContent.match(/temperature\s*:\s*([0-9.]+)/);
        if (tempMatch) temperature = parseFloat(tempMatch[1]);

        // Extract schema block
        const schemaStart = innerContent.match(/schema\s*:\s*\{/);
        const schemaMatch = schemaStart ? [null, balancedBody(innerContent, schemaStart.index! + schemaStart[0].length - 1)] : null;
        if (schemaMatch) {
          const schemaFieldsStr = schemaMatch[1];
          const fieldLines = splitTopLevel(schemaFieldsStr!);
          for (const line of fieldLines) {
            const parts = line.split(':').map((s) => s.trim());
            if (parts.length >= 2 && parts[0]) {
              const fieldName = parts[0].replace(/[^a-zA-Z0-9_]/g, '');
              const typeStr = parts.slice(1).join(':').trim();
              if (fieldName && typeStr) {
                schema[fieldName] = parseTypeSpec(typeStr);
              }
            }
          }
        }

        // Generate JSON schema
        const jsonSchema = generateJsonSchema(targetClass, schema);

        generateAST = {
          target_class: targetClass,
          model,
          temperature,
          schema,
          json_schema: jsonSchema,
          options,
        };
      }
    }

    const allVars = Array.from(new Set([...(systemParsed?.vars || []), ...(userParsed?.vars || [])]));

    const ast: AIPScriptAST = {
      system_prompt: systemParsed
        ? {
            tokens: systemParsed.tokens,
            raw_template: systemParsed.rawTemplate,
            variables: systemParsed.vars,
          }
        : null,
      user_prompt: userParsed
        ? {
            tokens: userParsed.tokens,
            raw_template: userParsed.rawTemplate,
            variables: userParsed.vars,
          }
        : null,
      generate: generateAST,
      variables: allVars,
    };

    return { ast, error: null };
  } catch (err: any) {
    return { ast: null, error: err.message || 'Parsing error' };
  }
}

function parseTypeSpec(typeStr: string): TypeSpecNode {
  typeStr = typeStr.trim();
  if (typeStr.startsWith('{') && typeStr.endsWith('}')) {
    const fields: Record<string, TypeSpecNode> = {};
    for (const field of splitTopLevel(typeStr.slice(1, -1))) {
      const colon = field.indexOf(':');
      if (colon < 0) throw new Error('Expected field: type in object schema.');
      fields[field.slice(0, colon).trim()] = parseTypeSpec(field.slice(colon + 1));
    }
    return { kind: 'object', fields };
  }
  const genericMatch = typeStr.match(/^([a-zA-Z_]\w*)\[(.*)\]$/);
  if (genericMatch) {
    const baseName = genericMatch[1];
    const argsStr = genericMatch[2];
    const args = splitTopLevel(argsStr).map((s) => parseTypeSpec(s.trim()));
    return {
      kind: 'type',
      name: baseName,
      type_args: args,
      repr: `${baseName}[${args.map((a) => a.repr || a.name).join(', ')}]`,
    };
  }
  return {
    kind: 'type',
    name: typeStr,
    type_args: [],
    repr: typeStr,
  };
}

function typeSpecToJsonSchema(typeNode: TypeSpecNode): Record<string, any> {
  if (typeNode.kind === 'object') {
    const properties = Object.fromEntries(Object.entries(typeNode.fields || {}).map(([key, value]) => [key, typeSpecToJsonSchema(value)]));
    return { type: 'object', properties, required: Object.keys(properties) };
  }
  const primitiveMap: Record<string, string> = {
    int: 'integer',
    integer: 'integer',
    float: 'number',
    number: 'number',
    str: 'string',
    string: 'string',
    bool: 'boolean',
    boolean: 'boolean',
  };

  const name = (typeNode.name || '').toLowerCase();
  if (name === 'dict' || name === 'map') {
    return { type: 'object', additionalProperties: typeNode.type_args?.[1] ? typeSpecToJsonSchema(typeNode.type_args[1]) : {} };
  }
  if (name === 'list' || name === 'array') {
    const itemType = typeNode.type_args?.[0] ? typeSpecToJsonSchema(typeNode.type_args[0]) : {};
    return { type: 'array', items: itemType };
  }

  const mapped = primitiveMap[name];
  if (mapped) {
    return { type: mapped };
  }
  return { type: 'string', description: typeNode.name };
}

function generateJsonSchema(title: string | null, schema: Record<string, TypeSpecNode>): Record<string, any> {
  const properties: Record<string, any> = {};
  for (const [k, v] of Object.entries(schema)) {
    properties[k] = typeSpecToJsonSchema(v);
  }
  const result: Record<string, any> = {
    type: 'object',
    properties,
    required: Object.keys(properties),
  };
  if (title) result.title = title;
  return result;
}

function splitTopLevel(source: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < source.length; i++) {
    if ('[{'.includes(source[i])) depth++;
    if (']}'.includes(source[i])) depth--;
    if (depth < 0) throw new Error('Unbalanced schema brackets.');
    if (source[i] === ',' && depth === 0) { parts.push(source.slice(start, i).trim()); start = i + 1; }
  }
  if (depth !== 0) throw new Error('Unbalanced schema brackets.');
  parts.push(source.slice(start).trim());
  return parts.filter(Boolean);
}

function balancedBody(source: string, start: number): string {
  let depth = 0;
  for (let i = start; i < source.length; i++) {
    if (source[i] === '{') depth++;
    if (source[i] === '}' && --depth === 0) return source.slice(start + 1, i);
  }
  throw new Error('Unclosed schema block.');
}
