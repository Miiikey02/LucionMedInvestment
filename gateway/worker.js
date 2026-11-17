// Cloudflare Workers entry. Deploy with `npx wrangler deploy` from this folder.
// Set secrets with `npx wrangler secret put LLM_API_KEY` (and SEARCH_API_KEY, ACCESS_CODE).
import { handle } from './gateway.mjs';

export default {
  fetch(request, env) {
    return handle(request, env);
  },
};
