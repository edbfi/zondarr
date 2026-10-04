/**
 * Type-safe API client using openapi-fetch.
 *
 * Provides typed wrapper functions for all backend endpoints with
 * automatic base URL configuration from environment variables.
 *
 * @module $lib/api/client
 */

import createClient, { type Client } from 'openapi-fetch';
import * as env from '$app/env/public';
import { showApiError, showNetworkError } from '$lib/utils/toast';
import type { components, paths } from './types';

/** Type alias for a typed openapi-fetch client instance. */
export type ApiClient = Client<paths>;

// Base URL from environment variable, defaults to empty string for same-origin
const API_BASE_URL = env.PUBLIC_API_URL ?? '';

/**
 * Type-safe API client instance.
 * Use this directly for custom requests or use the typed wrapper functions below.
 */
export const api = createClient<paths>({
	baseUrl: API_BASE_URL,
	credentials: 'include'
});

// Auth endpoints that should not trigger a refresh attempt
const AUTH_ENDPOINTS = ['/api/auth/refresh', '/api/auth/login', '/api/auth/setup'];

// Module-level promise to serialize concurrent refresh attempts
let refreshPromise: Promise<boolean> | null = null;

async function attemptTokenRefresh(): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
			method: 'POST',
			credentials: 'include'
		});
		return response.ok;
	} catch {
		return false;
	}
}

// Store request clones for retry after token refresh (keyed by original request).
// Cloning in onRequest preserves the body before fetch() consumes it.
const requestClones = new Map<Request, Request>();

// Auto-refresh on 401 responses (client-side only).
// Skipped for SSR and when already on public auth pages to avoid redirect loops.
api.use({
	onRequest({ request }) {
		requestClones.set(request, request.clone());
		return undefined;
	},
	async onResponse({ request, response }) {
		const requestClone = requestClones.get(request);
		requestClones.delete(request);

		if (
			response.status !== 401 ||
			typeof window === 'undefined' ||
			window.location.pathname.startsWith('/login') ||
			window.location.pathname.startsWith('/join') ||
			window.location.pathname.startsWith('/setup')
		) {
			return response;
		}

		// Don't try to refresh for auth endpoints themselves
		const url = new URL(request.url, window.location.origin);
		if (AUTH_ENDPOINTS.some((ep) => url.pathname === ep || url.pathname.startsWith(`${ep}/`))) {
			window.location.href = '/login';
			return response;
		}

		// Serialize concurrent refresh attempts
		if (!refreshPromise) {
			refreshPromise = attemptTokenRefresh().finally(() => {
				refreshPromise = null;
			});
		}

		const refreshed = await refreshPromise;

		if (refreshed && requestClone) {
			// Retry with the cloned request (body stream is still unconsumed)
			return fetch(requestClone);
		}

		window.location.href = '/login';
		return response;
	}
});

/**
 * Create a scoped API client that uses a custom fetch function.
 * Use this in SvelteKit load functions to pass SvelteKit's provided fetch.
 */
export function createScopedClient(customFetch: typeof globalThis.fetch): ApiClient {
	return createClient<paths>({
		baseUrl: API_BASE_URL,
		credentials: 'include',
		fetch: customFetch
	});
}

// =============================================================================
// Type Aliases for convenience
// =============================================================================

export type InvitationResponse = components['schemas']['InvitationResponse'];
export type InvitationDetailResponse = components['schemas']['InvitationDetailResponse'];
export type InvitationListResponse = components['schemas']['InvitationListResponse'];
export type InvitationValidationResponse = components['schemas']['InvitationValidationResponse'];
export type CreateInvitationRequest = components['schemas']['CreateInvitationRequest'];
export type UpdateInvitationRequest = components['schemas']['UpdateInvitationRequest'];

export type UserResponse = components['schemas']['UserResponse'];
export type UserDetailResponse = components['schemas']['UserDetailResponse'];
export type UserListResponse = components['schemas']['UserListResponse'];
export type IdentityResponse = components['schemas']['IdentityResponse'];

