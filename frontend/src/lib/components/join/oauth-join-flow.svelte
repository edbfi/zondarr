<script lang="ts">
/**
 * OAuth join flow component.
 *
 * Provides OAuth authentication flow for media servers:
 * - "Sign in" button with provider branding
 * - PIN creation via API (backend handles transient retries)
 * - Polls PIN status until authenticated or expired
 * - Opens auth URL in new window/tab
 * - Displays user's email when authenticated
 * - Error handling with manual retry option
 *
 * @module $lib/components/join/oauth-join-flow
 */

import { AlertTriangle, CheckCircle, ExternalLink, Loader2, RefreshCw } from '@lucide/svelte';
import { onDestroy } from 'svelte';
import { toast } from 'svelte-sonner';
import { checkOAuthPin, createOAuthPin, type OAuthPinResponse } from '$lib/api/client';
import { getErrorMessage } from '$lib/api/errors';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
import {
	getProviderColor,
	getProviderIconSvg,
	getProviderLabel
} from '$lib/stores/providers.svelte';

interface Props {
	/** The server type for branding (e.g., "plex") */
	serverType: string;
	/** Callback when authentication is successful (receives one-time redemption token) */
	onAuthenticated: (email: string, redemptionToken: string) => void;
	/** Callback when user cancels the flow */
	onCancel?: () => void;
}

const { serverType, onAuthenticated, onCancel }: Props = $props();

const providerLabel = $derived(getProviderLabel(serverType));
const providerColor = $derived(getProviderColor(serverType));
const providerIconSvg = $derived(getProviderIconSvg(serverType));

// Flow state
type FlowStep = 'idle' | 'creating_pin' | 'waiting' | 'authenticated' | 'expired' | 'error';
let currentStep = $state<FlowStep>('idle');

// PIN data
let pinData = $state<OAuthPinResponse | null>(null);
let authenticatedEmail = $state<string | null>(null);
let errorMessage = $state<string | null>(null);

// Popup window reference
let popupWindow = $state<Window | null>(null);

// Polling
let pollingInterval = $state<ReturnType<typeof setTimeout> | null>(null);
const POLL_INTERVAL_MS = 2000;
// Track consecutive polling errors to show status to user
let consecutivePollingErrors = $state(0);
// Guard against in-flight checkOAuthPin() resolving after cancellation
let pollCancelled = $state(false);

/**
 * Close the popup window if it's still open.
 */
function closePopup() {
	popupWindow?.close();
	popupWindow = null;
}

/**
 * Clean up polling interval.
 */
function stopPolling() {
	pollCancelled = true;
	if (pollingInterval) {
		clearTimeout(pollingInterval);
		pollingInterval = null;
	}
	consecutivePollingErrors = 0;
}

// Clean up on component destroy
onDestroy(() => {
	stopPolling();
	closePopup();
});

/**
 * Check if PIN has expired based on expires_at timestamp.
 */
function isPinExpired(expiresAt: string): boolean {
	return new Date(expiresAt) <= new Date();
}

/**
 * Start the OAuth flow.
 *
 * PIN creation is a single attempt — the backend already retries
 * transient failures (up to 6 attempts with exponential backoff).
 * Adding a frontend retry loop would multiply total requests and latency.
 */
async function startOAuthFlow() {
	currentStep = 'creating_pin';
	errorMessage = null;

	try {
		const { data, error } = await createOAuthPin(serverType);

		if (error) {
			throw new Error(getErrorMessage(error));
		}

		if (!data) {
			throw new Error('Failed to start authentication');
		}

		pinData = data;
		currentStep = 'waiting';

		// Open auth URL in popup window (named window allows control + auto-close).
		// Note: We intentionally omit noopener/noreferrer to retain a popup reference for
		// auto-close. Referrer leakage is mitigated by the join page's <meta name="referrer"
		// content="no-referrer"> tag. Reverse-tabnabbing risk is minimal since auth_url is
		// generated server-side pointing to trusted OAuth providers (e.g. Plex.tv).
		popupWindow = window.open(pinData.auth_url, `${serverType}-auth`, 'width=800,height=600');

		// Start polling for PIN status
		startPolling();
	} catch (err) {
		closePopup();
		errorMessage = getErrorMessage(err);
		currentStep = 'error';
		toast.error(`Failed to start ${providerLabel} authentication`);
	}
}

/**
 * Start polling for PIN status.
 *
 * Resilient to transient network errors — continues polling and tracks
 * consecutive failures. Only stops on terminal conditions (authentication,
 * expiration, or server-reported errors).
 */
