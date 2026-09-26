<script lang="ts">
import { Clock, Lock, RefreshCw } from '@lucide/svelte';
import { type SettingValue, updateExpirationInterval, updateSyncInterval } from '$lib/api/client';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { showApiError, showSuccess } from '$lib/utils/toast';

interface Props {
	syncInterval: SettingValue;
	expirationInterval: SettingValue;
}

let { syncInterval, expirationInterval }: Props = $props();

// svelte-ignore state_referenced_locally — intentionally captures initial values for editing
let syncNumeric = $state(Number(syncInterval.value ?? '900'));
// svelte-ignore state_referenced_locally
let expNumeric = $state(Number(expirationInterval.value ?? '3600'));
// svelte-ignore state_referenced_locally
let syncDisplay = $state(String(syncNumeric));
// svelte-ignore state_referenced_locally
let expDisplay = $state(String(expNumeric));
let savingSync = $state(false);
let savingExp = $state(false);

const syncPreview = $derived(formatInterval(syncNumeric));
const expPreview = $derived(formatInterval(expNumeric));

function formatInterval(seconds: number): string {
	if (!Number.isFinite(seconds)) return '—';
	if (seconds < 60) return `${seconds} seconds`;
	if (seconds < 3600) {
		const mins = Math.floor(seconds / 60);
		return mins === 1 ? '1 minute' : `${mins} minutes`;
	}
	const hours = Math.floor(seconds / 3600);
	const mins = Math.floor((seconds % 3600) / 60);
	if (mins === 0) return hours === 1 ? '1 hour' : `${hours} hours`;
	return `${hours}h ${mins}m`;
}

function handleSyncInput(e: Event) {
	syncDisplay = (e.currentTarget as HTMLInputElement).value;
	const n = Number(syncDisplay);
	if (Number.isFinite(n) && Number.isInteger(n) && n >= 60 && n <= 86400) syncNumeric = n;
}

function handleSyncBlur() {
	syncDisplay = String(syncNumeric);
}

function handleExpInput(e: Event) {
	expDisplay = (e.currentTarget as HTMLInputElement).value;
	const n = Number(expDisplay);
	if (Number.isFinite(n) && Number.isInteger(n) && n >= 60 && n <= 86400) expNumeric = n;
}

function handleExpBlur() {
	expDisplay = String(expNumeric);
}

async function handleSyncSave() {
	if (!Number.isFinite(syncNumeric) || syncNumeric < 60 || syncNumeric > 86400) return;
	savingSync = true;
	try {
		const result = await updateSyncInterval(syncNumeric);
		if (result.error) {
			showApiError(result.error);
		} else {
			showSuccess('Sync interval updated');
		}
	} finally {
		savingSync = false;
	}
}

async function handleExpSave() {
	if (!Number.isFinite(expNumeric) || expNumeric < 60 || expNumeric > 86400) return;
	savingExp = true;
	try {
		const result = await updateExpirationInterval(expNumeric);
		if (result.error) {
			showApiError(result.error);
		} else {
			showSuccess('Expiration check interval updated');
		}
	} finally {
		savingExp = false;
	}
}
</script>

<div class="space-y-6">
	<!-- Sync Interval Card -->
	<Card.Root>
		<Card.Header>
			<div class="flex items-center gap-2">
				<RefreshCw class="size-5 text-cr-accent" />
				<Card.Title>Media Server Sync Interval</Card.Title>
				{#if syncInterval.is_locked}
					<Badge variant="secondary" class="gap-1">
						<Lock class="size-3" />
						Environment Variable
					</Badge>
				{/if}
			</div>
			<Card.Description>
				How often Zondarr syncs users and libraries with your media servers.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<div class="space-y-2">
					<Label for="sync-interval">Interval (seconds)</Label>
					<Input
						id="sync-interval"
						type="number"
						min={60}
						max={86400}
						value={syncDisplay}
						oninput={handleSyncInput}
						onblur={handleSyncBlur}
						disabled={syncInterval.is_locked}
					/>
					<p class="text-sm text-muted-foreground">Every {syncPreview}</p>
				</div>
				<Button onclick={handleSyncSave} disabled={syncInterval.is_locked || savingSync}>
					{savingSync ? 'Saving...' : 'Save'}
				</Button>
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Expiration Check Interval Card -->
	<Card.Root>
		<Card.Header>
			<div class="flex items-center gap-2">
				<Clock class="size-5 text-cr-accent" />
				<Card.Title>Expiration Check Interval</Card.Title>
				{#if expirationInterval.is_locked}
					<Badge variant="secondary" class="gap-1">
						<Lock class="size-3" />
						Environment Variable
					</Badge>
				{/if}
			</div>
			<Card.Description>
				How often Zondarr checks for and deactivates expired invitations.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<div class="space-y-2">
					<Label for="exp-interval">Interval (seconds)</Label>
					<Input
						id="exp-interval"
						type="number"
						min={60}
						max={86400}
						value={expDisplay}
						oninput={handleExpInput}
						onblur={handleExpBlur}
						disabled={expirationInterval.is_locked}
					/>
					<p class="text-sm text-muted-foreground">Every {expPreview}</p>
				</div>
				<Button onclick={handleExpSave} disabled={expirationInterval.is_locked || savingExp}>
					{savingExp ? 'Saving...' : 'Save'}
				</Button>
			</div>
		</Card.Content>
	</Card.Root>
</div>
