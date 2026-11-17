// 医药赛道研究库 · AI gateway
// One request handler that runs on Cloudflare Workers (worker.js) or plain Node (server.mjs).
// It keeps the API keys server-side and exposes four routes to the static site:
//   GET  /health   which features are configured (no secrets)
//   POST /chat     one model turn: {system, messages, tools} -> {message:{content, tool_calls, raw}}
//   POST /search   web search: {query} -> {results:[{title,url,snippet,date}]}
//   POST /fetch    read a web page as text: {url} -> {url,title,text}
// Environment variables are documented in .env.example.

const JSON_HEADERS = { 'content-type': 'application/json; charset=utf-8' };

export async function handle(request, env) {
  const origin = request.headers.get('origin') || '';
  const cors = corsHeaders(origin, env);
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, '') || '/';
  try {
    if (cors === null) return json({ error: 'origin_not_allowed' }, 403, {});
    if (path === '/health' && request.method === 'GET') {
      return json({
        ok: true,
        ai: Boolean(env.LLM_API_KEY),
        provider: env.LLM_PROVIDER || 'openai',
        model: modelName(env),
        search: Boolean(env.SEARCH_API_KEY && env.SEARCH_PROVIDER),
        fetch: true,
        access_code_required: Boolean(env.ACCESS_CODE),
      }, 200, cors);
    }
    if (request.method !== 'POST') return json({ error: 'not_found' }, 404, cors);
    if (env.ACCESS_CODE && request.headers.get('x-access-code') !== env.ACCESS_CODE) {
      return json({ error: 'bad_access_code', message: '访问码不正确' }, 401, cors);
    }
    const body = await request.json().catch(() => ({}));
    if (path === '/chat') return json(await chat(body, env), 200, cors);
    if (path === '/search') return json(await search(body, env), 200, cors);
    if (path === '/fetch') return json(await readPage(body), 200, cors);
    return json({ error: 'not_found' }, 404, cors);
  } catch (e) {
    const status = e.status || 500;
    return json({ error: e.code || 'gateway_error', message: String(e.message || e).slice(0, 500) }, status, cors || {});
  }
}

function corsHeaders(origin, env) {
  const allowed = String(env.ALLOWED_ORIGINS || '*').split(',').map(s => s.trim()).filter(Boolean);
  const ok = allowed.includes('*') || !origin || allowed.includes(origin);
  if (!ok) return null;
  return {
    'access-control-allow-origin': allowed.includes('*') ? '*' : origin,
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    'access-control-allow-headers': 'content-type,x-access-code',
    'access-control-max-age': '86400',
    vary: 'origin',
  };
}

function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...JSON_HEADERS, ...headers } });
}

function fail(message, status = 502, code = 'upstream_error') {
  const e = new Error(message); e.status = status; e.code = code; return e;
}

function modelName(env) {
  if (env.LLM_MODEL) return env.LLM_MODEL;
  return (env.LLM_PROVIDER || 'openai') === 'anthropic' ? 'claude-opus-5-5' : 'deepseek-chat';
}

async function fetchWithTimeout(resource, init = {}, ms = 120000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(resource, { ...init, signal: ctl.signal }); }
  catch (e) { throw fail(e.name === 'AbortError' ? '上游请求超时' : '无法连接上游服务 ' + e.message, 504); }
  finally { clearTimeout(t); }
}

// ---------------- chat ----------------
// Neutral message format used by the site:
//   {role:'user', content}
//   {role:'assistant', content, tool_calls:[{id,name,arguments}], raw?}   raw = provider-native content, replayed unchanged
//   {role:'tool', tool_call_id, name, content}
async function chat(body, env) {
  if (!env.LLM_API_KEY) throw fail('网关未配置模型 API Key', 503, 'ai_not_configured');
  const system = String(body.system || '');
  const messages = Array.isArray(body.messages) ? body.messages.slice(-40) : [];
  const tools = Array.isArray(body.tools) ? body.tools.slice(0, 32) : [];
  if (!messages.length) throw fail('messages 为空', 400, 'bad_request');
  return (env.LLM_PROVIDER || 'openai') === 'anthropic'
    ? chatAnthropic(system, messages, tools, env)
    : chatOpenAI(system, messages, tools, env);
}

