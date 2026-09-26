<script lang="ts">
import { Loader2 } from '@lucide/svelte';
import { getErrorDetail, type TotpSetupResponse, totpSetup, totpVerifySetup } from '$lib/api/auth';
import TotpCodeInput from '$lib/components/auth/totp-code-input.svelte';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import { showApiError, showSuccess } from '$lib/utils/toast';
import BackupCodesDisplay from './backup-codes-display.svelte';

interface Props {
	open: boolean;
	oncomplete: () => void;
}

let { open = $bindable(false), oncomplete }: Props = $props();

type Step = 'loading' | 'scan' | 'verify' | 'backup';

let step = $state<Step>('loading');
let setupData = $state<TotpSetupResponse | null>(null);
let backupCodes = $state<string[]>([]);
let verifying = $state(false);
let verifyError = $state('');
let showSecret = $state(false);
let totpInputRef: TotpCodeInput | undefined = $state();

async function startSetup() {
	step = 'loading';
	setupData = null;
	backupCodes = [];
	verifyError = '';
	showSecret = false;

	const result = await totpSetup();
	if (result.error) {
		showApiError(result.error);
		open = false;
		return;
	}
	setupData = result.data!;
	step = 'scan';
}

async function handleVerify(code: string) {
	verifyError = '';
	verifying = true;
	try {
		const result = await totpVerifySetup({ code });
		if (result.error) {
			verifyError = getErrorDetail(result.error, 'Invalid verification code');
			verifying = false;
			totpInputRef?.reset();
			return;
		}
		backupCodes = result.data!.backup_codes;
		step = 'backup';
		showSuccess('Two-factor authentication enabled');
	} catch {
		verifyError = 'Failed to verify code. Please try again.';
		totpInputRef?.reset();
	} finally {
		verifying = false;
	}
}

function handleClose() {
	if (step === 'backup') {
		oncomplete();
	}
	open = false;
}

function handleOpenChange(isOpen: boolean) {
	if (!isOpen) {
		handleClose();
	}
}

$effect(() => {
	if (open) {
		startSetup();
	}
});
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content
		class="border-cr-border bg-cr-surface sm:max-w-lg"
		showCloseButton={step !== 'loading' && !verifying}
	>
		{#if step === 'loading'}
			<div class="flex flex-col items-center gap-4 py-8">
				<Loader2 class="size-8 animate-spin text-cr-accent" />
				<p class="text-sm text-cr-text-muted">Setting up two-factor authentication...</p>
			</div>
		{:else if step === 'scan'}
			<Dialog.Header>
				<Dialog.Title class="text-cr-text">Set up two-factor authentication</Dialog.Title>
				<Dialog.Description class="text-cr-text-muted">
					Scan the QR code with your authenticator app, then enter the verification code.
				</Dialog.Description>
			</Dialog.Header>

			<div class="flex flex-col items-center gap-4">
				<!-- QR Code -->
				{#if setupData}
					<div class="rounded-lg bg-white p-3">
						{@html setupData.qr_code_svg}
					</div>

					<!-- Manual entry -->
					<div class="w-full">
						<button
							type="button"
							onclick={() => (showSecret = !showSecret)}
							class="text-sm text-cr-accent hover:text-cr-accent-hover"
						>
							{showSecret ? 'Hide' : 'Show'}
							manual entry key
						</button>
						{#if showSecret}
							<div
								class="mt-2 rounded-md border border-cr-border bg-cr-bg p-3 font-mono text-xs text-cr-text break-all select-all"
							>
								{new URL(setupData.provisioning_uri).searchParams.get('secret') ?? ''}
							</div>
						{/if}
					</div>
				{/if}
			</div>

			<Dialog.Footer class="mt-4">
				<Button
					onclick={() => (step = 'verify')}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					Continue
				</Button>
			</Dialog.Footer>
		{:else if step === 'verify'}
			<Dialog.Header>
				<Dialog.Title class="text-cr-text">Verify authenticator app</Dialog.Title>
				<Dialog.Description class="text-cr-text-muted">
					Enter the 6-digit code from your authenticator app to verify setup.
				</Dialog.Description>
			</Dialog.Header>

			{#if verifyError}
				<div
					class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
				>
					{verifyError}
				</div>
			{/if}

			<div class="py-4">
				<TotpCodeInput bind:this={totpInputRef} onsubmit={handleVerify} disabled={verifying} />
			</div>

			{#if verifying}
				<div class="flex items-center justify-center gap-2 text-sm text-cr-text-muted">
					<Loader2 class="size-4 animate-spin" />
					Verifying...
				</div>
			{/if}

			<Dialog.Footer>
				<Button
					variant="outline"
					onclick={() => (step = 'scan')}
					disabled={verifying}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Back
				</Button>
			</Dialog.Footer>
		{:else if step === 'backup'}
			<Dialog.Header>
				<Dialog.Title class="text-cr-text">Save your backup codes</Dialog.Title>
				<Dialog.Description class="text-cr-text-muted">
					Store these codes in a safe place. Each code can only be used once to sign in if you lose
					access to your authenticator app.
				</Dialog.Description>
			</Dialog.Header>

			<BackupCodesDisplay codes={backupCodes} />

			<Dialog.Footer class="mt-2">
				<Button onclick={handleClose} class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
					Done
				</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>
