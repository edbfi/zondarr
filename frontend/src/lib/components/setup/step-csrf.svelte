<script lang="ts">
import { Lock, Plug, ShieldCheck } from '@lucide/svelte';
import { browser } from '$app/environment';
import type { CsrfOriginTestResponse } from '$lib/api/client';
import { getCsrfOrigin, setCsrfOrigin, testCsrfOrigin, withErrorHandling } from '$lib/api/client';
import { asErrorResponse } from '$lib/api/errors';
import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { csrfOriginSchema } from '$lib/schemas/setup';
import { showInfo } from '$lib/utils/toast';

interface Props {
	onComplete: () => void;
	onSkip: () => void;
}

const { onComplete, onSkip }: Props = $props();

let origin = $state(browser ? window.location.origin : '');
let errors = $state<Record<string, string>>({});
let serverError = $state('');
let submitting = $state(false);

// Test state
let testing = $state(false);
let testResult = $state<CsrfOriginTestResponse | null>(null);
let hasAttemptedTest = $state(false);

// Lock state — env-managed CSRF_ORIGIN cannot be edited from the wizard
let isLocked = $state(false);
let lockedSourceLoaded = $state(false);
let loadError = $state('');

// Confirmation dialog state
let showSaveConfirm = $state(false);
let showSkipConfirm = $state(false);

const canTest = $derived(origin.trim().length > 0);
const testPassed = $derived(testResult?.success === true);

async function loadLockedSource() {
	loadError = '';
	const result = await withErrorHandling(() => getCsrfOrigin(), {
		showErrorToast: false
	});
	if (result?.data) {
		isLocked = Boolean(result.data.is_locked);
		if (result.data.csrf_origin) {
			origin = result.data.csrf_origin;
		}
	} else {
		const errorBody = asErrorResponse(result?.error);
		loadError =
			errorBody?.detail ??
			'Could not load CSRF settings — the lock state is unknown. The backend may be env-locked.';
	}
	lockedSourceLoaded = true;
}

$effect(() => {
	loadLockedSource();
});

function onOriginChange() {
	testResult = null;
	hasAttemptedTest = false;
}

async function handleTest() {
	testing = true;
	testResult = null;

	try {
		const result = await withErrorHandling(() => testCsrfOrigin(origin), {
			showErrorToast: false
		});

		if (result.error || !result.data) {
			const errorBody = asErrorResponse(result.error);
			testResult = {
				success: false,
				message: errorBody?.detail ?? 'Network error — could not reach the backend.',
				request_origin: null
			};
		} else {
			testResult = result.data;
		}
	} finally {
		testing = false;
		hasAttemptedTest = true;
	}
}

function handleSaveClick() {
	if (testPassed) {
		handleSubmit();
	} else {
		showSaveConfirm = true;
	}
}

function handleSkipClick() {
	if (testPassed) {
		onSkip();
	} else {
		showSkipConfirm = true;
	}
}

