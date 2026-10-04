import { timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { isRedirect, redirect } from '@sveltejs/kit';
import * as env from '$app/env/private';
import { getAuthMethods, getMe, type OnboardingStep } from '$lib/api/auth';
import { isNetworkError } from '$lib/api/errors';
import { createValidatedNonce } from '$lib/server/setup-nonce';
import type { PageServerLoad } from './$types';

function readBootstrapToken(): string | null {
	const filePath = env.BOOTSTRAP_TOKEN_FILE;
	if (!filePath) return null;
	try {
		const content = readFileSync(filePath, 'utf-8').trim();
		return content || null;
	} catch {
		return null;
	}
}

function verifyToken(provided: string, expected: string): boolean {
	const a = Buffer.from(provided, 'utf-8');
	const b = Buffer.from(expected, 'utf-8');
	if (a.length !== b.length) return false;
	return timingSafeEqual(a, b);
}

export const load: PageServerLoad = async ({ fetch, cookies, url }) => {
	try {
		const authMethods = await getAuthMethods(fetch);

		if (authMethods.setup_required) {
			const diskToken = readBootstrapToken();
			const urlToken = url.searchParams.get('token');

			// URL token provided — validate and redirect to strip it
			if (urlToken && diskToken) {
				if (verifyToken(urlToken, diskToken)) {
					const nonce = createValidatedNonce();
					cookies.set('zondarr_setup_nonce', nonce, {
						httpOnly: true,
						sameSite: 'strict',
						path: '/',
						maxAge: 600
					});
					redirect(302, '/setup');
				}
				return {
					onboardingStep: 'account' as OnboardingStep,
					tokenAvailable: false,
					tokenError: 'Invalid setup token'
				};
			}

			// No URL token — check for existing nonce cookie (prior validated visit)
			const existingNonce = cookies.get('zondarr_setup_nonce');
			const tokenAvailable = existingNonce !== undefined;

			return {
				onboardingStep: 'account' as OnboardingStep,
				tokenAvailable,
				tokenError: undefined as string | undefined
			};
		}

		if (!authMethods.onboarding_required) {
			redirect(302, '/login');
		}

		const me = await getMe(fetch);
		if (!me) {
			redirect(302, '/login');
		}

		return { onboardingStep: authMethods.onboarding_step };
	} catch (e) {
		if (isRedirect(e)) throw e;
		if (!isNetworkError(e)) {
			console.warn('[setup loader] unexpected error from getAuthMethods:', e);
		}
		// Backend unreachable or broken — render setup page anyway (submission will fail gracefully)
	}

	return { onboardingStep: 'account' as OnboardingStep };
};