export type MediaServerResponse = components['schemas']['MediaServerResponse'];
export type PublicMediaServerResponse = components['schemas']['PublicMediaServerResponse'];
export type MediaServerWithLibrariesResponse =
	components['schemas']['MediaServerWithLibrariesResponse'];
export type LibraryResponse = components['schemas']['LibraryResponse'];

export type SyncRequest = components['schemas']['SyncRequest'];
export type SyncResult = components['schemas']['SyncResult'];

export interface SyncChannelStatus {
	in_progress: boolean;
	last_completed_at?: string | null;
	next_scheduled_at?: string | null;
	circuit_state?: string | null;
	consecutive_failures?: number | null;
	next_retry_at?: string | null;
}

export interface ServerSyncStatus {
	libraries: SyncChannelStatus;
	users: SyncChannelStatus;
}

export interface MediaServerDetailResponse extends MediaServerWithLibrariesResponse {
	sync_status: ServerSyncStatus;
}

export interface LibrarySyncResult {
	server_id: string;
	server_name: string;
	synced_at: string;
	total_libraries: number;
	added_count: number;
	updated_count: number;
	removed_count: number;
}

export type RedeemInvitationRequest = components['schemas']['RedeemInvitationRequest'];
export type RedemptionResponse = components['schemas']['RedemptionResponse'];
export type RedemptionErrorResponse = components['schemas']['RedemptionErrorResponse'];

export type DashboardStatsResponse = components['schemas']['DashboardStatsResponse'];
export type RecentActivityItem = components['schemas']['RecentActivityItem'];

export type LanguageResponse = components['schemas']['LanguageResponse'];

export type OAuthPinResponse = components['schemas']['OAuthPinResponse'];
export type OAuthCheckResponse = components['schemas']['OAuthCheckResponse'];

/** Per-server health status from join health check */
export interface ServerHealthStatus {
	name: string;
	server_type: string;
	reachable: boolean;
}

/** Response from join health check endpoint */
export interface JoinHealthResponse {
	all_reachable: boolean;
	servers: ServerHealthStatus[];
}

// ErrorResponse is manually defined because it's not used directly in endpoint responses
export interface ErrorResponse {
	detail: string;
	error_code: string;
	timestamp: string;
	correlation_id?: string | null;
}

// ValidationErrorResponse is manually defined for consistency
export interface ValidationErrorResponse extends ErrorResponse {
	field_errors: Array<{
		field: string;
		messages: string[];
	}>;
}

// =============================================================================
// Error Handling Wrapper
// =============================================================================

/** Options for the withErrorHandling wrapper */
export interface WithErrorHandlingOptions {
	/** Whether to show error toasts automatically (default: true) */
	showErrorToast?: boolean;
}

/**
 * Wrapper for API calls that handles errors and shows toasts.
 *
 * Automatically displays toast notifications for API errors and network failures.
 * Use this wrapper around API calls to provide consistent error feedback to users.
 *
 * @param apiCall - Function that returns a promise with { data, error } shape
 * @param options - Configuration options
 * @returns The API call result with { data, error } shape
 *
 * @example
 * ```ts
 * const result = await withErrorHandling(() => deleteInvitation(id));
 * if (result.data) {
 *   showSuccess('Invitation deleted');
 * }
 * ```
 */
export async function withErrorHandling<T>(
	apiCall: () => Promise<{ data?: T; error?: unknown }>,
	options?: WithErrorHandlingOptions
): Promise<{ data?: T; error?: unknown }> {
	const { showErrorToast = true } = options ?? {};

	try {
		const result = await apiCall();

		if (result.error && showErrorToast) {
			showApiError(result.error);
		}

		return result;
	} catch (error) {
		if (error instanceof TypeError && error.message.toLowerCase().includes('fetch')) {
			if (showErrorToast) {
				showNetworkError();
			}
		} else if (showErrorToast) {
			showApiError(error);
		}

		return { error };
	}
}

// =============================================================================
// Invitation API Wrappers
// =============================================================================

