<script lang="ts">
/**
 * Create server dialog component.
 *
 * Provides a modal dialog for adding new media servers with:
 * - Form validation via Zod
 * - Server type toggle (dynamically populated from provider registry)
 * - API submission with connection validation
 * - Success/error toast notifications
 * - Auto-close on successful creation
 *
 * @module $lib/components/servers/create-server-dialog
 */

import { Eye, EyeOff, Info, KeyRound, Plug, Plus, Server, X } from "@lucide/svelte";
import type {
	ConnectionTestRequest,
	ConnectionTestResponse,
	EnvCredentialResponse,
} from "$lib/api/client";
import { createServer, getEnvCredentials, testConnection, withErrorHandling } from "$lib/api/client";
import { asErrorResponse } from "$lib/api/errors";
import { Button } from "$lib/components/ui/button";
import * as Dialog from "$lib/components/ui/dialog";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import {
	type CreateServerInput,
	createServerSchema,
	transformCreateServerData,
} from "$lib/schemas/media-server";
import { getAllProviders, getProviderActiveToggleStyle } from "$lib/stores/providers.svelte";
import { showError, showSuccess } from "$lib/utils/toast";

interface Props {
	onSuccess?: () => void;
}

const { onSuccess }: Props = $props();

const providerList = $derived(getAllProviders());

// Dialog open state
let open = $state(false);

// Reset form when dialog closes, fetch env credentials when it opens
let hasBeenOpened = false;
$effect(() => {
	if (open) {
		hasBeenOpened = true;
		fetchEnvCredentials();
	} else if (hasBeenOpened) {
		resetForm();
	}
});

// Submitting state
let submitting = $state(false);

// Show/hide API key
let showApiKey = $state(false);

// Test connection state
let testing = $state(false);
let testResult = $state<ConnectionTestResponse | null>(null);

// Form data state
let formData = $state<CreateServerInput>({
	name: "",
	server_type: "plex",
	url: "",
	api_key: "",
	use_env_credentials: false,
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

// Env credentials auto-detection
let envCredentials = $state<EnvCredentialResponse[]>([]);
let envLoading = $state(false);
let envDismissed = $state(false);

const completeEnvCredentials = $derived(
	envCredentials.filter((c) => c.has_url && c.has_api_key)
);
const showEnvBanner = $derived(!envDismissed && completeEnvCredentials.length > 0);

/**
 * Reset form to initial state.
 */
function resetForm() {
	formData = {
		name: "",
		server_type: "plex",
		url: "",
		api_key: "",
		use_env_credentials: false,
	};
	errors = {};
	showApiKey = false;
	testing = false;
	testResult = null;
	envCredentials = [];
	envDismissed = false;
}

/**
 * Fetch detected environment credentials from the backend.
 */
async function fetchEnvCredentials() {
	envLoading = true;
	try {
		const result = await withErrorHandling(() => getEnvCredentials(), {
			showErrorToast: false,
		});
		if (open && result.data) {
			envCredentials = result.data.credentials;
		}
	} finally {
		envLoading = false;
	}
}

/**
 * Auto-fill the form with detected environment credentials.
 */
function handleUseEnvCredentials(credential: EnvCredentialResponse) {
	formData.server_type = credential.server_type;
	formData.url = "";
	formData.use_env_credentials = true;
	formData.api_key = "";
	if (!formData.name) formData.name = credential.display_name;
	const nextErrors = { ...errors };
	delete nextErrors.url;
	delete nextErrors.api_key;
	errors = nextErrors;
	testResult = null;
	envDismissed = true;
}

/**
 * Clear the env credential selection and show the manual API key input.
 */
function handleClearEnvCredentials() {
	formData.use_env_credentials = false;
	formData.api_key = "";
	testResult = null;
}

/**
 * Clear stale test result when connection fields change.
 */
function onConnectionFieldChange() {
	testResult = null;
}

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = createServerSchema.safeParse(formData);
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join(".");
			if (!fieldErrors[path]) {
				fieldErrors[path] = [];
			}
			fieldErrors[path].push(issue.message);
		}
		errors = fieldErrors;
		return false;
	}
	errors = {};
	return true;
}

/**
 * Get field errors for a specific field.
 */
function getFieldErrors(field: string): string[] {
	return errors[field] || [];
}

/**
 * Whether the "Test Connection" button should be enabled.
 */
const canTest = $derived(
	formData.use_env_credentials ||
		((formData.url ?? "").trim().length > 0 &&
			(formData.api_key ?? "").trim().length > 0),
);

/**
 * Whether the connection has been verified via a successful test.
 */
const connectionVerified = $derived(testResult?.success === true);

/**
 * Handle test connection button click.
 */
