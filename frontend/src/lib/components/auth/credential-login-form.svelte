<script lang="ts">
import { ChevronDown, ChevronUp } from '@lucide/svelte';
import { type AuthFieldInfo, getErrorDetail, loginExternal } from '$lib/api/auth';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { getProviderColor, getProviderIconSvg } from '$lib/stores/providers.svelte';

interface Props {
	method: string;
	displayName: string;
	fields: AuthFieldInfo[];
	onsuccess: () => void;
	ontotp: (challengeToken: string) => void;
	onerror: (message: string) => void;
}

const { method, displayName, fields, onsuccess, ontotp, onerror }: Props = $props();

let expanded = $state(false);
let fieldValues = $state<Record<string, string>>({});
let errors = $state<Record<string, string>>({});
let loading = $state(false);

const color = $derived(getProviderColor(method));
const iconSvg = $derived(getProviderIconSvg(method));

async function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	errors = {};

	// Validate required fields
	let hasErrors = false;
	for (const field of fields) {
		const val = fieldValues[field.name];
		if (field.required && (!val || val.trim() === '')) {
			errors[field.name] = `${field.label} is required`;
			hasErrors = true;
		} else if (field.field_type === 'url' && val && val.trim() !== '') {
			try {
				new URL(val);
			} catch {
				errors[field.name] = 'Must be a valid URL';
				hasErrors = true;
			}
		}
	}

	if (hasErrors) return;

	loading = true;
	try {
		const response = await loginExternal(method, fieldValues);
		if (response.error) {
			onerror(getErrorDetail(response.error, `${displayName} login failed`));
		} else if (response.data?.totp_required && response.data.challenge_token) {
			ontotp(response.data.challenge_token);
		} else {
			onsuccess();
		}
	} finally {
		loading = false;
	}
}

function getInputType(fieldType: string): string {
	if (fieldType === 'url') return 'url';
	if (fieldType === 'password') return 'password';
	return 'text';
}
</script>

{#if !expanded}
	<Button
		onclick={() => (expanded = true)}
		variant="outline"
		class="w-full border-cr-border bg-cr-bg text-cr-text"
		style="--provider-color: {color}"
	>
		<svg class="mr-2 size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
			<path d={iconSvg} />
		</svg>
		Sign in with {displayName}
		<ChevronDown class="ml-auto size-4" />
	</Button>
{:else}
	<div class="rounded-md border border-cr-border bg-cr-bg p-3">
		<button
			type="button"
			onclick={() => (expanded = false)}
			class="mb-3 flex w-full items-center gap-2 text-sm font-medium text-cr-text"
		>
			<svg class="size-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
				<path d={iconSvg} />
			</svg>
			{displayName}
			login
			<ChevronUp class="ml-auto size-4 text-cr-text-muted" />
		</button>

		<form onsubmit={handleSubmit} class="flex flex-col gap-3">
			{#each fields as field (field.name)}
				<div class="flex flex-col gap-1">
					<Label for="auth-{field.name}" class="text-xs text-cr-text">{field.label}</Label>
					<Input
						id="auth-{field.name}"
						type={getInputType(field.field_type)}
						bind:value={fieldValues[field.name]}
						placeholder={field.placeholder}
						autocomplete={field.field_type === 'password'
	? 'current-password'
	: field.name === 'username'
		? 'username'
		: undefined}
						class="h-8 border-cr-border bg-cr-surface text-cr-text text-sm placeholder:text-cr-text-dim"
					/>
					{#if errors[field.name]}
						<p class="text-xs text-red-400">{errors[field.name]}</p>
					{/if}
				</div>
			{/each}

			<Button
				type="submit"
				disabled={loading}
				size="sm"
				class="w-full text-white provider-submit-btn"
				style="background: {color}; --provider-submit-color: {color}"
			>
				{#if loading}
					Connecting...
				{:else}
					Sign in
				{/if}
			</Button>
		</form>
	</div>
{/if}

<style>
:global(button[style*="--provider-color"]:hover) {
	background: color-mix(in srgb, var(--provider-color) 10%, transparent);
	color: var(--provider-color);
	border-color: color-mix(in srgb, var(--provider-color) 30%, transparent);
}

:global(.provider-submit-btn:hover) {
	filter: brightness(0.9);
}
</style>
