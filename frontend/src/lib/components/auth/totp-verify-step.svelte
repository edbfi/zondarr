<script lang="ts">
import { Shield } from '@lucide/svelte';
import { getErrorDetail, verifyBackupCode, verifyTotp } from '$lib/api/auth';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { backupCodeSchema } from '$lib/schemas/auth';
import TotpCodeInput from './totp-code-input.svelte';

interface Props {
	challengeToken: string;
	onsuccess: () => void;
	oncancel: () => void;
}

const { challengeToken, onsuccess, oncancel }: Props = $props();

let loading = $state(false);
let error = $state('');
let useBackupCode = $state(false);
let backupCode = $state('');
let backupError = $state('');
let totpInputRef: TotpCodeInput | undefined = $state();

async function handleTotpSubmit(code: string) {
	error = '';
	loading = true;
	try {
		const result = await verifyTotp({
			challenge_token: challengeToken,
			code
		});
		if (result.error) {
			error = getErrorDetail(result.error, 'Invalid verification code');
			loading = false;
			totpInputRef?.reset();
			return;
		}
		onsuccess();
	} catch {
		error = 'Failed to verify code. Please try again.';
		loading = false;
		totpInputRef?.reset();
	}
}

async function handleBackupSubmit(e: SubmitEvent) {
	e.preventDefault();
	backupError = '';

	const result = backupCodeSchema.safeParse({ code: backupCode });
	if (!result.success) {
		backupError = result.error.issues[0]?.message ?? 'Invalid backup code';
		return;
	}

	loading = true;
	try {
		const apiResult = await verifyBackupCode({
			challenge_token: challengeToken,
			code: backupCode
		});
		if (apiResult.error) {
			backupError = getErrorDetail(apiResult.error, 'Invalid backup code');
			loading = false;
			return;
		}
		onsuccess();
	} catch {
		backupError = 'Failed to verify backup code. Please try again.';
		loading = false;
	}
}

function switchToBackup() {
	useBackupCode = true;
	error = '';
	backupError = '';
}

function switchToTotp() {
	useBackupCode = false;
	error = '';
	backupError = '';
	backupCode = '';
}
</script>

<div class="flex flex-col items-center gap-4">
	<div class="flex h-12 w-12 items-center justify-center rounded-full bg-cr-accent/10">
		<Shield class="h-6 w-6 text-cr-accent" />
	</div>

	<div class="text-center">
		<h2 class="text-lg font-medium text-cr-text">Two-factor authentication</h2>
		{#if useBackupCode}
			<p class="mt-1 text-sm text-cr-text-muted">Enter a backup code to continue</p>
		{:else}
			<p class="mt-1 text-sm text-cr-text-muted">Enter the code from your authenticator app</p>
		{/if}
	</div>

	{#if error}
		<div
			class="w-full rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
		>
			{error}
		</div>
	{/if}

	{#if useBackupCode}
		{#if backupError}
			<div
				class="w-full rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
			>
				{backupError}
			</div>
		{/if}

		<form onsubmit={handleBackupSubmit} class="flex w-full flex-col gap-3">
			<div class="flex flex-col gap-1.5">
				<Label for="backup-code" class="text-cr-text">Backup code</Label>
				<Input
					id="backup-code"
					type="text"
					bind:value={backupCode}
					placeholder="XXXX-XXXX"
					disabled={loading}
					autocomplete="off"
					class="border-cr-border bg-cr-bg text-center font-mono text-cr-text placeholder:text-cr-text-dim"
				/>
			</div>
			<Button
				type="submit"
				disabled={loading}
				class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
			>
				{#if loading}
					Verifying...
				{:else}
					Verify backup code
				{/if}
			</Button>
		</form>

		<button
			type="button"
			onclick={switchToTotp}
			disabled={loading}
			class="text-sm text-cr-accent hover:text-cr-accent-hover disabled:opacity-50"
		>
			Use authenticator app instead
		</button>
	{:else}
		<TotpCodeInput bind:this={totpInputRef} onsubmit={handleTotpSubmit} disabled={loading} />

		{#if loading}
			<div class="flex items-center gap-2 text-sm text-cr-text-muted">
				<div
					class="h-4 w-4 animate-spin rounded-full border-2 border-cr-text-muted border-t-cr-accent"
				></div>
				Verifying...
			</div>
		{/if}

		<button
			type="button"
			onclick={switchToBackup}
			disabled={loading}
			class="text-sm text-cr-accent hover:text-cr-accent-hover disabled:opacity-50"
		>
			Use a backup code instead
		</button>
	{/if}

	<button
		type="button"
		onclick={oncancel}
		disabled={loading}
		class="text-sm text-cr-text-muted hover:text-cr-text disabled:opacity-50"
	>
		Back to login
	</button>
</div>