/** Parameters for listing invitations */
export interface ListInvitationsParams {
	page?: number;
	page_size?: number;
	enabled?: boolean;
	expired?: boolean;
	sort_by?: 'created_at' | 'expires_at' | 'use_count';
	sort_order?: 'asc' | 'desc';
}

/**
 * List invitations with pagination, filtering, and sorting.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns Paginated list of invitations
 */
export async function getInvitations(params: ListInvitationsParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/invitations', { params: { query: cappedParams } });
}

/**
 * Get a single invitation by ID.
 *
 * @param invitationId - UUID of the invitation
 * @returns Invitation detail response
 */
export async function getInvitation(invitationId: string, client: ApiClient = api) {
	return client.GET('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Create a new invitation.
 *
 * @param data - Invitation creation data
 * @returns Created invitation detail response
 */
export async function createInvitation(data: CreateInvitationRequest, client: ApiClient = api) {
	return client.POST('/api/v1/invitations', { body: data });
}

/**
 * Update an existing invitation.
 *
 * @param invitationId - UUID of the invitation to update
 * @param data - Fields to update
 * @returns Updated invitation detail response
 */
export async function updateInvitation(
	invitationId: string,
	data: UpdateInvitationRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } },
		body: data
	});
}

/**
 * Delete an invitation.
 *
 * @param invitationId - UUID of the invitation to delete
 * @returns Empty response on success
 */