async function chatOpenAI(system, messages, tools, env) {
  const base = String(env.LLM_BASE_URL || 'https://api.deepseek.com').replace(/\/+$/, '');
  const msgs = [{ role: 'system', content: system }];
  for (const m of messages) {
    if (m.role === 'tool') msgs.push({ role: 'tool', tool_call_id: m.tool_call_id, content: String(m.content ?? '') });
    else if (m.role === 'assistant') {
      const out = { role: 'assistant', content: m.content || '' };
      if (m.tool_calls?.length) out.tool_calls = m.tool_calls.map(c => ({ id: c.id, type: 'function', function: { name: c.name, arguments: JSON.stringify(c.arguments ?? {}) } }));
      msgs.push(out);
    } else msgs.push({ role: 'user', content: String(m.content ?? '') });
  }
  const payload = { model: modelName(env), messages: msgs };
  if (tools.length) payload.tools = tools.map(t => ({ type: 'function', function: { name: t.name, description: t.description, parameters: t.parameters || { type: 'object', properties: {} } } }));
  if (env.LLM_MAX_TOKENS) payload.max_tokens = Number(env.LLM_MAX_TOKENS);
  const r = await fetchWithTimeout(base + '/chat/completions', {
    method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer ' + env.LLM_API_KEY }, body: JSON.stringify(payload),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw fail(`模型服务返回 ${r.status} ${data?.error?.message || ''}`.trim(), r.status === 429 ? 429 : 502, r.status === 429 ? 'rate_limited' : 'upstream_error');
  const msg = data.choices?.[0]?.message || {};
  const calls = (msg.tool_calls || []).map(c => ({ id: c.id, name: c.function?.name, arguments: safeJSON(c.function?.arguments) }));
  return { message: { role: 'assistant', content: msg.content || '', tool_calls: calls }, finish_reason: data.choices?.[0]?.finish_reason || null, model: data.model || payload.model };
}

// Claude through the Anthropic Messages API (raw HTTP: Workers have no Python/Node SDK runtime guarantees).
async function chatAnthropic(system, messages, tools, env) {
  const base = String(env.LLM_BASE_URL || 'https://api.anthropic.com').replace(/\/+$/, '');
  const msgs = [];
  for (const m of messages) {
    if (m.role === 'tool') {
      const block = { type: 'tool_result', tool_use_id: m.tool_call_id, content: String(m.content ?? '') };
      const last = msgs[msgs.length - 1];
      // all results for one assistant turn go back in a single user message
      if (last && last.role === 'user' && Array.isArray(last.content) && last.content.every(b => b.type === 'tool_result')) last.content.push(block);
      else msgs.push({ role: 'user', content: [block] });
    } else if (m.role === 'assistant') {
      if (Array.isArray(m.raw) && m.raw.length) msgs.push({ role: 'assistant', content: m.raw }); // replay unchanged (keeps thinking blocks valid)
      else {
        const content = [];
        if (m.content) content.push({ type: 'text', text: m.content });
        for (const c of m.tool_calls || []) content.push({ type: 'tool_use', id: c.id, name: c.name, input: c.arguments ?? {} });
        msgs.push({ role: 'assistant', content: content.length ? content : [{ type: 'text', text: ' ' }] });
      }
    } else msgs.push({ role: 'user', content: String(m.content ?? '') });
  }
  const payload = {
    model: modelName(env),
    max_tokens: Number(env.LLM_MAX_TOKENS || 16000),
    system,
    messages: msgs,
    output_config: { effort: env.LLM_EFFORT || 'medium' },
    fallbacks: 'default',
  };
  if (tools.length) payload.tools = tools.map(t => ({ name: t.name, description: t.description, input_schema: t.parameters || { type: 'object', properties: {} } }));
  const r = await fetchWithTimeout(base + '/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': env.LLM_API_KEY,
      'anthropic-version': '2023-06-01',
      'anthropic-beta': 'server-side-fallback-2026-07-01',
    },
    body: JSON.stringify(payload),
  }, 300000);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw fail(`模型服务返回 ${r.status} ${data?.error?.message || ''}`.trim(), r.status === 429 ? 429 : 502, r.status === 429 ? 'rate_limited' : 'upstream_error');
  if (data.stop_reason === 'refusal') {
    return { message: { role: 'assistant', content: '这个问题模型无法回答，请换一种问法。', tool_calls: [] }, finish_reason: 'refusal', model: data.model };
  }
  const content = data.content || [];
  const text = content.filter(b => b.type === 'text').map(b => b.text).join('');
  const calls = content.filter(b => b.type === 'tool_use').map(b => ({ id: b.id, name: b.name, arguments: b.input || {} }));
  return { message: { role: 'assistant', content: text, tool_calls: calls, raw: content }, finish_reason: data.stop_reason, model: data.model };
}

