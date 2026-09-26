<script lang="ts">
import { Loader2, ShieldCheck } from '@lucide/svelte';
import { getErrorDetail, type TotpSetupResponse, totpSetup, totpVerifySetup } from '$lib/api/auth';
import TotpCodeInput from '$lib/components/auth/totp-code-input.svelte';
import BackupCodesDisplay from '$lib/components/settings/backup-codes-display.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';

interface Props {
	onComplete: () => void;
	onSkip: () => void;
}

const { onComplete, onSkip }: Props = $props();

type Step = 'intro' | 'loading' | 'scan' | 'verify' | 'backup';

let step = $state<Step>('intro');
let setupData = $state<TotpSetupResponse | null>(null);
let backupCodes = $state<string[]>([]);
let verifying = $state(false);
let verifyError = $state('');
let showSecret = $state(false);
let setupError = $state('');
let totpInputRef: TotpCodeInput | undefined = $state();

async function startSetup() {
	step = 'loading';
	setupData = null;
	backupCodes = [];
	verifyError = '';
	setupError = '';
	showSecret = false;

	const result = await totpSetup();
	if (result.error) {
		setupError = getErrorDetail(result.error, 'Failed to initialize TOTP setup');
		step = 'intro';
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
	} catch {
		verifyError = 'Failed to verify code. Please try again.';
		totpInputRef?.reset();
	} finally {
		verifying = false;
	}
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<div class="flex items-center gap-2">
			<Card.Title class="text-lg text-cr-text">Two-Factor Authentication</Card.Title>
			<span
				class="rounded-full border border-cr-accent/30 bg-cr-accent/10 px-2 py-0.5 text-xs font-medium text-cr-accent"
			>
				Recommended
			</span>
		</div>
		<Card.Description class="text-cr-text-muted">
			Add an extra layer of security to your admin account with an authenticator app.
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if step === 'intro'}
			{#if setupError}
				<div
					class="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
				>
					{setupError}
				</div>
			{/if}

			<div class="mb-4 rounded-lg border border-cr-accent/30 bg-cr-accent/5 p-3">
				<div class="flex items-start gap-2">
					<ShieldCheck class="mt-0.5 size-4 shrink-0 text-cr-accent" />
					<p class="text-sm text-cr-text-muted">
						Two-factor authentication requires a code from your authenticator app (like Google
						Authenticator or Authy) each time you sign in, protecting your account even if your
						password is compromised.
					</p>
				</div>
			</div>

			<div class="flex items-center justify-between gap-3 border-t border-cr-border pt-4">
				<Button
					type="button"
					variant="ghost"
					onclick={onSkip}
					class="text-cr-text-muted hover:text-cr-text"
				>
					Set up later
				</Button>
				<Button
					type="button"
					onclick={startSetup}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					Set up now
				</Button>
			</div>
		{:else if step === 'loading'}
			<div class="flex flex-col items-center gap-4 py-8">
				<Loader2 class="size-8 animate-spin text-cr-accent" />
				<p class="text-sm text-cr-text-muted">Setting up two-factor authentication...</p>
			</div>
		{:else if step === 'scan'}
			<div class="flex flex-col items-center gap-4">
				<p class="text-sm text-cr-text-muted">
					Scan the QR code with your authenticator app, then continue to enter the verification
					code.
				</p>

				{#if setupData}
					<div class="rounded-lg bg-white p-3">
						{@html setupData.qr_code_svg}
					</div>

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

			<div class="flex items-center justify-end gap-3 border-t border-cr-border pt-4 mt-4">
				<Button
					type="button"
					onclick={() => (step = 'verify')}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					Continue
				</Button>
			</div>
		{:else if step === 'verify'}
			<div class="flex flex-col gap-4">
				<p class="text-sm text-cr-text-muted">
					Enter the 6-digit code from your authenticator app to verify setup.
				</p>

				{#if verifyError}
					<div
						class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
					>
						{verifyError}
					</div>
				{/if}

				<div class="py-2">
					<TotpCodeInput bind:this={totpInputRef} onsubmit={handleVerify} disabled={verifying} />
				</div>

				{#if verifying}
					<div class="flex items-center justify-center gap-2 text-sm text-cr-text-muted">
						<Loader2 class="size-4 animate-spin" />
						Verifying...
					</div>
				{/if}
			</div>

			<div class="flex items-center justify-between gap-3 border-t border-cr-border pt-4 mt-4">
				<Button
					variant="outline"
					onclick={() => (step = 'scan')}
					disabled={verifying}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Back
				</Button>
			</div>
		{:else if step === 'backup'}
			<div class="flex flex-col gap-4">
				<p class="text-sm text-cr-text-muted">
					Store these backup codes in a safe place. Each code can only be used once to sign in if
					you lose access to your authenticator app.
				</p>

				<BackupCodesDisplay codes={backupCodes} />
			</div>

			<div class="flex items-center justify-end gap-3 border-t border-cr-border pt-4 mt-2">
				<Button
					type="button"
					onclick={onComplete}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					Continue
				</Button>
			</div>
		{/if}

		{#if step === 'intro'}
			<p class="mt-3 text-center text-xs text-cr-text-dim">
				You can always enable this later in Settings.
			</p>
		{/if}
	</Card.Content>
</Card.Root>