export async function deleteInvitation(invitationId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Validate an invitation code without redeeming it.
 *
 * @param code - Invitation code to validate
 * @returns Validation response with target servers if valid
 */
export async function validateInvitation(code: string, client: ApiClient = api) {
	return client.GET('/api/v1/invitations/validate/{code}', {
		params: { path: { code } }
	});
}

// =============================================================================
// User API Wrappers
// =============================================================================

/** Parameters for listing users */
export interface ListUsersParams {
	page?: number;
	page_size?: number;
	server_id?: string;
	invitation_id?: string;
	enabled?: boolean;
	expired?: boolean;
	search?: string;
	sort_by?: 'created_at' | 'username' | 'expires_at';
	sort_order?: 'asc' | 'desc';
}

/**
 * List users with pagination, filtering, and sorting.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns Paginated list of users with relationships
 */
export async function getUsers(params: ListUsersParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/users', { params: { query: cappedParams } });
}

/**
 * Get a single user by ID.
 *
 * @param userId - UUID of the user
 * @returns User detail response with relationships
 */
export async function getUser(userId: string, client: ApiClient = api) {
	return client.GET('/api/v1/users/{user_id}', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Enable a user account.
 *
 * @param userId - UUID of the user to enable
 * @returns Updated user detail response
 */
export async function enableUser(userId: string, client: ApiClient = api) {
	return client.POST('/api/v1/users/{user_id}/enable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Disable a user account.
 *
 * @param userId - UUID of the user to disable
 * @returns Updated user detail response
 */
export async function disableUser(userId: string, client: ApiClient = api) {
	return client.POST('/api/v1/users/{user_id}/disable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Delete a user account.
 *
 * @param userId - UUID of the user to delete
 * @returns Empty response on success
 */
export async function deleteUser(userId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/users/{user_id}', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Remove shared library access without removing the friend relationship.
 *
 * @param userId - UUID of the user
 * @returns Updated user detail response
 */
export async function removeSharedAccess(userId: string, client: ApiClient = api) {
	return client.POST('/api/v1/users/{user_id}/remove-shares', {
		params: { path: { user_id: userId } }
	});
}

/** User permissions update request */
export interface UpdateUserPermissions {
	can_download?: boolean;
	can_stream?: boolean;
	can_sync?: boolean;
	can_transcode?: boolean;
}

/**
 * Update user permissions on the media server.
 *
 * @param userId - UUID of the user to update
 * @param permissions - Permission values to update
 * @returns Updated user detail response
 */
export async function updateUserPermissions(
	userId: string,
	permissions: UpdateUserPermissions,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/users/{user_id}/permissions', {
		params: { path: { user_id: userId } },
		body: permissions
	});
}

// =============================================================================
// Server API Wrappers
// =============================================================================

/**
 * List all media servers with their libraries.
 *
 * @param enabled - Optional filter for enabled servers only
 * @returns List of servers with libraries
 */
export async function getServers(enabled?: boolean, client: ApiClient = api) {
	return client.GET('/api/v1/servers', {
		params: { query: enabled !== undefined ? { enabled } : {} }
	});
}

/**
 * Sync users between local database and media server.
 *
 * @param serverId - UUID of the server to sync
 * @param dryRun - If true, only report discrepancies without making changes
 * @returns Sync result with discrepancy report
 */
export async function syncServer(serverId: string, dryRun = false, client: ApiClient = api) {
	return client.POST('/api/v1/servers/{server_id}/sync', {
		params: { path: { server_id: serverId } },
		body: { dry_run: dryRun }
	});
}

/**
 * Sync libraries between local database and media server.
 *
 * @param serverId - UUID of the server to sync
 * @returns Library sync result with change counts
 */
export async function syncServerLibraries(
	serverId: string,
	client: ApiClient = api
): Promise<{ data?: LibrarySyncResult; error?: unknown }> {
	const untypedClient = client as unknown as {
		POST: (
			path: string,
			init?: { params?: { path?: { server_id: string } } }
		) => Promise<{ data?: LibrarySyncResult; error?: unknown }>;
	};
	return untypedClient.POST('/api/v1/servers/{server_id}/sync-libraries', {
		params: { path: { server_id: serverId } }
	});
}

/**
 * Reset the circuit breaker for a media server's sync channels.
 *
 * @param serverId - UUID of the server
 * @returns Empty response on success
 */
export async function resetCircuitBreaker(
	serverId: string,
	client: ApiClient = api
): Promise<{ data?: unknown; error?: unknown }> {
	const untypedClient = client as unknown as {
		POST: (
			path: string,
			init?: { params?: { path?: { server_id: string } } }
		) => Promise<{ data?: unknown; error?: unknown }>;
	};
	return untypedClient.POST('/api/v1/servers/{server_id}/reset-circuit', {
		params: { path: { server_id: serverId } }
	});
}

/** Create server request */
export interface CreateServerRequest {
	name: string;
	server_type: string;
	url?: string | null;
	api_key?: string;
	use_env_credentials?: boolean;
}

/**
 * Create a new media server.
 *
 * @param data - Server creation data
 * @returns Created media server response
 */
export async function createServer(data: CreateServerRequest, client: ApiClient = api) {
	return client.POST('/api/v1/servers', { body: data as never });
}

/**
 * Get a single media server by ID.
 *
 * @param serverId - UUID of the server
 * @returns Media server detail response
 */
export async function getServer(
	serverId: string,
	client: ApiClient = api
): Promise<{ data?: MediaServerDetailResponse; error?: unknown; response?: Response }> {
	const untypedClient = client as unknown as {
		GET: (
			path: string,
			init?: { params?: { path?: { server_id: string } } }
		) => Promise<{
			data?: MediaServerDetailResponse;
			error?: unknown;
			response?: Response;
		}>;
	};
	return untypedClient.GET('/api/v1/servers/{server_id}', {
		params: { path: { server_id: serverId } }
	});
}

// Override generated type to support use_env_credentials flow
export interface ConnectionTestRequest {
	url?: string | null;
	api_key?: string | null;
	server_type?: string | null;
	use_env_credentials?: boolean;
}
export type ConnectionTestResponse = components['schemas']['ConnectionTestResponse'];

// Env credentials types — manually defined since the endpoint is new
// and types may not yet be regenerated
export interface EnvCredentialResponse {
	server_type: string;
	display_name: string;
	has_url: boolean;
	has_api_key: boolean;
}

export interface EnvCredentialsResponse {
	credentials: EnvCredentialResponse[];
}

/**
 * Test a media server connection and optionally auto-detect server type.
 *
 * @param data - Connection test data (url, api_key, optional server_type)
 * @returns Connection test response
 */
export async function testConnection(data: ConnectionTestRequest, client: ApiClient = api) {
	return client.POST('/api/v1/servers/test-connection', { body: data as never });
}

/**
 * Get detected environment variable credentials for media server providers.
 *
 * @returns Env credentials response with detected providers
 */
export async function getEnvCredentials(
	client: ApiClient = api
): Promise<{ data?: EnvCredentialsResponse; error?: unknown }> {
	return client.GET('/api/v1/servers/env-credentials' as never);
}

/** Per-field credential lock status for a media server. */
export interface CredentialLockStatus {
	url_locked: boolean;
	api_key_locked: boolean;
}

/**
 * Get credential lock status for a media server.
 *
 * @param serverId - UUID of the server
 * @returns Per-field lock status indicating which credentials are env-var-overridden
 */
export async function getCredentialLocks(
	serverId: string,
	client: ApiClient = api
): Promise<{ data?: CredentialLockStatus; error?: unknown }> {
	const untypedClient = client as unknown as {
		GET: (
			path: string,
			init?: { params?: { path?: { server_id: string } } }
		) => Promise<{ data?: CredentialLockStatus; error?: unknown }>;
	};
	return untypedClient.GET('/api/v1/servers/{server_id}/credential-locks', {
		params: { path: { server_id: serverId } }
	});
}

/**
 * Delete a media server.
 *
 * @param serverId - UUID of the server to delete
 * @returns Empty response on success
 */
export async function deleteServer(serverId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/servers/{server_id}', {
		params: { path: { server_id: serverId } }
	});
}

// =============================================================================
// Join Flow API Wrappers
// =============================================================================

/**
 * Redeem an invitation code to create user accounts.
 *
 * @param code - Invitation code to redeem
 * @param data - Registration data (username, password, optional email)
 * @returns Redemption response with created users
 */
export async function redeemInvitation(
	code: string,
	data: RedeemInvitationRequest,
	client: ApiClient = api
) {
	return client.POST('/api/v1/join/{code}', {
		params: { path: { code } },
		body: data
	});
}

/**
 * Check target server health for an invitation code.
 *
 * @param code - Invitation code to check health for
 * @returns Health response with per-server reachability, including HTTP status on error
 */
export async function checkJoinHealth(
	code: string,
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: JoinHealthResponse; error?: unknown; status?: number }> {
	const response = await customFetch(
		`${API_BASE_URL}/api/v1/join/health/${encodeURIComponent(code)}`,
		{
			credentials: 'include'
		}
	);
	if (!response.ok) {
		let error: unknown;
		try {
			error = await response.json();
		} catch {
			error = { detail: response.statusText || 'Request failed' };
		}
		return { error, status: response.status };
	}
	try {
		return { data: (await response.json()) as JoinHealthResponse };
	} catch {
		return { error: { detail: 'Invalid response format' }, status: response.status };
	}
}

// =============================================================================
// OAuth API Wrappers
// =============================================================================

/**
 * Create an OAuth PIN for authentication with a provider.
 *
 * @param provider - Provider type
 * @returns PIN response with auth URL and opaque handle
 */
export async function createOAuthPin(
	provider: string,
	client: ApiClient = api
): Promise<{ data?: OAuthPinResponse; error?: unknown }> {
	return client.POST('/api/v1/join/{provider}/oauth/pin', {
		params: { path: { provider } }
	});
}

/**
 * Check the status of an OAuth PIN.
 *
 * @param provider - Provider type
 * @param handle - Opaque PIN handle from createOAuthPin
 * @returns Check response with authentication status and redemption token
 */
export async function checkOAuthPin(
	provider: string,
	handle: string,
	client: ApiClient = api
): Promise<{ data?: OAuthCheckResponse; error?: unknown }> {
	return client.GET('/api/v1/join/{provider}/oauth/pin/{handle}', {
		params: { path: { provider, handle } }
	});
}

// =============================================================================
// Settings API Wrappers
// =============================================================================

/** CSRF origin response */
export interface CsrfOriginResponse {
	csrf_origin: string | null;
	is_locked: boolean;
	secure_cookies_auto_enabled?: boolean;
}

/**
 * Get the current CSRF origin setting.
 *
 * @returns CSRF origin and locked status
 */
export async function getCsrfOrigin(
	client: ApiClient = api
): Promise<{ data?: CsrfOriginResponse; error?: unknown }> {
	return client.GET('/api/v1/settings/csrf-origin' as never);
}

/**
 * Set the CSRF origin setting.
 *
 * @param data - The origin to set (or null to clear)
 * @returns Updated CSRF origin and locked status
 */
export async function setCsrfOrigin(data: {
	csrf_origin: string | null;
}): Promise<{ data?: CsrfOriginResponse; error?: unknown }> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/csrf-origin`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as CsrfOriginResponse;
	return { data: result };
}

export interface CsrfOriginTestResponse {
	success: boolean;
	message: string;
	request_origin: string | null;
}

/**
 * Test a CSRF origin against the browser's actual Origin header.
 *
 * @param origin - The origin URL to test
 * @returns Test result with success/failure and message
 */
export async function testCsrfOrigin(
	origin: string
): Promise<{ data?: CsrfOriginTestResponse; error?: unknown }> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/csrf-origin/test`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ origin }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as CsrfOriginTestResponse;
	return { data: result };
}

// =============================================================================
// Secure Cookies API Wrappers
// =============================================================================

/** Secure cookies response */
export interface SecureCookiesResponse {
	secure_cookies: boolean;
	is_locked: boolean;
}

/**
 * Get the current secure cookies setting.
 *
 * @returns Secure cookies status and locked status
 */
export async function getSecureCookies(): Promise<{
	data?: SecureCookiesResponse;
	error?: unknown;
}> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/secure-cookies`, {
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as SecureCookiesResponse };
}

/**
 * Set the secure cookies setting.
 *
 * @param value - Whether to enable secure cookies
 * @returns Updated secure cookies status and locked status
 */
export async function setSecureCookies(
	value: boolean
): Promise<{ data?: SecureCookiesResponse; error?: unknown }> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/secure-cookies`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ secure_cookies: value }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as SecureCookiesResponse };
}