async function handleTestConnection() {
	testing = true;
	testResult = null;

	const testedUrl = formData.url ?? "";
	const testedApiKey = formData.api_key;
	const testedUseEnv = formData.use_env_credentials;
	const testedServerType = formData.server_type;

	try {
		const testPayload: ConnectionTestRequest = testedUseEnv
			? { server_type: testedServerType, use_env_credentials: true as const }
			: { url: testedUrl, api_key: testedApiKey ?? null };

		const result = await withErrorHandling(
			() => testConnection(testPayload),
			{ showErrorToast: false }
		);

		// Discard stale results if inputs changed during the request
		if (
			formData.url !== testedUrl ||
			formData.api_key !== testedApiKey ||
			formData.use_env_credentials !== testedUseEnv ||
			formData.server_type !== testedServerType
		) {
			return;
		}

		if (result.error || !result.data) {
			const errorBody = asErrorResponse(result.error);
			testResult = {
				success: false,
				message: errorBody?.detail ?? "Network error — could not reach the backend.",
			};
			return;
		}

		testResult = result.data;

		// Auto-populate server_type on success
		if (result.data.success && result.data.server_type) {
			formData.server_type = result.data.server_type;
		}
	} finally {
		testing = false;
	}
}

/**
 * Handle form submission.
 */
async function handleSubmit(event: Event) {
	event.preventDefault();

	if (!connectionVerified || !validateForm()) {
		return;
	}

	submitting = true;
	try {
		const data = transformCreateServerData(formData);
		const result = await withErrorHandling(() => createServer(data), {
			showErrorToast: false,
		});

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError(
				"Failed to add server",
				errorBody?.detail ?? "An error occurred",
			);
			return;
		}

		// Success
		showSuccess(
			"Server added successfully",
			`${result.data?.name} has been configured`,
		);

		// Close dialog (form resets via $effect watching open)
		open = false;

		// Notify parent to refresh list
		onSuccess?.();
	} finally {
		submitting = false;
	}
}

/**
 * Handle cancel button.
 */
function handleCancel() {
	open = false;
}
</script>

