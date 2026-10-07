<script lang="ts">
import { Link2, Unlink } from '@lucide/svelte';
import { onDestroy } from 'svelte';
import {
	type AuthFieldInfo,
	getAuthMethods,
	getErrorDetail,
	linkProvider,
	type ProviderAuthInfo
} from '$lib/api/auth';
import { checkOAuthPin, createOAuthPin } from '$lib/api/client';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { getProviderColor, getProviderIconSvg } from '$lib/stores/providers.svelte';
import { showError, showSuccess } from '$lib/utils/toast';

interface Props {
	authMethod: string;
}

let { authMethod }: Props = $props();

let externalMethods = $state<ProviderAuthInfo[]>([]);
let loadingMethods = $state(true);
let selectedMethod = $state<string | null>(null);
let linking = $state(false);
let errorMessage = $state('');
let linkedResult = $state<{ method: string; external_id: string } | null>(null);

// Credential form state
let fieldValues = $state<Record<string, string>>({});
let fieldErrors = $state<Record<string, string>>({});

// OAuth polling state
let pollIntervalId: ReturnType<typeof setInterval> | null = null;
let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;

const isLinked = $derived(authMethod !== 'local' || linkedResult !== null);

onDestroy(() => {
	stopPolling();
});

$effect(() => {
	if (authMethod === 'local' && !linkedResult) {
		loadAuthMethods();
	} else {
		loadingMethods = false;
	}
});

async function loadAuthMethods() {
	try {
		const methods = await getAuthMethods();
		externalMethods = methods.provider_auth;
	} catch {
		// Silently fail — card just won't show link options
	} finally {
		loadingMethods = false;
	}
}

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

function selectMethod(method: string) {
	selectedMethod = method;
	errorMessage = '';
	fieldValues = {};
	fieldErrors = {};
}

function cancelSelection() {
	stopPolling();
	selectedMethod = null;
	linking = false;
	errorMessage = '';
	fieldValues = {};
	fieldErrors = {};
}

async function handleOAuthLink(method: string) {
	stopPolling();
	linking = true;
	errorMessage = '';
	try {
		const { data: pinData, error: pinError } = await createOAuthPin(method);

		if (pinError || !pinData) {
			linking = false;
			errorMessage = 'Failed to start authentication';
			return;
		}

		window.open(pinData.auth_url, `${method}-auth`, 'width=800,height=600');

		pollIntervalId = setInterval(async () => {
			try {
				const { data: checkData, error: checkError } = await checkOAuthPin(method, pinData.handle);

				if (checkError || !checkData) return;

				if (checkData.authenticated && checkData.redemption_token) {
					stopPolling();
					const result = await linkProvider({
						method,
						credentials: { redemption_token: checkData.redemption_token }
					});
					if (result.error) {
						linking = false;
						errorMessage = getErrorDetail(result.error, 'Failed to link provider');
						showError(errorMessage);
					} else if (result.data) {
						linking = false;
						linkedResult = result.data;
						showSuccess(`Linked to ${method} successfully`);
					}
				}
			} catch {
				// Ignore polling errors
			}
		}, 2000);

		// Stop polling after 5 minutes
		pollTimeoutId = setTimeout(() => {
			stopPolling();
			linking = false;
			errorMessage = 'Authentication timed out. Please try again.';
		}, 300_000);
	} catch {
		linking = false;
		errorMessage = 'Failed to connect to provider';
	}
}

async function handleCredentialLink(e: SubmitEvent) {
	e.preventDefault();
	if (!selectedMethod) return;

	const method = externalMethods.find((m) => m.method_name === selectedMethod);
	if (!method) return;

	// Validate required fields
	fieldErrors = {};
	let hasErrors = false;
	for (const field of method.fields) {
		const val = fieldValues[field.name];
		if (field.required && (!val || val.trim() === '')) {
			fieldErrors[field.name] = `${field.label} is required`;
			hasErrors = true;
		} else if (field.field_type === 'url' && val && val.trim() !== '') {
			try {
				new URL(val);
			} catch {
				fieldErrors[field.name] = 'Must be a valid URL';
				hasErrors = true;
			}
		}
	}
	if (hasErrors) return;

	linking = true;
	errorMessage = '';
	try {
		const result = await linkProvider({
			method: selectedMethod,
			credentials: fieldValues
		});
		if (result.error) {
			errorMessage = getErrorDetail(result.error, 'Failed to link provider');
			showError(errorMessage);
		} else if (result.data) {
			linkedResult = result.data;
			showSuccess(`Linked to ${selectedMethod} successfully`);
		}
	} finally {
		linking = false;
	}
}

function getInputType(fieldType: string): string {
	if (fieldType === 'url') return 'url';
	if (fieldType === 'password') return 'password';
	return 'text';
}
</script>