// =============================================================================
// Settings Bundle API Wrappers
// =============================================================================

/** A single setting value with lock status */
export interface SettingValue {
	value: string | null;
	is_locked: boolean;
}

/** All application settings bundled */
export interface AllSettingsResponse {
	csrf_origin: SettingValue;
	secure_cookies: SettingValue;
	sync_interval_seconds: SettingValue;
	expiration_check_interval_seconds: SettingValue;
}

/** System information */
export interface AboutResponse {
	app_version: string;
	python_version: string;
	db_engine: string;
	os_info: string;
}

/**
 * Get all application settings with lock status.
 *
 * @param customFetch - Optional fetch function (use SvelteKit's fetch in load functions)
 */
export async function getAllSettings(customFetch: typeof globalThis.fetch = fetch): Promise<{
	data?: AllSettingsResponse;
	error?: unknown;
}> {
	const response = await customFetch(`${API_BASE_URL}/api/v1/settings`, {
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as AllSettingsResponse };
}

/**
 * Update the sync interval setting.
 */
export async function updateSyncInterval(
	value: number
): Promise<{ data?: SettingValue; error?: unknown }> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/sync-interval`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ sync_interval_seconds: value }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as SettingValue };
}

/**
 * Update the expiration check interval setting.
 */
export async function updateExpirationInterval(
	value: number
): Promise<{ data?: SettingValue; error?: unknown }> {
	const response = await fetch(`${API_BASE_URL}/api/v1/settings/expiration-interval`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ expiration_check_interval_seconds: value }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as SettingValue };
}

/**
 * Get system information for the about page.
 *
 * @param customFetch - Optional fetch function (use SvelteKit's fetch in load functions)
 */
export async function getAbout(
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AboutResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/v1/settings/about`, {
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as AboutResponse };
}

