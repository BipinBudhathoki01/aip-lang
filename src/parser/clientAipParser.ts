import type {AIPScriptAST, PromptToken, TypeSpecNode, GenerateAST} from '../types/aip';

function diagnostic(source: string, offset: number, message: string): Error {
  const line = source.slice(0, offset).split('\n').length;
  const start = source.lastIndexOf('\n', offset - 1) + 1;
  const column = offset - start + 1;
  const text = source.split('\n')[line - 1] || '';
  return new Error(`${message}\nLine ${line}, column ${column}\n${line} | ${text}\n${' '.repeat(String(line).length + 3 + column - 1)}^`);
}

class ConfigParser {
  private i = 0;
  constructor(private text: string, private source: string, private base: number) {}
  private fail(message: string, at = this.i): never { throw diagnostic(this.source, this.base + at, message); }
  private skip() { while (/[ \t\r\n\f]/.test(this.text[this.i] || '\0')) this.i++; }
  private take(value: string) { this.skip(); if (this.text.startsWith(value, this.i)) { this.i += value.length; return true; } return false; }
  private expect(value: string) { if (!this.take(value)) this.fail(`Expected ${JSON.stringify(value)}.`); }
  private identifier(): string {
    this.skip(); const match = this.text.slice(this.i).match(/^[a-zA-Z_]\w*/);
    if (!match) this.fail('Expected an identifier.');
    this.i += match[0].length; return match[0];
  }
  private fields(): Record<string, TypeSpecNode> {
    this.expect('{'); const fields: Record<string, TypeSpecNode> = Object.create(null);
    if (this.take('}')) return fields;
    while (true) {
      const key = this.identifier(); this.expect(':'); fields[key] = this.type();
      if (this.take('}')) return fields;
      this.expect(','); if (this.take('}')) return fields;
    }
  }
  private type(): TypeSpecNode {
    this.skip(); const at = this.i;
    if (this.text[this.i] === '{') return {kind: 'object', fields: this.fields()};
    const name = this.identifier(); const args: TypeSpecNode[] = [];
    if (this.take('[')) {
      args.push(this.type());
      while (this.take(',')) args.push(this.type());
      this.expect(']');
    }
    const lower = name.toLowerCase();
    const primitive = ['int', 'integer', 'float', 'number', 'str', 'string', 'bool', 'boolean'];
    const required = ['list', 'array'].includes(lower) ? 1 : ['dict', 'map'].includes(lower) ? 2 : 0;
    if (!primitive.includes(lower) && required === 0) this.fail(`Unsupported schema type ${JSON.stringify(name)}.`, at);
    if (args.length !== required) this.fail(`Type ${JSON.stringify(name)} requires ${required} type argument(s).`, at);
    if (required === 2 && !['str', 'string'].includes((args[0].name || '').toLowerCase())) this.fail('Dictionary keys must use string or str.', at);
    return {kind: 'type', name, type_args: args, repr: args.length ? `${name}[${args.map(typeRepr).join(', ')}]` : name};
  }
  private value(): string | number | boolean | Record<string, TypeSpecNode> {
    this.skip();
    if (this.text[this.i] === '{') return this.fields();
    if (this.text[this.i] === '"') {
      const start = this.i++;
      while (this.i < this.text.length) {
        if (this.text[this.i] === '\\') { this.i += 2; continue; }
        if (this.text[this.i++] === '"') {
          try { return JSON.parse(this.text.slice(start, this.i)); } catch { this.fail('Invalid quoted string.', start); }
        }
      }
      this.fail('Unclosed quoted string.', start);
    }
    const bool = this.text.slice(this.i).match(/^(true|false)\b/);
    if (bool) { this.i += bool[0].length; return bool[0] === 'true'; }
    const number = this.text.slice(this.i).match(/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/);
    if (number) { this.i += number[0].length; return Number(number[0]); }
    this.fail('Expected a double-quoted string, number, boolean, or schema object.');
  }
  parse(): GenerateAST {
    if (this.identifier() !== 'generate') this.fail('Expected generate.');
    let target: string | null = null;
    this.skip();
    if (/^as\b/.test(this.text.slice(this.i))) { this.i += 2; target = this.identifier(); }
    this.expect('{');
    const values: Record<string, ReturnType<ConfigParser['value']>> = Object.create(null);
    if (!this.take('}')) {
      while (true) {
        const key = this.identifier(); this.expect(':'); values[key] = this.value();
        if (this.take('}')) break;
        this.expect(','); if (this.take('}')) break;
      }
    }
    this.skip(); if (this.i !== this.text.length) this.fail('Unexpected text after generate block.');
    const model = values.model ?? null;
    const temperature = values.temperature ?? null;
    const schema = values.schema ?? Object.create(null);
    if (model !== null && typeof model !== 'string') this.fail('model must be a quoted string.');
    if (temperature !== null && typeof temperature !== 'number') this.fail('temperature must be a number.');
    if (typeof schema !== 'object' || schema === null) this.fail('schema must be an object of field: type declarations.');
    if (values.provider !== undefined && typeof values.provider !== 'string') this.fail('provider must be a quoted string.');
    const options = Object.fromEntries(Object.entries(values).filter(([key]) => !['model', 'temperature', 'schema'].includes(key)));
    const typedSchema = schema as Record<string, TypeSpecNode>;
    const jsonSchema: Record<string, unknown> = {type: 'object', properties: Object.fromEntries(Object.entries(typedSchema).map(([key, type]) => [key, toSchema(type)])), required: Object.keys(typedSchema)};
    if (target) jsonSchema.title = target;
    return {target_class: target, model: model as string | null, temperature: temperature as number | null, schema: typedSchema, json_schema: jsonSchema, options};
  }
}