function startPolling() {
	if (!pinData) return;
	pollCancelled = false;
	consecutivePollingErrors = 0;

	async function poll() {
		if (!pinData) {
			stopPolling();
			return;
		}

		// Check if PIN has expired
		if (isPinExpired(pinData.expires_at)) {
			stopPolling();
			closePopup();
			currentStep = 'expired';
			return;
		}

		try {
			const { data, error } = await checkOAuthPin(serverType, pinData.handle);

			// Cancelled while the request was in-flight
			if (pollCancelled) return;

			if (error) {
				consecutivePollingErrors++;
				console.error('PIN check error:', error);
			} else {
				// Successful response — reset error counter
				consecutivePollingErrors = 0;

				if (data) {
					if (data.authenticated && data.email && data.redemption_token) {
						stopPolling();
						closePopup();
						authenticatedEmail = data.email;
						currentStep = 'authenticated';
						onAuthenticated(data.email, data.redemption_token);
						return;
					} else if (data.authenticated && data.email) {
						stopPolling();
						closePopup();
						errorMessage = 'OAuth succeeded but no redemption token was returned.';
						currentStep = 'error';
						return;
					} else if (data.error) {
						stopPolling();
						closePopup();
						errorMessage = data.error;
						currentStep = 'error';
						return;
					}
				}
			}
		} catch {
			// Don't stop polling on network errors — increment counter for UX
			consecutivePollingErrors++;
		}

		// Schedule next poll only after this one completes
		if (pollingInterval !== null) {
			pollingInterval = setTimeout(poll, POLL_INTERVAL_MS);
		}
	}

	// Start first poll after interval delay (matching current behavior)
	pollingInterval = setTimeout(poll, POLL_INTERVAL_MS);
}

/**
 * Retry the OAuth flow after error or expiration.
 */
function handleRetry() {
	stopPolling();
	closePopup();
	pinData = null;
	authenticatedEmail = null;
	errorMessage = null;
	startOAuthFlow();
}

/**
 * Cancel the OAuth flow.
 */
function handleCancel() {
	stopPolling();
	closePopup();
	pinData = null;
	currentStep = 'idle';
	onCancel?.();
}

/**
 * Open the auth URL again.
 */
function openAuthUrl() {
	if (pinData?.auth_url) {
		// See startOAuthFlow() for security rationale on omitting noopener/noreferrer
		popupWindow = window.open(pinData.auth_url, `${serverType}-auth`, 'width=800,height=600');
	}
}
</script>

<div class="space-y-6" data-oauth-join-flow data-step={currentStep}>
	<!-- Idle state: Sign in button -->
	{#if currentStep === 'idle'}
		<div class="text-center space-y-4">
			<p class="text-cr-text-muted">
				Sign in with your {providerLabel} account to get access to the media server.
			</p>
			<Button
				onclick={startOAuthFlow}
				class="w-full font-semibold"
				style="background: {providerColor}; color: #000"
				data-oauth-signin-button
			>
				{#if providerIconSvg}
					<svg class="size-5 mr-2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<path d={providerIconSvg} />
					</svg>
				{/if}
				Sign in with {providerLabel}
			</Button>
		</div>
	<!-- Creating PIN state -->
	{:else if currentStep === 'creating_pin'}
		<div class="text-center space-y-4">
			<div class="flex justify-center">
				<Loader2 class="size-8 animate-spin text-cr-accent" />
			</div>
			<p class="text-cr-text-muted">Preparing {providerLabel} authentication...</p>
		</div>
	<!-- Waiting for authentication -->
	{:else if currentStep === 'waiting' && pinData}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<CardTitle class="text-cr-text">Complete Authentication</CardTitle>
				<CardDescription class="text-cr-text-muted">
					A new window has opened for {providerLabel} sign-in. Complete the authentication there.
				</CardDescription>
			</CardHeader>
			<CardContent class="space-y-4">
				<!-- Waiting indicator -->
				<div class="flex items-center justify-center gap-2 text-cr-text-muted">
					<Loader2 class="size-4 animate-spin" />
					<span class="text-sm">
						{#if consecutivePollingErrors > 2}
							Reconnecting... ({consecutivePollingErrors}
							check{consecutivePollingErrors === 1 ? '' : 's'}
							missed)
						{:else}
							Waiting for authentication...
						{/if}
					</span>
				</div>

				<!-- Action buttons -->
				<div class="flex gap-2">
					<Button
						variant="outline"
						onclick={openAuthUrl}
						class="flex-1 border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
					>
						<ExternalLink class="size-4 mr-2" />
						Open {providerLabel} Again
					</Button>
					<Button
						variant="ghost"
						onclick={handleCancel}
						class="text-cr-text-muted hover:text-cr-text"
					>
						Cancel
					</Button>
				</div>
			</CardContent>
		</Card>
	<!-- Authenticated state -->
	{:else if currentStep === 'authenticated' && authenticatedEmail}
		<Card class="border-emerald-500/30 bg-emerald-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-emerald-500/15 p-2 text-emerald-400">
						<CheckCircle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">{providerLabel} Authentication Successful</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Signed in as
							<span class="font-medium text-cr-text" data-oauth-email>{authenticatedEmail}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
		</Card>
	<!-- Expired state -->
	{:else if currentStep === 'expired'}
		<Card class="border-amber-500/30 bg-amber-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-amber-500/15 p-2 text-amber-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Authentication Expired</CardTitle>
						<CardDescription class="text-cr-text-muted">
							The authentication session has expired. Please try again.
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<Button
					onclick={handleRetry}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					<RefreshCw class="size-4 mr-2" />
					Try Again
				</Button>
			</CardContent>
		</Card>
	<!-- Error state -->
	{:else if currentStep === 'error'}
		<Card class="border-rose-500/30 bg-rose-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Authentication Failed</CardTitle>
						<CardDescription class="text-cr-text-muted">
							{errorMessage ?? 'An error occurred during authentication.'}
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<Button
					onclick={handleRetry}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					<RefreshCw class="size-4 mr-2" />
					Try Again
				</Button>
			</CardContent>
		</Card>
	{/if}
</div>