// =============================================================================
// Health API Wrappers
// =============================================================================

/**
 * Check the health status of the backend.
 * Note: Uses direct fetch since health endpoint isn't in OpenAPI spec.
 *
 * @returns Health check response
 */
export async function healthCheck(customFetch: typeof globalThis.fetch = fetch) {
	const response = await customFetch(`${API_BASE_URL}/health`);
	return response.json() as Promise<{
		status: string;
		checks: Record<string, boolean>;
	}>;
}

// =============================================================================
// Dashboard API Wrappers
// =============================================================================

/**
 * Get aggregated dashboard statistics.
 *
 * @returns Dashboard stats including counts and recent activity
 */
export async function getDashboardStats(client: ApiClient = api) {
	return client.GET('/api/v1/dashboard/stats');
}

// =============================================================================
// Language API Wrappers
// =============================================================================

/**
 * Get the list of supported ISO 639-1 languages.
 *
 * @returns Sorted list of languages (English first, rest alphabetical by code)
 */
export async function getLanguages(client: ApiClient = api) {
	return client.GET('/api/v1/languages');
}

// =============================================================================
// Wizard Types
// =============================================================================

/** Interaction configuration types (not in OpenAPI spec) */
export interface ClickConfig {
	button_text?: string;
}

export interface TimerConfig {
	duration_seconds: number;
}