function typeRepr(type: TypeSpecNode): string {
  if (type.kind === 'object') return '{' + Object.entries(type.fields || {}).map(([key, value]) => `${key}: ${typeRepr(value)}`).join(', ') + '}';
  return type.repr || type.name || '';
}

function toSchema(type: TypeSpecNode): Record<string, unknown> {
  if (type.kind === 'object') {
    const properties = Object.fromEntries(Object.entries(type.fields || {}).map(([key, value]) => [key, toSchema(value)]));
    return {type: 'object', properties, required: Object.keys(properties)};
  }
  const name = type.name!.toLowerCase();
  if (['list', 'array'].includes(name)) return {type: 'array', items: toSchema(type.type_args![0])};
  if (['dict', 'map'].includes(name)) return {type: 'object', additionalProperties: toSchema(type.type_args![1])};
  return {type: ({int: 'integer', integer: 'integer', float: 'number', number: 'number', str: 'string', string: 'string', bool: 'boolean', boolean: 'boolean'} as Record<string, string>)[name]};
}

export function parseAipClient(source: string): {ast: AIPScriptAST | null; error: string | null} {
  try {
    for (const candidate of source.matchAll(/^[ \t]*generate\s+as\b/gm)) {
      if (!/^generate\s+as\s+[a-zA-Z_]\w*\s*\{/.test(source.slice(candidate.index).trimStart())) throw diagnostic(source, candidate.index!, 'Expected generate as ClassName { ... }.');
    }
    const pattern = /^[ \t]*(system[ \t]*:|user[ \t]*:|generate(?:\s+as\s+[a-zA-Z_]\w*)?\s*\{)/gm;
    const sections = [...source.matchAll(pattern)];
    if (!sections.length || source.slice(0, sections[0].index).trim()) throw diagnostic(source, 0, 'Expected system:, user:, or generate block.');
    const ast: AIPScriptAST = {system_prompt: null, user_prompt: null, generate: null, variables: []};
    for (let index = 0; index < sections.length; index++) {
      const section = sections[index];
      const start = section.index!;
      const end = sections[index + 1]?.index ?? source.length;
      if (section[1].startsWith('generate')) {
        ast.generate = new ConfigParser(source.slice(start, end), source, start).parse();
        continue;
      }
      const contentStart = start + section[0].length;
      const raw = source.slice(contentStart, end);
      if (!raw.length) throw diagnostic(source, contentStart, 'Expected prompt text.');
      const tokens: PromptToken[] = [];
      const variables: string[] = [];
      let cursor = 0;
      while (cursor < raw.length) {
        const next = raw.indexOf('{{', cursor);
        if (next < 0) { tokens.push({type: 'text', text: raw.slice(cursor)}); break; }
        if (next > cursor) tokens.push({type: 'text', text: raw.slice(cursor, next)});
        const match = raw.slice(next).match(/^\{\{\s*\$([a-zA-Z_]\w*)\s*\}\}/);
        if (!match) throw diagnostic(source, contentStart + next, 'Expected a variable such as {{ $name }}.');
        tokens.push({type: 'variable', name: match[1]});
        if (!variables.includes(match[1])) variables.push(match[1]);
        cursor = next + match[0].length;
      }
      const prompt = {tokens, raw_template: raw, variables};
      if (section[1].startsWith('system')) ast.system_prompt = prompt; else ast.user_prompt = prompt;
    }
    ast.variables = [...new Set([...(ast.system_prompt?.variables || []), ...(ast.user_prompt?.variables || [])])];
    return {ast, error: null};
  } catch (error) { return {ast: null, error: error instanceof Error ? error.message : String(error)}; }
}
