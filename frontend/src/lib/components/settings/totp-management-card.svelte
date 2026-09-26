<script lang="ts">
import { RefreshCw, Shield, ShieldCheck, ShieldOff } from '@lucide/svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import TotpDisableDialog from './totp-disable-dialog.svelte';
import TotpRegenerateDialog from './totp-regenerate-dialog.svelte';
import TotpSetupDialog from './totp-setup-dialog.svelte';

interface Props {
	totpEnabled: boolean;
}

let { totpEnabled = $bindable(false) }: Props = $props();

let showSetupDialog = $state(false);
let showDisableDialog = $state(false);
let showRegenerateDialog = $state(false);
</script>

<Card.Root>
	<Card.Header>
		<div class="flex items-center gap-2">
			<Shield class="size-5 text-cr-accent" />
			<Card.Title>Two-Factor Authentication</Card.Title>
		</div>
		<Card.Description>
			Add an extra layer of security to your account with a TOTP authenticator app.
		</Card.Description>
	</Card.Header>
	<Card.Content>
		<div class="space-y-4">
			<div class="flex items-center gap-3">
				<span class="text-sm text-cr-text">Status:</span>
				{#if totpEnabled}
					<Badge variant="outline" class="border-green-500/30 text-green-400">
						<ShieldCheck class="mr-1 size-3" />
						Enabled
					</Badge>
				{:else}
					<Badge variant="outline" class="border-cr-text-dim/30 text-cr-text-muted">
						<ShieldOff class="mr-1 size-3" />
						Disabled
					</Badge>
				{/if}
			</div>

			<div class="flex flex-wrap gap-2">
				{#if totpEnabled}
					<Button
						variant="outline"
						onclick={() => (showRegenerateDialog = true)}
						class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
					>
						<RefreshCw class="mr-1.5 size-4" />
						Regenerate backup codes
					</Button>
					<Button
						variant="outline"
						onclick={() => (showDisableDialog = true)}
						class="border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
					>
						<ShieldOff class="mr-1.5 size-4" />
						Disable 2FA
					</Button>
				{:else}
					<Button
						onclick={() => (showSetupDialog = true)}
						class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
					>
						<ShieldCheck class="mr-1.5 size-4" />
						Enable 2FA
					</Button>
				{/if}
			</div>
		</div>
	</Card.Content>
</Card.Root>

<TotpSetupDialog bind:open={showSetupDialog} oncomplete={() => (totpEnabled = true)} />
<TotpDisableDialog bind:open={showDisableDialog} oncomplete={() => (totpEnabled = false)} />
<TotpRegenerateDialog bind:open={showRegenerateDialog} />