function safeJSON(s) {
  if (s && typeof s === 'object') return s;
  try { return JSON.parse(s || '{}'); } catch { return {}; }
}

// ---------------- search ----------------
async function search(body, env) {
  const query = String(body.query || '').trim().slice(0, 300);
  if (!query) throw fail('缺少搜索关键词', 400, 'bad_request');
  if (!env.SEARCH_API_KEY || !env.SEARCH_PROVIDER) throw fail('网关未配置搜索服务', 503, 'search_not_configured');
  const n = Math.min(10, Number(body.count) || 8);
  if (env.SEARCH_PROVIDER === 'tavily') {
    const r = await fetchWithTimeout('https://api.tavily.com/search', {
      method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer ' + env.SEARCH_API_KEY },
      body: JSON.stringify({ query, max_results: n, search_depth: 'basic', include_answer: false }),
    }, 30000);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw fail('搜索服务返回 ' + r.status);
    return { provider: 'tavily', results: (d.results || []).map(x => ({ title: x.title, url: x.url, snippet: (x.content || '').slice(0, 600), date: x.published_date || '' })) };
  }
  if (env.SEARCH_PROVIDER === 'bocha') {
    const r = await fetchWithTimeout('https://api.bochaai.com/v1/web-search', {
      method: 'POST', headers: { 'content-type': 'application/json', authorization: 'Bearer ' + env.SEARCH_API_KEY },
      body: JSON.stringify({ query, count: n, summary: true }),
    }, 30000);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw fail('搜索服务返回 ' + r.status);
    const items = d?.data?.webPages?.value || [];
    return { provider: 'bocha', results: items.map(x => ({ title: x.name, url: x.url, snippet: (x.summary || x.snippet || '').slice(0, 600), date: x.datePublished || x.dateLastCrawled || '' })) };
  }
  throw fail('不支持的搜索服务 ' + env.SEARCH_PROVIDER, 400, 'bad_request');
}

// ---------------- read a page ----------------
const PRIVATE_HOST = /^(localhost|.*\.local|.*\.internal|.*\.lan|0\.0\.0\.0|127\.\d+\.\d+\.\d+|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|169\.254\.\d+\.\d+|\[?::1\]?|\[?f[cd][0-9a-f]{2}:.*)$/i;
async function readPage(body) {
  let u;
  try { u = new URL(String(body.url || '')); } catch { throw fail('链接无效', 400, 'bad_request'); }
  if (!/^https?:$/.test(u.protocol) || PRIVATE_HOST.test(u.hostname)) throw fail('只能读取公网 http 或 https 页面', 400, 'bad_request');
  const r = await fetchWithTimeout(u.toString(), { headers: { 'user-agent': 'Mozilla/5.0 (compatible; research-reader/1.0)', accept: 'text/html,text/plain,application/json;q=0.9,*/*;q=0.5' }, redirect: 'follow' }, 20000);
  if (!r.ok) throw fail('页面返回 ' + r.status);
  const type = r.headers.get('content-type') || '';
  if (!/text|json|xml/.test(type)) throw fail('不是文本页面 ' + type, 415, 'unsupported');
  const raw = (await r.text()).slice(0, 2_000_000);
  const title = (raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || '';
  const text = raw
    .replace(/<(script|style|noscript|svg|nav|footer|header)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<br\s*\/?>|<\/(p|div|li|h\d|tr)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[ \t\r\f\v]+/g, ' ').replace(/\n\s*\n+/g, '\n').trim();
  return { url: u.toString(), title: decodeEntities(title.trim()), text: text.slice(0, 16000), truncated: text.length > 16000 };
}
function decodeEntities(s) { return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'"); }
