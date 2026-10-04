/**
 * Auth API wrappers for /api/auth/* endpoints.
 *
 * Uses raw fetch for auth endpoints that use cookie-based auth.
 * Types are imported from the auto-generated OpenAPI types.
 */

import * as env from '$app/env/public';
import type { components } from './types';

const API_BASE_URL = env.PUBLIC_API_URL ?? '';

// =============================================================================
// Types — re-export from generated OpenAPI types
// =============================================================================

export type AuthFieldInfo = components['schemas']['AuthFieldInfo'];
export type ProviderAuthInfo = Omit<
	components['schemas']['ProviderAuthInfo'],
	'flow_type' | 'fields'
> & {
	/** Narrowed from the generated `string` to known flow types. */
	flow_type: 'oauth' | 'credentials';
	/** Always present (defaults to [] on backend). */
	fields: AuthFieldInfo[];
};
export type AuthMethodsResponse = Omit<
	components['schemas']['AuthMethodsResponse'],
	'provider_auth'
> & {
	provider_auth: ProviderAuthInfo[];
	onboarding_required: boolean;
	onboarding_step: OnboardingStep;
};

export type OnboardingStep = 'account' | 'security' | 'server' | 'complete';

const ONBOARDING_STEPS: readonly OnboardingStep[] = ['account', 'security', 'server', 'complete'];

export function isOnboardingStep(value: unknown): value is OnboardingStep {
	return typeof value === 'string' && (ONBOARDING_STEPS as readonly string[]).includes(value);
}

export interface AdminMeResponse {
	id: string;
	username: string;
	email: string | null;
	auth_method: string;
	totp_enabled: boolean;
	onboarding_required: boolean;
	onboarding_step: OnboardingStep;
}

export interface AuthSuccessResponse {
	success: boolean;
}

export interface LoginResponse {
	totp_required?: boolean;
	challenge_token?: string | null;
}

export interface TotpVerifyResponse {
	success: boolean;
}

export interface OnboardingStatusResponse {
	onboarding_required: boolean;
	onboarding_step: OnboardingStep;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Extract `detail` string from an unknown error response body.
 *
 * Backend error responses are `{ detail: string }`, but the raw-fetch
 * wrappers type errors as `unknown`. This helper narrows safely.
 */
export function getErrorDetail(error: unknown, fallback: string = 'Unknown error'): string {
	if (error != null && typeof error === 'object' && 'detail' in error) {
		const detail = (error as Record<string, unknown>).detail;
		if (typeof detail === 'string') return detail;
	}
	return fallback;
}

// =============================================================================
// API Functions
// =============================================================================

export async function getAuthMethods(
	customFetch: typeof globalThis.fetch = fetch
): Promise<AuthMethodsResponse> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/methods`, {
		credentials: 'include'
	});
	if (!response.ok) {
		throw new Error(`Auth methods request failed (${response.status})`);
	}
	const data: unknown = await response.json();
	if (
		data == null ||
		typeof data !== 'object' ||
		typeof (data as Record<string, unknown>).setup_required !== 'boolean' ||
		typeof (data as Record<string, unknown>).onboarding_required !== 'boolean' ||
		!isOnboardingStep((data as Record<string, unknown>).onboarding_step)
	) {
		throw new Error('Invalid auth methods response');
	}
	return data as AuthMethodsResponse;
}

export async function setupAdmin(
	data: { username: string; password: string; email?: string; bootstrap_token: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthSuccessResponse; error?: unknown }> {
	const response = await customFetch(`/api/auth/setup`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthSuccessResponse;
	return { data: result };
}

export async function loginLocal(
	data: { username: string; password: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: LoginResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as LoginResponse;
	return { data: result };
}

/**
 * Verify a TOTP code during login.
 */
export async function verifyTotp(
	data: { challenge_token: string; code: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: TotpVerifyResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/verify`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as TotpVerifyResponse };
}

/**
 * Verify a backup code during login.
 */
export async function verifyBackupCode(
	data: { challenge_token: string; code: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: TotpVerifyResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/backup-code`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as TotpVerifyResponse };
}

/**
 * Authenticate via an external provider.
 *
 * @param method - Provider method name (e.g., "plex", "jellyfin")
 * @param credentials - Provider-specific credentials
 */
export async function loginExternal(
	method: string,
	credentials: Record<string, string>,
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: LoginResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login/${method}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ credentials }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as LoginResponse;
	return { data: result };
}

export async function logout(customFetch: typeof globalThis.fetch = fetch): Promise<void> {
	await customFetch(`${API_BASE_URL}/api/auth/logout`, {
		method: 'POST',
		credentials: 'include'
	});
}

export async function advanceOnboarding(
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: OnboardingStatusResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/onboarding/advance`, {
		method: 'POST',
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as OnboardingStatusResponse;
	return { data: result };
}

export interface LinkProviderResponse {
	method: string;
	external_id: string;
}

export interface AdminProfileResponse {
	id: string;
	username: string;
	email: string | null;
	auth_method: string;
}

export interface PasswordChangeResponse {
	success: boolean;
	message: string;
}

/**
 * Update admin email address.
 */
export async function updateAdminEmail(
	data: { email: string | null },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AdminProfileResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/me`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as AdminProfileResponse };
}

/**
 * Change admin password.
 */
export async function changePassword(
	data: { current_password: string; new_password: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: PasswordChangeResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/me/change-password`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as PasswordChangeResponse };
}

/**
 * Link an external auth provider to the current admin account.
 */
export async function linkProvider(
	data: { method: string; credentials: Record<string, string> },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: LinkProviderResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/me/link-provider`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as LinkProviderResponse };
}

// =============================================================================
// TOTP 2FA Management
// =============================================================================

export interface TotpSetupResponse {
	provisioning_uri: string;
	qr_code_svg: string;
	backup_codes: string[];
}

export interface TotpVerifySetupResponse {
	backup_codes: string[];
}

export interface TotpBackupCodesResponse {
	backup_codes: string[];
}

/**
 * Initiate TOTP setup — returns secret, provisioning URI, and QR code SVG.
 */
export async function totpSetup(
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: TotpSetupResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/setup`, {
		method: 'POST',
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as TotpSetupResponse };
}

/**
 * Verify TOTP setup with a code from the authenticator app.
 * Returns backup codes on success.
 */
export async function totpVerifySetup(
	data: { code: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: TotpVerifySetupResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/confirm-setup`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as TotpVerifySetupResponse };
}

/**
 * Disable TOTP 2FA. Requires password confirmation.
 */
export async function totpDisable(
	data: { password: string; code: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/disable`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return {};
}

/**
 * Regenerate backup codes. Requires a valid TOTP code.
 */
export async function totpRegenerateBackupCodes(
	data: { code: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: TotpBackupCodesResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/totp/regenerate-backup-codes`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	return { data: (await response.json()) as TotpBackupCodesResponse };
}

export async function getMe(
	customFetch: typeof globalThis.fetch = fetch
): Promise<AdminMeResponse | null> {
	try {
		const response = await customFetch(`${API_BASE_URL}/api/auth/me`, {
			credentials: 'include'
		});
		if (!response.ok) return null;
		return (await response.json()) as AdminMeResponse;
	} catch {
		return null;
	}
}
