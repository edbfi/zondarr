/**
 * Zod validation schemas for server forms.
 *
 * Provides client-side validation matching backend constraints for:
 * - Creating new media servers
 *
 * @module $lib/schemas/media-server
 */

import { z } from 'zod';
import { getAllProviders } from '$lib/stores/providers.svelte';

/**
 * Schema for creating a new media server.
 *
 * Required fields:
 * - name: Human-readable name for the server
 * - server_type: Type of media server (as registered by a provider)
 * - url: Base URL for the media server API (required unless use_env_credentials is true)
 * - api_key: Authentication token for the server (required unless use_env_credentials is true)
 * - use_env_credentials: Whether to use server-side env var credentials
 */
export const createServerSchema = z
	.object({
		name: z.string().min(1, 'Name is required').max(255, 'Name must be at most 255 characters'),
		server_type: z
			.string()
			.min(1, 'Server type is required')
			.refine((val) => getAllProviders().some((p) => p.server_type === val), 'Invalid server type'),
		url: z.string().max(2048, 'URL must be at most 2048 characters').optional().default(''),
		api_key: z.string().max(512, 'API key must be at most 512 characters').default(''),
		use_env_credentials: z.boolean().default(false)
	})
	.refine((d) => d.use_env_credentials || d.url.length >= 1, {
		message: 'URL is required',
		path: ['url']
	})
	.refine(
		(d) => d.use_env_credentials || d.url.length === 0 || z.string().url().safeParse(d.url).success,
		{
			message: 'Must be a valid URL',
			path: ['url']
		}
	)
	.refine((d) => d.use_env_credentials || d.api_key.length >= 1, {
		message: 'API key is required',
		path: ['api_key']
	});

export type CreateServerInput = z.input<typeof createServerSchema>;

/**
 * Transform form data to API request format.
 *
 * When use_env_credentials is true, sends that flag and omits api_key.
 * Otherwise sends api_key as before.
 */
export function transformCreateServerData(data: CreateServerInput) {
	const base = {
		name: data.name.trim(),
		server_type: data.server_type
	};

	if (data.use_env_credentials) {
		return { ...base, use_env_credentials: true };
	}

	return { ...base, url: (data.url ?? '').trim(), api_key: (data.api_key ?? '').trim() };
}
