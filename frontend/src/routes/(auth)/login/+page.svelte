<script lang="ts">
import { goto, invalidateAll } from '$app/navigation';
import { getErrorDetail, loginLocal } from '$lib/api/auth';
import CredentialLoginForm from '$lib/components/auth/credential-login-form.svelte';
import LocalLoginForm from '$lib/components/auth/local-login-form.svelte';
import OAuthLoginButton from '$lib/components/auth/oauth-login-button.svelte';
import TotpVerifyStep from '$lib/components/auth/totp-verify-step.svelte';
import * as Card from '$lib/components/ui/card';
import { Separator } from '$lib/components/ui/separator';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

let error = $state('');
let retryTimer: ReturnType<typeof setInterval> | null = null;
let totpChallengeToken = $state<string | null>(null);

const backendAvailable = $derived(data.backendAvailable !== false);
const externalMethods = $derived(data.providerAuth ?? []);
const hasExternal = $derived(externalMethods.length > 0);
const showTotpStep = $derived(totpChallengeToken !== null);

$effect(() => {
	if (!backendAvailable && !retryTimer) {
		retryTimer = setInterval(() => {
			invalidateAll();
		}, 3000);
	}
	if (backendAvailable && retryTimer) {
		clearInterval(retryTimer);
		retryTimer = null;
	}
	return () => {
		if (retryTimer) {
			clearInterval(retryTimer);
		}
	};
});

async function handleLocalLogin(username: string, password: string) {
	error = '';
	const result = await loginLocal({ username, password });
	if (result.error) {
		error = getErrorDetail(result.error, 'Invalid credentials');
		return;
	}
	if (result.data?.totp_required && result.data.challenge_token) {
		totpChallengeToken = result.data.challenge_token;
		return;
	}
	await invalidateAll();
	await goto('/dashboard');
}

async function handleTotpSuccess() {
	totpChallengeToken = null;
	await invalidateAll();
	await goto('/dashboard');
}

function handleTotpCancel() {
	totpChallengeToken = null;
	error = '';
}

async function handleExternalSuccess() {
	await invalidateAll();
	await goto('/dashboard');
}

function handleExternalTotp(challengeToken: string) {
	totpChallengeToken = challengeToken;
}

function handleExternalError(message: string) {
	error = message;
}
</script>

{#if !backendAvailable}
	<Card.Root class="border-cr-border bg-cr-surface">
		<Card.Header>
			<Card.Title class="text-center text-lg text-cr-text">Connecting to server...</Card.Title>
			<Card.Description class="text-center text-cr-text-muted">
				Waiting for the backend to become available. This page will retry automatically.
			</Card.Description>
		</Card.Header>
		<Card.Content class="flex justify-center py-4">
			<div
				class="h-6 w-6 animate-spin rounded-full border-2 border-cr-text-muted border-t-cr-accent"
			></div>
		</Card.Content>
	</Card.Root>
{:else if showTotpStep}
	<Card.Root class="border-cr-border bg-cr-surface">
		<Card.Content class="py-6">
			<TotpVerifyStep
				challengeToken={totpChallengeToken!}
				onsuccess={handleTotpSuccess}
				oncancel={handleTotpCancel}
			/>
		</Card.Content>
	</Card.Root>
{:else}
	<Card.Root class="border-cr-border bg-cr-surface">
		<Card.Header>
			<Card.Title class="text-center text-lg text-cr-text">Sign in to Zondarr</Card.Title>
			<Card.Description class="text-center text-cr-text-muted">
				Enter your credentials to continue
			</Card.Description>
		</Card.Header>
		<Card.Content class="flex flex-col gap-4">
			{#if error}
				<div
					class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
				>
					{error}
				</div>
			{/if}

			<LocalLoginForm onsubmit={handleLocalLogin} />

			{#if hasExternal}
				<div class="relative my-2">
					<Separator class="bg-cr-border" />
					<span
						class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-cr-surface px-3 text-xs text-cr-text-dim"
					>
						or
					</span>
				</div>

				<div class="flex flex-col gap-2">
					{#each externalMethods as method (method.method_name)}
						{#if method.flow_type === 'oauth'}
							<OAuthLoginButton
								method={method.method_name}
								displayName={method.display_name}
								onsuccess={handleExternalSuccess}
								ontotp={handleExternalTotp}
								onerror={handleExternalError}
							/>
						{:else}
							<CredentialLoginForm
								method={method.method_name}
								displayName={method.display_name}
								fields={method.fields}
								onsuccess={handleExternalSuccess}
								ontotp={handleExternalTotp}
								onerror={handleExternalError}
							/>
						{/if}
					{/each}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
{/if}
