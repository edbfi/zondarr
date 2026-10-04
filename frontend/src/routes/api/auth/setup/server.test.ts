import { afterEach, describe, expect, it, vi } from 'vitest';

/* ------------------------------------------------------------------ */
/*  Hoisted mocks — must be declared before any import that uses them */
/* ------------------------------------------------------------------ */

const { privateEnv, publicEnv, mockConsumeNonce, mockReadFileSync } = vi.hoisted(() => ({
	privateEnv: {
		INTERNAL_API_URL: 'http://localhost:8000',
		BOOTSTRAP_TOKEN_FILE: '/run/secrets/bootstrap_token'
	},
	publicEnv: {
		PUBLIC_API_URL: 'http://localhost:8000'
	},
	mockConsumeNonce: vi.fn(),
	mockReadFileSync: vi.fn()
}));

vi.mock('$app/env/private', () => privateEnv);

vi.mock('$app/env/public', () => publicEnv);

vi.mock('node:fs', async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
	return {
		...actual,
		default: { ...actual, readFileSync: mockReadFileSync },
		readFileSync: mockReadFileSync
	};
});

vi.mock('$lib/server/setup-nonce', () => ({
	consumeNonce: mockConsumeNonce
}));

/* ------------------------------------------------------------------ */
/*  Import the handler AFTER mocks are registered                     */
/* ------------------------------------------------------------------ */

import { POST } from './+server';

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function makeRequest(body: Record<string, unknown>, nonceCookie?: string): Request {
	const headers = new Headers({ 'content-type': 'application/json' });
	if (nonceCookie) {
		headers.set('cookie', `zondarr_setup_nonce=${nonceCookie}`);
	}
	return new Request('http://frontend.local/api/auth/setup', {
		method: 'POST',
		headers,
		body: JSON.stringify(body)
	});
}

function makeEvent(body: Record<string, unknown>, nonceCookie?: string) {
	const request = makeRequest(body, nonceCookie);
	return {
		request,
		cookies: {
			get: vi.fn((name: string) => {
				if (name === 'zondarr_setup_nonce') return nonceCookie;
				return undefined;
			}),
			delete: vi.fn()
		}
	};
}

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

describe('POST /api/auth/setup (hardened proxy)', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('auto-injects bootstrap token when validated nonce is present and token is empty', async () => {
		mockConsumeNonce.mockReturnValue(true);
		mockReadFileSync.mockReturnValue('secret-bootstrap-token\n');

		const upstreamResponse = new Response(JSON.stringify({ id: 'user-1' }), {
			status: 200,
			headers: { 'content-type': 'application/json' }
		});
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(upstreamResponse);

		const event = makeEvent(
			{ username: 'admin', password: 'pass', bootstrap_token: '' },
			'valid-nonce'
		);
		const response = await POST(event as never);

		expect(mockConsumeNonce).toHaveBeenCalledWith('valid-nonce');
		expect(response.status).toBe(200);

		// Verify the upstream fetch was called with the injected token
		const fetchCall = vi.mocked(globalThis.fetch).mock.calls[0];
		const sentBody = JSON.parse(fetchCall![1]!.body as string);
		expect(sentBody.bootstrap_token).toBe('secret-bootstrap-token');
	});

	it('returns 403 when nonce is invalid and no manual token provided', async () => {
		mockConsumeNonce.mockReturnValue(false);
		mockReadFileSync.mockReturnValue('secret-bootstrap-token\n');

		const event = makeEvent(
			{ username: 'admin', password: 'pass', bootstrap_token: '' },
			'invalid-nonce'
		);
		const response = await POST(event as never);

		expect(mockConsumeNonce).toHaveBeenCalledWith('invalid-nonce');
		expect(response.status).toBe(403);

		const body = await response.json();
		expect(body.detail).toContain('Setup authorization expired or invalid');
	});

	it('returns 403 when nonce cookie is missing and no manual token provided', async () => {
		mockReadFileSync.mockReturnValue('secret-bootstrap-token\n');

		const event = makeEvent({ username: 'admin', password: 'pass', bootstrap_token: '' });
		const response = await POST(event as never);

		expect(response.status).toBe(403);

		const body = await response.json();
		expect(body.detail).toContain('Setup authorization expired or invalid');
	});

	it('passes through when manual bootstrap_token is provided regardless of nonce', async () => {
		// Nonce is invalid but manual token is provided — should still work
		mockConsumeNonce.mockReturnValue(false);

		const upstreamResponse = new Response(JSON.stringify({ id: 'user-1' }), {
			status: 200,
			headers: { 'content-type': 'application/json' }
		});
		vi.spyOn(globalThis, 'fetch').mockResolvedValue(upstreamResponse);

		const event = makeEvent(
			{ username: 'admin', password: 'pass', bootstrap_token: 'manual-token' },
			'bad-nonce'
		);
		const response = await POST(event as never);

		expect(response.status).toBe(200);

		// Verify the upstream fetch was called with the manual token
		const fetchCall = vi.mocked(globalThis.fetch).mock.calls[0];
		const sentBody = JSON.parse(fetchCall![1]!.body as string);
		expect(sentBody.bootstrap_token).toBe('manual-token');
	});

	it('returns 403 when nonce is expired and no manual token provided', async () => {
		// An expired nonce causes consumeNonce to return false
		mockConsumeNonce.mockReturnValue(false);
		mockReadFileSync.mockReturnValue('secret-bootstrap-token\n');

		const event = makeEvent(
			{ username: 'admin', password: 'pass', bootstrap_token: '' },
			'expired-nonce'
		);
		const response = await POST(event as never);

		expect(mockConsumeNonce).toHaveBeenCalledWith('expired-nonce');
		expect(response.status).toBe(403);

		const body = await response.json();
		expect(body.detail).toContain('Setup authorization expired or invalid');
	});

	it('returns 403 when nonce exists but was not validated (no token check performed)', async () => {
		// A non-validated nonce (created but never confirmed via token check)
		// is rejected by consumeNonce returning false
		mockConsumeNonce.mockReturnValue(false);
		mockReadFileSync.mockReturnValue('secret-bootstrap-token\n');

		const event = makeEvent(
			{ username: 'admin', password: 'pass', bootstrap_token: '' },
			'non-validated-nonce'
		);
		const response = await POST(event as never);

		expect(mockConsumeNonce).toHaveBeenCalledWith('non-validated-nonce');
		expect(response.status).toBe(403);

		const body = await response.json();
		expect(body.detail).toContain('Setup authorization expired or invalid');
	});
});
