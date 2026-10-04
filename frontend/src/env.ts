import { defineEnvVars } from '@sveltejs/kit/env';

/**
 * Every variable is optional: the validator returns the raw value, so an unset
 * variable stays `undefined` (the readers fall back with `??`) and an empty one
 * stays `''`. Without a validator, SvelteKit 3 fails startup when a declared
 * variable is unset.
 */
const optional = (value: string | undefined) => value;

export const variables = defineEnvVars({
	/** Backend URL for SSR requests and the `/api/*` proxy. */
	INTERNAL_API_URL: { schema: optional },
	/** Development-only auth bypass; the backend honours it only with `DEBUG`. */
	DEV_SKIP_AUTH: { schema: optional },
	/** File the backend writes the bootstrap token to, read by the setup flow. */
	BOOTSTRAP_TOKEN_FILE: { schema: optional },
	/** Backend URL the browser calls directly; empty or unset uses the same-origin proxy. */
	PUBLIC_API_URL: { public: true, schema: optional }
});
