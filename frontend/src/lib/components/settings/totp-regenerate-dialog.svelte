<script lang="ts">
import { Loader2 } from '@lucide/svelte';
import { getErrorDetail, totpRegenerateBackupCodes } from '$lib/api/auth';
import TotpCodeInput from '$lib/components/auth/totp-code-input.svelte';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import { showApiError, showSuccess } from '$lib/utils/toast';
import BackupCodesDisplay from './backup-codes-display.svelte';

interface Props {
	open: boolean;
}

let { open = $bindable(false) }: Props = $props();

type Step = 'verify' | 'codes';

let step = $state<Step>('verify');
let backupCodes = $state<string[]>([]);
let loading = $state(false);
let error = $state('');
let totpInputRef: TotpCodeInput | undefined = $state();

function resetState() {
	step = 'verify';
	backupCodes = [];
	loading = false;
	error = '';
}

async function handleVerify(code: string) {
	error = '';
	loading = true;
	try {
		const result = await totpRegenerateBackupCodes({ code });
		if (result.error) {
			error = getErrorDetail(result.error, 'Invalid verification code');
			loading = false;
			totpInputRef?.reset();
			return;
		}
		backupCodes = result.data!.backup_codes;
		step = 'codes';
		showSuccess('Backup codes regenerated');
	} catch {
		error = 'Failed to regenerate codes. Please try again.';
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
	<Dialog.Content class="border-cr-border bg-cr-surface sm:max-w-lg" showCloseButton={!loading}>
		{#if step === 'verify'}
			<Dialog.Header>
				<Dialog.Title class="text-cr-text">Regenerate backup codes</Dialog.Title>
				<Dialog.Description class="text-cr-text-muted">
					Enter a code from your authenticator app. This will invalidate all existing backup codes.
				</Dialog.Description>
			</Dialog.Header>

			{#if error}
				<div
					class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
				>
					{error}
				</div>
			{/if}

			<div class="py-4">
				<TotpCodeInput bind:this={totpInputRef} onsubmit={handleVerify} disabled={loading} />
			</div>

			{#if loading}
				<div class="flex items-center justify-center gap-2 text-sm text-cr-text-muted">
					<Loader2 class="size-4 animate-spin" />
					Regenerating...
				</div>
			{/if}

			<Dialog.Footer>
				<Button
					variant="outline"
					onclick={closeDialog}
					disabled={loading}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Cancel
				</Button>
			</Dialog.Footer>
		{:else}
			<Dialog.Header>
				<Dialog.Title class="text-cr-text">New backup codes</Dialog.Title>
				<Dialog.Description class="text-cr-text-muted">
					Your previous backup codes have been invalidated. Save these new codes in a safe place.
				</Dialog.Description>
			</Dialog.Header>

			<BackupCodesDisplay codes={backupCodes} />

			<Dialog.Footer class="mt-2">
				<Button onclick={closeDialog} class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
					Done
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
