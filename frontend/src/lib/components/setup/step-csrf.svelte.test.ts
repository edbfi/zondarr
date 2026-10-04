/**
 * Component tests for StepCsrf with API mocking.
 *
 * Tests rendering, validation, test button, and API interaction.
 *
 * @module $lib/components/setup/step-csrf.svelte.test
 */

import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/env', () => ({ browser: true }));
vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		getCsrfOrigin: vi.fn(),
		setCsrfOrigin: vi.fn(),
		testCsrfOrigin: vi.fn(),
		withErrorHandling: vi.fn()
	};
});

import * as apiClient from '$lib/api/client';
import StepCsrf from './step-csrf.svelte';

afterEach(() => {
	cleanup();
	vi.resetAllMocks();
});

beforeEach(() => {
	// Default getCsrfOrigin response: not locked. The component's $effect
	// always issues this call on mount via withErrorHandling, so each test
	// must enqueue a leading mock for it before the test-specific calls.
	vi.mocked(apiClient.withErrorHandling).mockResolvedValue({
		data: { csrf_origin: 'http://localhost:3000', is_locked: false },
		error: undefined
	});
});

/** Helper to find a button by text content. */
function findButton(container: HTMLElement, text: string): HTMLButtonElement | undefined {
	return Array.from(container.querySelectorAll('button')).find((b) =>
		b.textContent?.includes(text)
	) as HTMLButtonElement | undefined;
}

/** Mock for the $effect's getCsrfOrigin call. Returns unlocked by default. */
function mockGetCsrfOriginUnlocked() {
	vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
		data: { csrf_origin: 'http://localhost:3000', is_locked: false },
		error: undefined
	});
}

