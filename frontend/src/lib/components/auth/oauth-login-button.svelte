<script lang="ts">
import { onDestroy } from 'svelte';
import { getErrorDetail, loginExternal } from '$lib/api/auth';
import { checkOAuthPin, createOAuthPin } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { getProviderColor, getProviderIconSvg } from '$lib/stores/providers.svelte';

interface Props {
	method: string;
	displayName: string;
	onsuccess: () => void;
	ontotp: (challengeToken: string) => void;
	onerror: (message: string) => void;
}

const { method, displayName, onsuccess, ontotp, onerror }: Props = $props();

let loading = $state(false);

const color = $derived(getProviderColor(method));
const iconSvg = $derived(getProviderIconSvg(method));

let pollIntervalId: ReturnType<typeof setInterval> | null = null;
let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;

function stopPolling() {
	if (pollIntervalId) {
		clearInterval(pollIntervalId);
		pollIntervalId = null;
	}
	if (pollTimeoutId) {
		clearTimeout(pollTimeoutId);
		pollTimeoutId = null;
	}
}

onDestroy(() => {
	stopPolling();
});

async function handleOAuthLogin() {
	loading = true;
	try {
		const { data: pinData, error: pinError } = await createOAuthPin(method);

		if (pinError || !pinData) {
			loading = false;
			onerror(`Failed to start ${displayName} authentication`);
			return;
		}

		const popup = window.open(pinData.auth_url, `${method}-auth`, 'width=800,height=600');

		pollIntervalId = setInterval(async () => {
			try {
				const { data: checkData, error: checkError } = await checkOAuthPin(method, pinData.handle);

				if (checkError || !checkData) return;

				if (checkData.authenticated && checkData.redemption_token) {
					stopPolling();
					popup?.close();

					const result = await loginExternal(method, {
						redemption_token: checkData.redemption_token
					});
					if (result.error) {
						loading = false;
						onerror(getErrorDetail(result.error, `${displayName} login failed`));
					} else if (result.data?.totp_required && result.data.challenge_token) {
						loading = false;
						ontotp(result.data.challenge_token);
					} else {
						loading = false;
						onsuccess();
					}
				}
			} catch {
				// Ignore polling errors
			}
		}, 2000);

		// Stop polling after 5 minutes
		pollTimeoutId = setTimeout(() => {
			stopPolling();
			popup?.close();
			loading = false;
		}, 300_000);
	} catch {
		loading = false;
		onerror(`Failed to connect to ${displayName}`);
	}
}
</script>

<Button
	onclick={handleOAuthLogin}
	disabled={loading}
	variant="outline"
	class="w-full border-cr-border bg-cr-bg text-cr-text"
	style="--provider-color: {color}"
>
	<svg class="mr-2 size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
		<path d={iconSvg} />
	</svg>
	{#if loading}
		Connecting to {displayName}...
	{:else}
		Sign in with {displayName}
	{/if}
</Button>

<style>
:global(button[style*="--provider-color"]:hover) {
	background: color-mix(in srgb, var(--provider-color) 10%, transparent);
	color: var(--provider-color);
	border-color: color-mix(in srgb, var(--provider-color) 30%, transparent);
}
</style>