async function handleSubmit() {
	errors = {};
	serverError = '';

	const result = csrfOriginSchema.safeParse({ origin });
	if (!result.success) {
		for (const issue of result.error.issues) {
			const field = issue.path[0];
			if (field && typeof field === 'string') {
				errors[field] = issue.message;
			}
		}
		return;
	}

	submitting = true;
	try {
		const response = await withErrorHandling(
			() => setCsrfOrigin({ csrf_origin: result.data.origin }),
			{ showErrorToast: false }
		);

		if (response.error) {
			const errorBody = asErrorResponse(response.error);
			serverError = errorBody?.detail ?? 'Failed to save CSRF origin';
			return;
		}

		if (response.data?.secure_cookies_auto_enabled) {
			showInfo('Secure cookies have been automatically enabled because your site uses HTTPS.');
		}

		onComplete();
	} finally {
		submitting = false;
	}
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<div class="flex items-center gap-2">
			<Card.Title class="text-lg text-cr-text">Security Configuration</Card.Title>
			{#if isLocked}
				<Badge variant="secondary" class="gap-1">
					<Lock class="size-3" />
					Environment Variable
				</Badge>
			{/if}
		</div>
		<Card.Description class="text-cr-text-muted">
			{#if isLocked}
				CSRF origin is managed by the <code class="font-mono text-xs">CSRF_ORIGIN</code>
				environment variable. The current value is shown below and cannot be edited from the wizard.
			{:else}
				Set your trusted origin for CSRF protection.
			{/if}
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if serverError}
			<div
				class="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
			>
				{serverError}
			</div>
		{/if}

		{#if loadError}
			<div
				class="mb-4 flex items-start justify-between gap-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-400"
			>
				<span>{loadError}</span>
				<button
					type="button"
					onclick={loadLockedSource}
					class="shrink-0 underline hover:text-amber-300"
				>
					Retry
				</button>
			</div>
		{/if}

		<!-- Info callout -->
		<div class="mb-4 rounded-lg border border-cr-accent/30 bg-cr-accent/5 p-3">
			<div class="flex items-start gap-2">
				<ShieldCheck class="mt-0.5 size-4 shrink-0 text-cr-accent" />
				<p class="text-sm text-cr-text-muted">
					CSRF protection prevents unauthorized requests from other websites. Set this to the URL
					where you access Zondarr to ensure only your browser can make changes.
				</p>
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<Label for="csrf-origin" class="text-cr-text">Trusted Origin</Label>
				<Input
					id="csrf-origin"
					type="url"
					bind:value={origin}
					oninput={onOriginChange}
					placeholder="https://zondarr.example.com"
					disabled={isLocked || submitting || testing || !lockedSourceLoaded}
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm"
				/>
				<p class="text-xs text-cr-text-muted">
					The origin URL where Zondarr is accessed (e.g., https://zondarr.example.com)
				</p>
				{#if errors.origin}
					<p class="text-xs text-red-400">{errors.origin}</p>
				{/if}
			</div>

			{#if lockedSourceLoaded && !isLocked}
				<!-- Test Origin -->
				<div class="space-y-2">
					<Button
						type="button"
						variant="outline"
						onclick={handleTest}
						disabled={!canTest || testing || submitting}
						class="w-full border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border"
					>
						{#if testing}
							<span
								class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
							></span>
							Testing...
						{:else}
							<Plug class="size-4" />
							Test Origin
						{/if}
					</Button>

					{#if testResult}
						{#if testResult.success}
							<div
								class="rounded-md border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-400"
							>
								<p>{testResult.message}</p>
							</div>
						{:else}
							<div
								class="rounded-md border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-sm text-rose-400"
							>
								<p>{testResult.message}</p>
							</div>
						{/if}
					{/if}
				</div>
			{/if}

			<div class="flex items-center justify-between gap-3 border-t border-cr-border pt-4">
				{#if !lockedSourceLoaded}
					<div class="ml-auto">
						<span
							class="block size-4 animate-spin rounded-full border-2 border-current border-t-transparent text-cr-text-muted"
						></span>
					</div>
				{:else if isLocked}
					<Button
						type="button"
						onclick={onSkip}
						class="ml-auto bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
					>
						Continue
					</Button>
				{:else}
					<Button
						type="button"
						variant="ghost"
						onclick={handleSkipClick}
						disabled={!hasAttemptedTest || submitting || testing}
						class="text-cr-text-muted hover:text-cr-text"
					>
						Skip for now
					</Button>
					<Button
						type="button"
						onclick={handleSaveClick}
						disabled={!hasAttemptedTest || submitting || testing}
						class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
					>
						{#if submitting}
							<span
								class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
							></span>
							Saving...
						{:else}
							Save & Continue
						{/if}
					</Button>
				{/if}
			</div>
		</div>

		<p class="mt-3 text-center text-xs text-cr-text-dim">You can change this later in Settings.</p>
	</Card.Content>
</Card.Root>

<ConfirmDialog
	bind:open={showSaveConfirm}
	title="Save Mismatched Origin?"
	description="The CSRF origin test did not pass. Saving a mismatched origin may block you from accessing Zondarr. Are you sure you want to save?"
	confirmLabel="Save Anyway"
	variant="warning"
	onConfirm={() => {
	showSaveConfirm = false;
	handleSubmit();
}}
	onCancel={() => {
	showSaveConfirm = false;
}}
/>

<ConfirmDialog
	bind:open={showSkipConfirm}
	title="Skip Without CSRF Protection?"
	description="The CSRF origin test did not pass. Skipping means CSRF protection will not be configured. Are you sure?"
	confirmLabel="Skip Anyway"
	variant="warning"
	onConfirm={() => {
	showSkipConfirm = false;
	onSkip();
}}
	onCancel={() => {
	showSkipConfirm = false;
}}
/>