export interface TosConfig {
	checkbox_label?: string;
}

export interface TextInputConfig {
	label: string;
	placeholder?: string;
	required?: boolean;
	min_length?: number;
	max_length?: number;
}

export interface QuizConfig {
	question: string;
	options: string[];
	correct_answer_index: number;
}

export type StepConfig = ClickConfig | TimerConfig | TosConfig | TextInputConfig | QuizConfig;

// Translation types — manually defined until types.d.ts is regenerated
export interface TranslationData {
	language_code: string;
	title: string;
	content_markdown: string;
}

export interface TranslationResponse {
	language_code: string;
	title: string;
	content_markdown: string;
}

// Override generated WizardStepResponse to include translation fields
// (types.d.ts hasn't been regenerated yet with primary_language/translations)
export interface WizardStepResponse
	extends Omit<components['schemas']['WizardStepResponse'], 'primary_language' | 'translations'> {
	primary_language: string;
	translations: TranslationResponse[];
}

export type WizardResponse = components['schemas']['WizardResponse'];

export type WizardDetailResponse = Omit<components['schemas']['WizardDetailResponse'], 'steps'> & {
	steps: WizardStepResponse[];
};

export type WizardListResponse = components['schemas']['WizardListResponse'];
export type StepValidationResponse = components['schemas']['StepValidationResponse'];
export type StepValidationRequest = components['schemas']['StepValidationRequest'];
export type StepReorderRequest = components['schemas']['StepReorderRequest'];
export type CreateWizardRequest = components['schemas']['WizardCreate'];
export type UpdateWizardRequest = components['schemas']['WizardUpdate'];

// Override generated step create/update to include translation fields
export interface CreateWizardStepRequest
	extends Omit<components['schemas']['WizardStepCreate'], 'primary_language' | 'translations'> {
	primary_language?: string;
	translations?: TranslationData[];
}

export interface UpdateWizardStepRequest
	extends Omit<components['schemas']['WizardStepUpdate'], 'primary_language' | 'translations'> {
	primary_language?: string | null;
	translations?: TranslationData[] | null;
}

export type StepInteractionResponse = components['schemas']['StepInteractionResponse'];
export type StepInteractionCreate = components['schemas']['StepInteractionCreate'];
export type StepInteractionUpdate = components['schemas']['StepInteractionUpdate'];
export type InteractionResponseData = components['schemas']['InteractionResponseData'];

// =============================================================================
// Wizard API Wrappers
// =============================================================================

/** Parameters for listing wizards */
export interface ListWizardsParams {
	page?: number;
	page_size?: number;
}

/**
 * List wizards with pagination.
 *
 * @param params - Query parameters for pagination
 * @returns Paginated list of wizards
 */
export async function getWizards(params: ListWizardsParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/wizards', { params: { query: cappedParams } });
}

/**
 * Get a single wizard by ID with all its steps.
 *
 * @param wizardId - UUID of the wizard
 * @returns Wizard detail response with steps
 */
export async function getWizard(wizardId: string, client: ApiClient = api) {
	return client.GET('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } }
	});
}