describe('Step CSRF Component', () => {
	it('should render security configuration card', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		expect(container.textContent).toContain('Security Configuration');
		expect(container.textContent).toContain('CSRF protection');
		expect(container.querySelector('input[type="url"]')).toBeTruthy();
	});

	it('should auto-populate origin with window.location.origin', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		expect(input).toBeTruthy();
		expect(input.value).toBe(window.location.origin);
	});

	it('should render Test, Skip and Save buttons', async () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		// Wait for the $effect to settle and footer buttons to appear.
		await waitFor(() => {
			expect(findButton(container, 'Save')).toBeTruthy();
		});

		expect(findButton(container, 'Test Origin')).toBeTruthy();
		expect(findButton(container, 'Skip')).toBeTruthy();
		expect(findButton(container, 'Save')).toBeTruthy();
	});

	it('should have Save and Skip disabled before test attempt', async () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Save')).toBeTruthy();
		});

		const saveBtn = findButton(container, 'Save');
		const skipBtn = findButton(container, 'Skip');
		expect(saveBtn?.disabled).toBe(true);
		expect(skipBtn?.disabled).toBe(true);
	});

	it('should enable Save and Skip after successful test', async () => {
		const user = userEvent.setup();

		// First call from effect (unlocked), second from test button (success)
		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: { success: true, message: 'Origin matches', request_origin: 'http://localhost:3000' },
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		const testBtn = findButton(container, 'Test Origin')!;
		await user.click(testBtn);

		const saveBtn = findButton(container, 'Save');
		const skipBtn = findButton(container, 'Skip');
		expect(saveBtn?.disabled).toBe(false);
		expect(skipBtn?.disabled).toBe(false);
	});

	it('should display success result after test', async () => {
		const user = userEvent.setup();

		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: {
				success: true,
				message: 'Origin matches — CSRF protection will work correctly.',
				request_origin: 'http://localhost:3000'
			},
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		await user.click(findButton(container, 'Test Origin')!);

		expect(container.textContent).toContain('Origin matches');
		// Green success box
		expect(container.querySelector('.border-green-500\\/30')).toBeTruthy();
	});

	it('should display failure result after test', async () => {
		const user = userEvent.setup();

		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: {
				success: false,
				message:
					"Origin mismatch: you entered 'https://wrong.com' but your browser sent 'http://localhost:3000'.",
				request_origin: 'http://localhost:3000'
			},
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		await user.click(findButton(container, 'Test Origin')!);

		expect(container.textContent).toContain('Origin mismatch');
		// Rose failure box
		expect(container.querySelector('.border-rose-400\\/30')).toBeTruthy();
	});

	it('should reset test state when origin changes', async () => {
		const user = userEvent.setup();

		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling).mockResolvedValue({
			data: { success: true, message: 'Origin matches', request_origin: 'http://localhost:3000' },
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		// Run test first
		await user.click(findButton(container, 'Test Origin')!);
		expect(findButton(container, 'Save')?.disabled).toBe(false);

		// Change origin input
		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		await user.type(input, '/changed');

		// Save and Skip should be disabled again
		expect(findButton(container, 'Save')?.disabled).toBe(true);
		expect(findButton(container, 'Skip')?.disabled).toBe(true);
	});

	it('should call API and onComplete on successful test then save', async () => {
		const onComplete = vi.fn();
		const user = userEvent.setup();

		// Effect call (unlocked), test origin call, save call
		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling)
			.mockResolvedValueOnce({
				data: { success: true, message: 'Origin matches', request_origin: 'http://localhost:3000' },
				error: undefined
			})
			.mockResolvedValueOnce({
				data: { csrf_origin: 'http://localhost:3000', is_locked: false },
				error: undefined
			});

		const { container } = render(StepCsrf, {
			props: { onComplete, onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		// Test first
		await user.click(findButton(container, 'Test Origin')!);
		// Then save (test passed, so no confirmation dialog)
		await user.click(findButton(container, 'Save')!);

		// 3 calls: effect's getCsrfOrigin, testCsrfOrigin, setCsrfOrigin
		expect(apiClient.withErrorHandling).toHaveBeenCalledTimes(3);
		expect(onComplete).toHaveBeenCalledTimes(1);
	});

	it('should call onSkip directly when test passed and Skip clicked', async () => {
		const onSkip = vi.fn();
		const user = userEvent.setup();

		mockGetCsrfOriginUnlocked();
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: { success: true, message: 'Origin matches', request_origin: 'http://localhost:3000' },
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		await user.click(findButton(container, 'Test Origin')!);
		await user.click(findButton(container, 'Skip')!);

		expect(onSkip).toHaveBeenCalledTimes(1);
	});

	it('should show validation error for empty origin on save', async () => {
		const user = userEvent.setup();

		mockGetCsrfOriginUnlocked();
		// Mock test as failed so save triggers confirmation
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: { success: false, message: 'Failed', request_origin: null },
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		// Clear the auto-populated input
		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		await user.clear(input);

		// Type something to enable test, then test
		await user.type(input, 'https://test.com');
		await user.click(findButton(container, 'Test Origin')!);

		// Clear input again
		await user.clear(input);

		// Test the validation path: type a path-containing origin
		await user.type(input, 'https://example.com/path');

		// Test to enable buttons
		vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
			data: { success: false, message: 'Mismatch', request_origin: 'http://localhost:3000' },
			error: undefined
		});
		await user.click(findButton(container, 'Test Origin')!);

		// Click save - shows confirmation since test failed
		await user.click(findButton(container, 'Save')!);

		// Confirm in the dialog - find "Save Anyway" button
		const confirmBtn = findButton(document.body as HTMLElement, 'Save Anyway');
		if (confirmBtn) {
			vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
				data: undefined,
				error: undefined
			});
			await user.click(confirmBtn);
		}

		// Should show a validation error for path
		expect(container.textContent).toContain('without a trailing path');
	});

	it('should display server error on API failure', async () => {
		// pointerEventsCheck disabled: prior test's dialog CSS leaks into jsdom
		const user = userEvent.setup({ pointerEventsCheck: 0 });

		let callCount = 0;
		vi.mocked(apiClient.withErrorHandling).mockImplementation(async () => {
			callCount++;
			// First call: effect's getCsrfOrigin
			if (callCount === 1) {
				return {
					data: { csrf_origin: 'http://localhost:3000', is_locked: false },
					error: undefined
				};
			}
			// Second call: test origin succeeds
			if (callCount === 2) {
				return {
					data: {
						success: true,
						message: 'Origin matches',
						request_origin: 'http://localhost:3000'
					},
					error: undefined
				};
			}
			// Third call: save fails
			return {
				data: undefined,
				error: { detail: 'Server unavailable', error_code: 'INTERNAL_ERROR' }
			};
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		await waitFor(() => {
			expect(findButton(container, 'Test Origin')).toBeTruthy();
		});

		await user.click(findButton(container, 'Test Origin')!);
		await user.click(findButton(container, 'Save')!);

		expect(container.textContent).toContain('Server unavailable');
	});

	it('should display CSRF info callout', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		expect(container.textContent).toContain(
			'CSRF protection prevents unauthorized requests from other websites'
		);
	});

	describe('Locked CSRF (env-managed)', () => {
		it('should show env badge and a single Continue button when CSRF_ORIGIN is locked', async () => {
			const onComplete = vi.fn();
			const onSkip = vi.fn();

			vi.mocked(apiClient.withErrorHandling).mockReset();
			vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
				data: { csrf_origin: 'http://localhost:5173', is_locked: true },
				error: undefined
			});

			const { container } = render(StepCsrf, {
				props: { onComplete, onSkip }
			});

			// Wait for the $effect to settle and the locked-state UI to appear.
			await waitFor(() => {
				expect(container.textContent).toContain('Environment Variable');
			});

			// Save & Continue should NOT be present in locked state
			expect(findButton(container, 'Save')).toBeUndefined();
			// Test Origin should be hidden in locked state
			expect(findButton(container, 'Test Origin')).toBeUndefined();
			// Skip button should be hidden — replaced by Continue
			expect(findButton(container, 'Skip')).toBeUndefined();

			// Continue button is present
			const continueBtn = findButton(container, 'Continue');
			expect(continueBtn).toBeTruthy();

			// Input should be disabled in locked state
			const input = container.querySelector('input[type="url"]') as HTMLInputElement;
			expect(input.disabled).toBe(true);
			// And display the env-supplied origin
			expect(input.value).toBe('http://localhost:5173');
		});

		it('Continue button calls onSkip exactly once (advances onboarding)', async () => {
			const onComplete = vi.fn();
			const onSkip = vi.fn();
			const user = userEvent.setup();

			vi.mocked(apiClient.withErrorHandling).mockReset();
			vi.mocked(apiClient.withErrorHandling).mockResolvedValueOnce({
				data: { csrf_origin: 'http://localhost:5173', is_locked: true },
				error: undefined
			});

			const { container } = render(StepCsrf, {
				props: { onComplete, onSkip }
			});

			await waitFor(() => {
				expect(findButton(container, 'Continue')).toBeTruthy();
			});

			await user.click(findButton(container, 'Continue')!);

			expect(onSkip).toHaveBeenCalledTimes(1);
			expect(onComplete).not.toHaveBeenCalled();
		});
	});
});
