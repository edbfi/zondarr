<script lang="ts">
import { Check, Copy, Download } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';

interface Props {
	codes: string[];
}

let { codes }: Props = $props();

let copied = $state(false);

async function copyAll() {
	await navigator.clipboard.writeText(codes.join('\n'));
	copied = true;
	setTimeout(() => (copied = false), 2000);
}

function downloadCodes() {
	const content = [
		'Zondarr — TOTP Backup Codes',
		'Keep these codes in a safe place.',
		'Each code can only be used once.',
		'',
		...codes
	].join('\n');

	const blob = new Blob([content], { type: 'text/plain' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'zondarr-backup-codes.txt';
	a.click();
	URL.revokeObjectURL(url);
}
</script>

<div class="space-y-4">
	<div class="grid grid-cols-2 gap-2 rounded-md border border-cr-border bg-cr-bg p-4">
		{#each codes as code}
			<span class="font-mono text-sm text-cr-text">{code}</span>
		{/each}
	</div>

	<div class="flex gap-2">
		<Button
			variant="outline"
			size="sm"
			onclick={copyAll}
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
		>
			{#if copied}
				<Check class="mr-1.5 size-4" />
				Copied
			{:else}
				<Copy class="mr-1.5 size-4" />
				Copy all
			{/if}
		</Button>
		<Button
			variant="outline"
			size="sm"
			onclick={downloadCodes}
			class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
		>
			<Download class="mr-1.5 size-4" />
			Download as text
		</Button>
	</div>
</div>