<Card.Root>
	<Card.Header>
		<div class="flex items-center gap-2">
			<Link2 class="size-5 text-cr-accent" />
			<Card.Title>Linked Provider</Card.Title>
		</div>
		<Card.Description>Link an external authentication provider to your account.</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if isLinked}
			{@const displayMethod = linkedResult?.method ?? authMethod}
			{@const displayId = linkedResult?.external_id ?? ''}
			{@const color = getProviderColor(displayMethod)}
			{@const iconSvg = getProviderIconSvg(displayMethod)}
			<div class="flex items-center gap-3">
				{#if iconSvg}
					<svg class="size-5" viewBox="0 0 24 24" fill={color} aria-hidden="true">
						<path d={iconSvg} />
					</svg>
				{/if}
				<div class="flex flex-col gap-1">
					<div class="flex items-center gap-2">
						<span class="text-sm font-medium capitalize">{displayMethod}</span>
						<Badge variant="outline" class="text-xs">Linked</Badge>
					</div>
					{#if displayId}
						<span class="text-xs text-cr-text-muted">ID: {displayId}</span>
					{/if}
				</div>
			</div>
		{:else if loadingMethods}
			<p class="text-sm text-cr-text-muted">Loading available providers...</p>
		{:else if externalMethods.length === 0}
			<div class="flex items-center gap-2 text-sm text-cr-text-muted">
				<Unlink class="size-4" />
				<span>No external auth providers configured. Add a media server first.</span>
			</div>
		{:else if !selectedMethod}
			<div class="space-y-3">
				<p class="text-sm text-cr-text-muted">
					Link a provider to sign in with your media server account instead of a password.
				</p>
				<div class="flex flex-col gap-2">
					{#each externalMethods as method (method.method_name)}
						{@const color = getProviderColor(method.method_name)}
						{@const iconSvg = getProviderIconSvg(method.method_name)}
						<Button
							onclick={() =>
								method.flow_type === 'oauth'
									? handleOAuthLink(method.method_name)
									: selectMethod(method.method_name)}
							disabled={linking}
							variant="outline"
							class="w-full justify-start border-cr-border bg-cr-bg text-cr-text"
							style="--provider-color: {color}"
						>
							{#if iconSvg}
								<svg class="mr-2 size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
									<path d={iconSvg} />
								</svg>
							{/if}
							Link {method.display_name}
						</Button>
					{/each}
				</div>
			</div>
		{:else}
			{@const method = externalMethods.find((m) => m.method_name === selectedMethod)}
			{#if method}
				{@const color = getProviderColor(method.method_name)}
				{@const iconSvg = getProviderIconSvg(method.method_name)}
				<div class="space-y-3">
					<div class="flex items-center gap-2 text-sm font-medium">
						{#if iconSvg}
							<svg class="size-4" viewBox="0 0 24 24" fill={color} aria-hidden="true">
								<path d={iconSvg} />
							</svg>
						{/if}
						Link {method.display_name}
					</div>

					<form onsubmit={handleCredentialLink} class="flex flex-col gap-3">
						{#each method.fields as field (field.name)}
							<div class="flex flex-col gap-1">
								<Label for="link-{field.name}" class="text-xs">{field.label}</Label>
								<Input
									id="link-{field.name}"
									type={getInputType(field.field_type)}
									bind:value={fieldValues[field.name]}
									placeholder={field.placeholder}
								/>
								{#if fieldErrors[field.name]}
									<p class="text-xs text-red-400">{fieldErrors[field.name]}</p>
								{/if}
							</div>
						{/each}

						{#if errorMessage}
							<p class="text-xs text-red-400">{errorMessage}</p>
						{/if}

						<div class="flex gap-2">
							<Button type="submit" disabled={linking} size="sm">
								{linking ? 'Linking...' : 'Link Account'}
							</Button>
							<Button
								type="button"
								onclick={cancelSelection}
								variant="outline"
								size="sm"
								disabled={linking}
							>
								Cancel
							</Button>
						</div>
					</form>
				</div>
			{/if}
		{/if}

		{#if linking && !selectedMethod}
			<div class="mt-3 flex items-center gap-2 text-sm text-cr-text-muted">
				<span
					class="inline-block size-4 animate-spin rounded-full border-2 border-cr-accent border-t-transparent"
				></span>
				Waiting for authentication...
			</div>
		{/if}

		{#if errorMessage && !selectedMethod}
			<p class="mt-3 text-xs text-red-400">{errorMessage}</p>
		{/if}
	</Card.Content>
</Card.Root>

<style>
:global(button[style*="--provider-color"]:hover) {
	background: color-mix(in srgb, var(--provider-color) 10%, transparent);
	color: var(--provider-color);
	border-color: color-mix(in srgb, var(--provider-color) 30%, transparent);
}
</style>
