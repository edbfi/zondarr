<script lang="ts">
import { Loader2 } from '@lucide/svelte';
import { getErrorDetail, totpDisable } from '$lib/api/auth';
import TotpCodeInput from '$lib/components/auth/totp-code-input.svelte';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { showApiError, showSuccess } from '$lib/utils/toast';

interface Props {
	open: boolean;
	oncomplete: () => void;
}

let { open = $bindable(false), oncomplete }: Props = $props();

let password = $state('');
let loading = $state(false);
let error = $state('');
let showCodeInput = $state(false);
let totpInputRef: TotpCodeInput | undefined = $state();

function resetState() {
	password = '';
	loading = false;
	error = '';
	showCodeInput = false;
}

function handlePasswordSubmit(e: SubmitEvent) {
	e.preventDefault();
	if (!password) {
		error = 'Password is required';
		return;
	}
	error = '';
	showCodeInput = true;
}

async function handleTotpSubmit(code: string) {
	error = '';
	loading = true;
	try {
		const result = await totpDisable({ password, code });
		if (result.error) {
			error = getErrorDetail(result.error, 'Failed to disable 2FA');
			loading = false;
			totpInputRef?.reset();
			return;
		}
		showSuccess('Two-factor authentication disabled');
		open = false;
		oncomplete();
	} catch {
		error = 'Failed to disable 2FA. Please try again.';
		totpInputRef?.reset();
	} finally {
		loading = false;
	}
}

function handleOpenChange(isOpen: boolean) {
	if (!isOpen && !loading) {
		resetState();
	}
}

function closeDialog() {
	open = false;
}

$effect(() => {
	if (open) {
		resetState();
	}
});
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content class="border-cr-border bg-cr-surface sm:max-w-md" showCloseButton={!loading}>
		<Dialog.Header>
			<Dialog.Title class="text-cr-text">Disable two-factor authentication</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				{#if showCodeInput}
					Enter the 6-digit code from your authenticator app to confirm.
				{:else}
					Enter your password to continue. This will remove 2FA from your account.
				{/if}
			</Dialog.Description>
		</Dialog.Header>

		{#if error}
			<div class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
				{error}
			</div>
		{/if}

		{#if showCodeInput}
			<div class="py-4">
				<TotpCodeInput bind:this={totpInputRef} onsubmit={handleTotpSubmit} disabled={loading} />
			</div>

			{#if loading}
				<div class="flex items-center justify-center gap-2 text-sm text-cr-text-muted">
					<Loader2 class="size-4 animate-spin" />
					Disabling...
				</div>
			{/if}

			<Dialog.Footer>
				<Button
					variant="outline"
					onclick={() => (showCodeInput = false)}
					disabled={loading}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Back
				</Button>
			</Dialog.Footer>
		{:else}
			<form onsubmit={handlePasswordSubmit} class="space-y-4">
				<div class="space-y-2">
					<Label for="disable-2fa-password">Password</Label>
					<Input
						id="disable-2fa-password"
						type="password"
						bind:value={password}
						autocomplete="current-password"
					/>
				</div>
				<Dialog.Footer>
					<Button
						variant="outline"
						type="button"
						onclick={closeDialog}
						class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
					>
						Cancel
					</Button>
					<Button type="submit" class="bg-rose-500 hover:bg-rose-600 text-white"> Continue </Button>
				</Dialog.Footer>
			</form>
		{/if}
	</Dialog.Content>
</Dialog.Root>