<Dialog.Root bind:open>
	<Dialog.Trigger>
		{#snippet child({ props })}
			<Button
				{...props}
				class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
			>
				<Plus class="size-4" />
				Add Server
			</Button>
		{/snippet}
	</Dialog.Trigger>

	<Dialog.Content
		class="border-cr-border bg-cr-surface sm:max-w-lg max-h-[85dvh] overflow-y-auto"
	>
		<Dialog.Header>
			<Dialog.Title class="text-cr-text flex items-center gap-2">
				<Server class="size-5 text-cr-accent" />
				Add Media Server
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				Connect a media server to manage user access.
			</Dialog.Description>
		</Dialog.Header>

		{#if showEnvBanner}
			<div class="min-w-0 rounded-lg border border-cr-accent/30 bg-cr-accent/5 p-3">
				<div class="flex items-start justify-between gap-2">
					<div class="flex items-center gap-2 text-sm font-medium text-cr-accent">
						<Info class="size-4 shrink-0" />
						Environment credentials detected
					</div>
					<button
						type="button"
						onclick={() => (envDismissed = true)}
						class="text-xs text-cr-text-muted hover:text-cr-text"
					>
						Dismiss
					</button>
				</div>
				<div class="mt-2 space-y-1.5">
					{#each completeEnvCredentials as credential (credential.server_type)}
						{@const providerMeta = providerList.find((p) => p.server_type === credential.server_type)}
						<button
							type="button"
							onclick={() => handleUseEnvCredentials(credential)}
							class="flex w-full items-center gap-3 rounded-md border border-cr-border bg-cr-bg px-3 py-2 text-left text-sm transition-colors hover:border-cr-accent/40 hover:bg-cr-accent/5"
						>
							<span
								class="shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold"
								style="background: {providerMeta?.color ?? '#6b7280'}20; color: {providerMeta?.color ?? '#6b7280'}"
							>
								{credential.display_name}
							</span>
							<span class="min-w-0 flex-1 text-xs text-cr-text-muted">
								Configured in environment
							</span>
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<form onsubmit={handleSubmit} class="min-w-0 space-y-4">
			<!-- Server Name -->
			<div class="space-y-2">
				<Label for="name" class="text-cr-text">Server Name</Label>
				<Input
					id="name"
					bind:value={formData.name}
					oninput={onConnectionFieldChange}
					placeholder="My Media Server"
					disabled={submitting}
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent"
					data-field="name"
				/>
				{#if getFieldErrors('name').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="name">
						{#each getFieldErrors('name') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Server Type Toggle -->
			<div class="space-y-2">
				<Label class="text-cr-text">Server Type</Label>
				<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
				<div class="flex rounded-lg border border-cr-border overflow-hidden" role="group">
					{#each providerList as provider, i (provider.server_type)}
						<button
							type="button"
							disabled={submitting}
							onclick={() => { formData.server_type = provider.server_type; onConnectionFieldChange(); }}
							class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors {i < providerList.length - 1 ? 'border-r' : ''} {formData.server_type === provider.server_type
								? ''
								: 'bg-cr-bg text-cr-text-muted hover:bg-cr-border border-cr-border'}"
							style={formData.server_type === provider.server_type ? getProviderActiveToggleStyle(provider.server_type) : ''}
							data-server-type={provider.server_type}
						>
							{provider.display_name}
						</button>
					{/each}
				</div>
				{#if getFieldErrors('server_type').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="server_type">
						{#each getFieldErrors('server_type') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Server URL -->
			<div class="space-y-2">
				<Label for="url" class="text-cr-text">Server URL</Label>
				{#if formData.use_env_credentials}
					<div class="flex items-center gap-2 rounded-md border border-cr-accent/30 bg-cr-accent/5 px-3 py-2">
						<KeyRound class="size-4 text-cr-accent shrink-0" />
						<span class="flex-1 text-sm text-cr-text">Configured in environment</span>
					</div>
				{:else}
					<Input
						id="url"
						type="url"
						bind:value={formData.url}
						oninput={onConnectionFieldChange}
						placeholder="https://media.example.com"
						disabled={submitting}
						class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm"
						data-field="url"
					/>
					<p class="text-cr-text-muted text-xs">Full URL including protocol (http:// or https://)</p>
				{/if}
				{#if getFieldErrors('url').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="url">
						{#each getFieldErrors('url') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- API Key -->
			<div class="space-y-2">
				<Label for="api_key" class="text-cr-text">API Key</Label>
				{#if formData.use_env_credentials}
					<div class="flex items-center gap-2 rounded-md border border-cr-accent/30 bg-cr-accent/5 px-3 py-2">
						<KeyRound class="size-4 text-cr-accent shrink-0" />
						<span class="flex-1 text-sm text-cr-text">Using environment credentials</span>
						<button
							type="button"
							onclick={handleClearEnvCredentials}
							class="text-cr-text-muted hover:text-cr-text p-0.5"
							aria-label="Clear environment credentials"
						>
							<X class="size-4" />
						</button>
					</div>
				{:else}
					<div class="relative">
						<Input
							id="api_key"
							type={showApiKey ? 'text' : 'password'}
							bind:value={formData.api_key}
							oninput={onConnectionFieldChange}
							placeholder="Enter API key"
							disabled={submitting}
							class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm pr-10"
							data-field="api_key"
						/>
						<button
							type="button"
							onclick={() => (showApiKey = !showApiKey)}
							class="absolute right-2 top-1/2 -translate-y-1/2 text-cr-text-muted hover:text-cr-text p-1"
							aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
						>
							{#if showApiKey}
								<EyeOff class="size-4" />
							{:else}
								<Eye class="size-4" />
							{/if}
						</button>
					</div>
				{/if}
				{#each providerList as provider (provider.server_type)}
					{#if formData.server_type === provider.server_type && provider.api_key_help_text}
						<p class="text-cr-text-muted text-xs">{provider.api_key_help_text}</p>
					{/if}
				{/each}
				{#if getFieldErrors('api_key').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="api_key">
						{#each getFieldErrors('api_key') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Test Connection -->
			<div class="space-y-2">
				<Button
					type="button"
					variant="outline"
					onclick={handleTestConnection}
					disabled={!canTest || testing || submitting}
					class="w-full border-cr-border bg-cr-bg hover:bg-cr-border text-cr-text"
				>
					{#if testing}
						<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						Testing...
					{:else}
						<Plug class="size-4" />
						Test Connection
					{/if}
				</Button>

				{#if testResult}
					{#if testResult.success}
						{@const providerMeta = providerList.find((p) => p.server_type === testResult?.server_type)}
						<div
							class="rounded-md border px-3 py-2 text-sm"
							style="border-color: {providerMeta?.color ?? '#22c55e'}40; background: {providerMeta?.color ?? '#22c55e'}10; color: {providerMeta?.color ?? '#22c55e'}"
						>
							<p class="font-medium break-all">
								Connected — {providerMeta?.display_name ?? testResult.server_type} server detected
							</p>
							{#if testResult.server_name}
								<p class="text-cr-text-muted text-xs mt-0.5 break-all">
									{testResult.server_name}{testResult.version ? ` (v${testResult.version})` : ""}
								</p>
							{/if}
						</div>
					{:else}
						<div class="rounded-md border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-sm text-rose-400">
							<p class="break-all">{testResult.message}</p>
						</div>
					{/if}
				{/if}
			</div>

			<!-- Form Actions -->
			<div class="flex items-center justify-end gap-3 pt-4 border-t border-cr-border">
				<Button
					type="button"
					variant="outline"
					onclick={handleCancel}
					disabled={submitting}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Cancel
				</Button>
				<Button
					type="submit"
					disabled={submitting || !connectionVerified}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					{#if submitting}
						<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						Testing Connection...
					{:else}
						Add Server
					{/if}
				</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