/**
 * Create a new wizard.
 *
 * @param data - Wizard creation data
 * @returns Created wizard response
 */
export async function createWizard(data: CreateWizardRequest, client: ApiClient = api) {
	return client.POST('/api/v1/wizards', { body: data });
}

/**
 * Update an existing wizard.
 *
 * @param wizardId - UUID of the wizard to update
 * @param data - Fields to update
 * @returns Updated wizard response
 */
export async function updateWizard(
	wizardId: string,
	data: UpdateWizardRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } },
		body: data
	});
}

/**
 * Delete a wizard.
 *
 * @param wizardId - UUID of the wizard to delete
 * @returns Empty response on success
 */
export async function deleteWizard(wizardId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } }
	});
}

/**
 * Create a new wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param data - Step creation data
 * @returns Created step response
 */
export async function createStep(
	wizardId: string,
	data: CreateWizardStepRequest,
	client: ApiClient = api
) {
	return client.POST('/api/v1/wizards/{wizard_id}/steps', {
		params: { path: { wizard_id: wizardId } },
		body: { primary_language: 'en', ...data } as never
	});
}

/**
 * Update an existing wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to update
 * @param data - Fields to update
 * @returns Updated step response
 */
export async function updateStep(
	wizardId: string,
	stepId: string,
	data: UpdateWizardStepRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/wizards/{wizard_id}/steps/{step_id}', {
		params: { path: { wizard_id: wizardId, step_id: stepId } },
		body: data as never
	});
}

/**
 * Delete a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to delete
 * @returns Empty response on success
 */
export async function deleteStep(wizardId: string, stepId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/wizards/{wizard_id}/steps/{step_id}', {
		params: { path: { wizard_id: wizardId, step_id: stepId } }
	});
}

/**
 * Reorder a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to reorder
 * @param newOrder - New position for the step
 * @returns Updated step response
 */
export async function reorderStep(
	wizardId: string,
	stepId: string,
	newOrder: number,
	client: ApiClient = api
) {
	return client.POST('/api/v1/wizards/{wizard_id}/steps/{step_id}/reorder', {
		params: { path: { wizard_id: wizardId, step_id: stepId } },
		body: { new_order: newOrder }
	});
}

/**
 * Validate a wizard step completion.
 *
 * @param data - Step validation request
 * @returns Validation response with completion token if valid
 */
export async function validateStep(data: StepValidationRequest, client: ApiClient = api) {
	return client.POST('/api/v1/wizards/validate-step', { body: data });
}

/**
 * Add an interaction to a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step
 * @param data - Interaction creation data
 * @returns Created interaction response
 */
export async function addStepInteraction(
	wizardId: string,
	stepId: string,
	data: StepInteractionCreate,
	client: ApiClient = api
) {
	return client.POST('/api/v1/wizards/{wizard_id}/steps/{step_id}/interactions', {
		params: { path: { wizard_id: wizardId, step_id: stepId } },
		body: data
	});
}

/**
 * Update a step interaction's configuration.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step
 * @param interactionId - UUID of the interaction to update
 * @param data - Fields to update
 * @returns Updated interaction response
 */
export async function updateStepInteraction(
	wizardId: string,
	stepId: string,
	interactionId: string,
	data: StepInteractionUpdate,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/wizards/{wizard_id}/steps/{step_id}/interactions/{interaction_id}', {
		params: {
			path: { wizard_id: wizardId, step_id: stepId, interaction_id: interactionId }
		},
		body: data
	});
}

/**
 * Remove an interaction from a step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step
 * @param interactionId - UUID of the interaction to remove
 * @returns Empty response on success
 */
export async function removeStepInteraction(
	wizardId: string,
	stepId: string,
	interactionId: string,
	client: ApiClient = api
) {
	return client.DELETE(
		'/api/v1/wizards/{wizard_id}/steps/{step_id}/interactions/{interaction_id}',
		{
			params: {
				path: { wizard_id: wizardId, step_id: stepId, interaction_id: interactionId }
			}
		}
	);
}
